from decimal import Decimal, InvalidOperation
from flask import Blueprint, jsonify, request, current_app
from app.models.compra import Compra
from app.models.cliente import Cliente
from app.extensions import db

compras_bp = Blueprint("compras", __name__)


@compras_bp.route("/", methods=["GET"])
def listar():
    id_cliente = request.args.get("id_cliente", type=int)
    query = Compra.query
    if id_cliente:
        query = query.filter_by(id_cliente=id_cliente)
    compras = query.order_by(Compra.data.desc()).all()
    return jsonify([c.to_dict() for c in compras])


@compras_bp.route("/", methods=["POST"])
def registrar():
    """Sprint 3 - Registra compra, calcula pontos e credita no cliente."""
    data = request.get_json() or {}

    # Aceita id_cliente OU telefone (fluxo do PDV/Arduino)
    cliente = None
    if data.get("id_cliente"):
        cliente = Cliente.query.get(data["id_cliente"])
    elif data.get("telefone"):
        cliente = Cliente.query.filter_by(telefone=data["telefone"]).first()
    if not cliente:
        return jsonify({"erro": "Cliente nao encontrado"}), 404

    try:
        valor = Decimal(str(data.get("valor")))
    except (InvalidOperation, TypeError):
        return jsonify({"erro": "valor invalido"}), 400
    if valor <= 0:
        return jsonify({"erro": "valor deve ser maior que zero"}), 400

    pontos_por_real = current_app.config.get("PONTOS_POR_REAL", 1)
    pontos_gerados = int(valor) * pontos_por_real

    compra = Compra(id_cliente=cliente.id_cliente, valor=valor, pontos_gerados=pontos_gerados)
    cliente.pontos_acumulados += pontos_gerados
    db.session.add(compra)
    db.session.commit()

    return jsonify({
        "compra": compra.to_dict(),
        "cliente": cliente.to_dict(),
        "saldo_atualizado": cliente.pontos_acumulados,
    }), 201
