import hmac
import re
from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user
from flask_wtf.csrf import validate_csrf
from sqlalchemy.exc import IntegrityError
from sqlalchemy import inspect
from wtforms.validators import ValidationError
from app.models.compra import Compra
from app.models.cliente import Cliente
from app.extensions import csrf, db, limiter
from app.services.pontos import registrar_movimentacao

compras_bp = Blueprint("compras", __name__)


def verificar_autenticacao_pontuacao():
    """
    Permite pontuação apenas por:
    1. Vendedora autenticada via sessão web; OU
    2. Terminal IoT (ESP8266) com token pré-compartilhado seguro.
    """
    if current_user.is_authenticated and getattr(current_user, "is_vendedora", False):
        if not getattr(current_user, "ativo", True):
            return False, None
        if not current_user.tem_permissao("pontos.adicionar"):
            return False, None
        return True, "vendedora"

    device_key = request.headers.get("X-Device-Key")
    expected_key = current_app.config.get("IOT_DEVICE_KEY")
    if device_key and expected_key and hmac.compare_digest(device_key, expected_key):
        return True, "iot_device"

    return False, None


@compras_bp.route("/", methods=["GET"])
@login_required
def listar():
    """Exige login e segrega a visão de compras por perfil."""
    query = Compra.query.filter(Compra.tipo_eh("COMPRA"))

    if getattr(current_user, "is_cliente", False):
        query = query.filter_by(id_cliente=current_user.id_cliente)
    elif getattr(current_user, "is_vendedora", False):
        if not current_user.tem_permissao("pontos.visualizar"):
            return jsonify({"erro": "Acesso negado. Requer permissão 'pontos.visualizar'."}), 403
        id_cliente = request.args.get("id_cliente", type=int)
        if id_cliente:
            query = query.filter_by(id_cliente=id_cliente)
    else:
        return jsonify({"erro": "Acesso nao autorizado"}), 403

    compras = query.order_by(Compra.data.desc()).all()
    return jsonify([c.to_dict() for c in compras])


@compras_bp.route("/", methods=["POST"])
@csrf.exempt
@limiter.limit("30 per minute")
def registrar():
    """
    Pontuação restrita a vendedoras ou hardware autorizado.
    Executa com bloqueio pessimista (with_for_update) e ledger atômico de transação.
    """
    autorizado, origem = verificar_autenticacao_pontuacao()
    if not autorizado:
        return jsonify({"erro": "Acesso nao autorizado para pontuacao."}), 401

    if origem == "vendedora" and current_app.config.get("WTF_CSRF_ENABLED", True):
        token_csrf = request.headers.get("X-CSRFToken") or request.headers.get("X-CSRF-Token")
        try:
            validate_csrf(token_csrf)
        except ValidationError:
            return jsonify({"erro": "Token CSRF ausente ou invalido"}), 400

    data = request.get_json() or {}
    chave_idempotencia = str(request.headers.get("X-Idempotency-Key") or "").strip() or None
    if chave_idempotencia and not re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", chave_idempotencia):
        return jsonify({"erro": "X-Idempotency-Key deve conter de 8 a 128 caracteres seguros"}), 400

    try:
        # Busca com lock pessimista para evitar concorrência no saldo
        query_cli = Cliente.query.with_for_update().filter(Cliente.nivel_acesso == "CLIENTE")
        id_cli_raw = data.get("id_cliente")
        if id_cli_raw is not None:
            if isinstance(id_cli_raw, bool) or not isinstance(id_cli_raw, int):
                try:
                    id_cli = int(id_cli_raw)
                except (ValueError, TypeError):
                    db.session.rollback()
                    return jsonify({"erro": "id_cliente deve ser um número inteiro"}), 400
            else:
                id_cli = id_cli_raw
            cliente = query_cli.filter_by(id_cliente=id_cli).first()
        elif data.get("telefone"):
            identificador = str(data["telefone"]).strip()
            tel_limpo = re.sub(r"\D", "", identificador)
            cliente = query_cli.filter(
                (Cliente.telefone == identificador) | (Cliente.telefone == tel_limpo)
            ).first()
        else:
            cliente = None

        if not cliente:
            db.session.rollback()
            return jsonify({"erro": "Cliente nao encontrado"}), 404

        if not getattr(cliente, "ativo", True):
            db.session.rollback()
            return jsonify({"erro": "Cliente está inativo. Pontuação não permitida."}), 400

        if chave_idempotencia:
            existente = Compra.query.filter(
                Compra.chave_idempotencia == chave_idempotencia,
            ).first()
            if existente:
                db.session.rollback()
                if existente.id_cliente != cliente.id_cliente or str(existente.tipo_movimentacao).strip().upper() != "COMPRA":
                    return jsonify({"erro": "Chave de idempotência já utilizada em outra operação"}), 409
                return jsonify({
                    "status": "sucesso",
                    "duplicada": True,
                    "origem": existente.origem,
                    "pontos_adicionados": 0,
                    "compra": existente.to_dict(),
                    "cliente": cliente.to_dict(),
                    "saldo_atualizado": cliente.pontos_acumulados,
                }), 200

        # Regra de negócio obrigatória IT Clube: 1 COMPRA VÁLIDA = 1 PONTO
        pontos_gerados = 1

        sucesso, mov, erro = registrar_movimentacao(
            cliente_id=cliente.id_cliente,
            tipo="COMPRA",
            quantidade=pontos_gerados,
            origem=origem,
            motivo="Compra registrada (+1 ponto)",
            chave_idempotencia=chave_idempotencia,
        )

        if not sucesso:
            db.session.rollback()
            return jsonify({"erro": erro or "Falha ao creditar pontos no ledger."}), 400

        mov.descricao = "Compra registrada (+1 ponto)"
        compra = mov

        db.session.commit()

        return jsonify({
            "status": "sucesso",
            "origem": origem,
            "pontos_adicionados": pontos_gerados,
            "compra": compra.to_dict(),
            "cliente": cliente.to_dict(),
            "saldo_atualizado": cliente.pontos_acumulados,
        }), 201

    except IntegrityError as error:
        db.session.rollback()
        constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
        unique_keys = []
        if chave_idempotencia and getattr(error.orig, "pgcode", None) == "23505":
            inspector = inspect(db.engine)
            unique_keys = [i["name"] for i in inspector.get_indexes("historico")
                           if i["unique"] and i["column_names"] == ["chave_idempotencia"]]
            unique_keys += [i["name"] for i in inspector.get_unique_constraints("historico")
                            if i["column_names"] == ["chave_idempotencia"]]
        if chave_idempotencia and constraint in unique_keys:
            existente = Compra.query.filter_by(chave_idempotencia=chave_idempotencia).first()
            if existente:
                if existente.id_cliente != cliente.id_cliente or str(existente.tipo_movimentacao).strip().upper() != "COMPRA":
                    return jsonify({"erro": "Chave de idempotência já utilizada em outra operação"}), 409
                cliente_atual = db.session.get(Cliente, existente.id_cliente)
                return jsonify({
                    "status": "sucesso", "duplicada": True,
                    "origem": existente.origem, "pontos_adicionados": 0,
                    "compra": existente.to_dict(), "cliente": cliente_atual.to_dict(),
                    "saldo_atualizado": cliente_atual.pontos_acumulados,
                }), 200
        current_app.logger.exception("Falha de integridade ao registrar compra")
        return jsonify({"erro": "Falha ao registrar compra no banco de dados"}), 500
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha transacional ao registrar compra")
        return jsonify({"erro": "Falha ao registrar compra no banco de dados"}), 500
