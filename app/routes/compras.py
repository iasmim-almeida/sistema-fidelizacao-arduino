import hmac
import re
from decimal import Decimal, InvalidOperation
from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user
from app.models.compra import Compra
from app.models.cliente import Cliente
from app.extensions import db
from app.services.pontos import registrar_movimentacao
from app.services.auditoria import registrar_auditoria

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
        return True, "vendedora"

    device_key = request.headers.get("X-Device-Key")
    expected_key = current_app.config.get("IOT_DEVICE_KEY")
    if device_key and expected_key and hmac.compare_digest(device_key, expected_key):
        return True, "iot_device"

    return False, None


@compras_bp.route("/", methods=["GET"])
@login_required
def listar():
    """Mitigação VULN-01: Exige login e segrega visão de compras por perfil."""
    query = Compra.query

    if getattr(current_user, "is_cliente", False):
        query = query.filter_by(id_cliente=current_user.id_cliente)
    elif getattr(current_user, "is_vendedora", False):
        id_cliente = request.args.get("id_cliente", type=int)
        if id_cliente:
            query = query.filter_by(id_cliente=id_cliente)
    else:
        return jsonify({"erro": "Acesso nao autorizado"}), 403

    compras = query.order_by(Compra.data.desc()).all()
    return jsonify([c.to_dict() for c in compras])


@compras_bp.route("/", methods=["POST"])
def registrar():
    """
    Mitigação VULN-01 e VULN-03: Pontuação restrita a vendedoras ou hardware autorizado.
    Executa com bloqueio pessimista (with_for_update) e ledger atômico de transação.
    """
    autorizado, origem = verificar_autenticacao_pontuacao()
    if not autorizado:
        return jsonify({"erro": "Acesso nao autorizado para pontuacao."}), 401

    data = request.get_json() or {}

    try:
        # Busca com lock pessimista para evitar concorrência no saldo
        query_cli = Cliente.query.with_for_update()
        if data.get("id_cliente"):
            cliente = query_cli.filter_by(id_cliente=data["id_cliente"]).first()
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

        try:
            valor = Decimal(str(data.get("valor")))
        except (InvalidOperation, TypeError):
            db.session.rollback()
            return jsonify({"erro": "valor invalido"}), 400

        if valor <= 0:
            db.session.rollback()
            return jsonify({"erro": "valor deve ser maior que zero"}), 400

        if valor > Decimal("50000.00"):
            db.session.rollback()
            return jsonify({"erro": "valor excede o limite maximo por transacao"}), 400

        pontos_por_real = current_app.config.get("PONTOS_POR_REAL", 1)
        pontos_gerados = int(valor) * pontos_por_real

        # Cria a compra
        compra = Compra(id_cliente=cliente.id_cliente, valor=valor, pontos_gerados=pontos_gerados)
        db.session.add(compra)
        db.session.flush()

        # Registra no ledger de pontos de forma atômica
        usuario_id = current_user.id_usuario if current_user.is_authenticated and getattr(current_user, "is_vendedora", False) else None
        sucesso, mov, erro = registrar_movimentacao(
            cliente_id=cliente.id_cliente,
            tipo="COMPRA",
            quantidade=pontos_gerados,
            origem=origem,
            motivo=f"Compra no valor de R$ {valor:.2f}",
            usuario_id=usuario_id,
            compra_id=compra.id_compra,
        )

        if not sucesso:
            db.session.rollback()
            return jsonify({"erro": erro or "Falha ao creditar pontos no ledger."}), 400

        db.session.commit()

        if usuario_id:
            registrar_auditoria(
                acao="PONTUAR_COMPRA",
                entidade="compra",
                entidade_id=compra.id_compra,
                detalhes={"id_cliente": cliente.id_cliente, "valor": str(valor), "pontos": pontos_gerados, "origem": origem},
            )
            db.session.commit()

        return jsonify({
            "status": "sucesso",
            "origem": origem,
            "compra": compra.to_dict(),
            "cliente": cliente.to_dict(),
            "saldo_atualizado": cliente.pontos_acumulados,
        }), 201

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha transacional ao registrar compra")
        return jsonify({"erro": "Falha ao registrar compra no banco de dados"}), 500
