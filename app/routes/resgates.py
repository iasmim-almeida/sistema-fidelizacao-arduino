import re
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app.models.resgate import Resgate
from app.models.cliente import Cliente
from app.extensions import db

resgates_bp = Blueprint("resgates", __name__)


@resgates_bp.route("/", methods=["GET"])
@login_required
def listar():
    """Mitigação VULN-01: Exige autenticação e segrega visualização de resgates por perfil."""
    query = Resgate.query

    if getattr(current_user, "is_cliente", False):
        query = query.filter_by(id_cliente=current_user.id_cliente)
    elif getattr(current_user, "is_vendedora", False):
        id_cliente = request.args.get("id_cliente", type=int)
        if id_cliente:
            query = query.filter_by(id_cliente=id_cliente)
    else:
        return jsonify({"erro": "Acesso nao autorizado"}), 403

    resgates = query.order_by(Resgate.data.desc()).all()
    return jsonify([r.to_dict() for r in resgates])


@resgates_bp.route("/", methods=["POST"])
@login_required
def registrar():
    """
    Mitigação VULN-01 e VULN-04:
    Exige autenticação, restringe cliente ao próprio saldo e utiliza
    bloqueio pessimista (with_for_update) para evitar condições de corrida (Double Spending).
    """
    data = request.get_json() or {}

    # Define o alvo do resgate garantindo validação de perfil/posse do recurso
    if getattr(current_user, "is_cliente", False):
        alvo_id = current_user.id_cliente
    elif getattr(current_user, "is_vendedora", False):
        alvo_id = data.get("id_cliente")
        if not alvo_id and data.get("telefone"):
            identificador = str(data["telefone"]).strip()
            tel_limpo = re.sub(r"\D", "", identificador)
            c_encontrado = Cliente.query.filter(
                (Cliente.telefone == identificador) | (Cliente.telefone == tel_limpo)
            ).first()
            if c_encontrado:
                alvo_id = c_encontrado.id_cliente
    else:
        return jsonify({"erro": "Perfil sem permissao para efetuar resgates"}), 403

    if not alvo_id:
        return jsonify({"erro": "Cliente nao informado para o resgate"}), 400

    pontos = data.get("pontos_utilizados")
    descricao = (data.get("descricao_recompensa") or "").strip()

    if not isinstance(pontos, int) or pontos <= 0:
        return jsonify({"erro": "pontos_utilizados deve ser inteiro positivo"}), 400
    if not descricao:
        return jsonify({"erro": "descricao_recompensa e obrigatoria"}), 400

    try:
        # Mitigação VULN-04: SELECT ... FOR UPDATE bloqueia o registro até a conclusão da transação
        cliente = Cliente.query.with_for_update().filter_by(id_cliente=alvo_id).first()

        if not cliente:
            db.session.rollback()
            return jsonify({"erro": "Cliente nao encontrado"}), 404

        if pontos > cliente.pontos_acumulados:
            db.session.rollback()
            return jsonify({
                "erro": "Saldo insuficiente",
                "saldo_atual": cliente.pontos_acumulados,
                "pontos_solicitados": pontos,
            }), 400

        resgate = Resgate(
            id_cliente=cliente.id_cliente,
            pontos_utilizados=pontos,
            descricao_recompensa=descricao,
        )
        cliente.pontos_acumulados -= pontos
        db.session.add(resgate)
        db.session.commit()

        return jsonify({
            "status": "sucesso",
            "resgate": resgate.to_dict(),
            "cliente": cliente.to_dict(),
            "saldo_atualizado": cliente.pontos_acumulados,
        }), 201

    except Exception:
        db.session.rollback()
        return jsonify({"erro": "Falha transacional ao processar resgate"}), 500
