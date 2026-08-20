from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError
from app.models.cliente import Cliente
from app.extensions import db

clientes_bp = Blueprint("clientes", __name__)


@clientes_bp.route("/", methods=["GET"])
def listar():
    telefone = request.args.get("telefone")
    if telefone:
        cliente = Cliente.query.filter_by(telefone=telefone).first()
        if not cliente:
            return jsonify({"erro": "Cliente nao encontrado"}), 404
        return jsonify(cliente.to_dict())
    clientes = Cliente.query.order_by(Cliente.nome).all()
    return jsonify([c.to_dict() for c in clientes])


@clientes_bp.route("/<int:id>", methods=["GET"])
def obter(id):
    cliente = Cliente.query.get_or_404(id)
    return jsonify(cliente.to_dict())


@clientes_bp.route("/", methods=["POST"])
def cadastrar():
    data = request.get_json() or {}
    if not data.get("nome") or not data.get("telefone"):
        return jsonify({"erro": "nome e telefone sao obrigatorios"}), 400
    cliente = Cliente(
        nome=data["nome"],
        telefone=data["telefone"],
        email=data.get("email"),
        endereco=data.get("endereco"),
    )
    try:
        db.session.add(cliente)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"erro": "Telefone ou email ja cadastrado"}), 409
    return jsonify(cliente.to_dict()), 201
