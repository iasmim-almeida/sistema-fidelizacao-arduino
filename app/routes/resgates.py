from flask import Blueprint, jsonify, request
from app.models.resgate import Resgate
from app.models.cliente import Cliente
from app.extensions import db

resgates_bp = Blueprint("resgates", __name__)


@resgates_bp.route("/", methods=["GET"])
def listar():
    id_cliente = request.args.get("id_cliente", type=int)
    query = Resgate.query
    if id_cliente:
        query = query.filter_by(id_cliente=id_cliente)
    resgates = query.order_by(Resgate.data.desc()).all()
    return jsonify([r.to_dict() for r in resgates])


@resgates_bp.route("/", methods=["POST"])
def registrar():
    """Sprint 4 - Valida saldo, debita pontos e registra o resgate."""
    data = request.get_json() or {}

    cliente = None
    if data.get("id_cliente"):
        cliente = Cliente.query.get(data["id_cliente"])
    elif data.get("telefone"):
        cliente = Cliente.query.filter_by(telefone=data["telefone"]).first()
    if not cliente:
        return jsonify({"erro": "Cliente nao encontrado"}), 404

    pontos = data.get("pontos_utilizados")
    descricao = (data.get("descricao_recompensa") or "").strip()
    if not isinstance(pontos, int) or pontos <= 0:
        return jsonify({"erro": "pontos_utilizados deve ser inteiro positivo"}), 400
    if not descricao:
        return jsonify({"erro": "descricao_recompensa e obrigatoria"}), 400

    if pontos > cliente.pontos_acumulados:
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
        "resgate": resgate.to_dict(),
        "cliente": cliente.to_dict(),
        "saldo_atualizado": cliente.pontos_acumulados,
    }), 201
