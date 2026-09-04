import re
import secrets
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError
from app.models.cliente import Cliente
from app.extensions import db

clientes_bp = Blueprint("clientes", __name__)


@clientes_bp.route("/me", methods=["GET"])
@login_required
def me():
    """Retorna os dados do cliente atualmente autenticado."""
    if not getattr(current_user, "is_cliente", False):
        return jsonify({"erro": "Usuario autenticado nao e um cliente"}), 403
    cliente = Cliente.query.get(current_user.id_cliente)
    return jsonify(cliente.to_dict() if cliente else current_user.to_dict())


@clientes_bp.route("/", methods=["GET"])
@login_required
def listar():
    """
    Mitigação VULN-01: Exige autenticação.
    Clientes comuns acessam apenas os próprios dados.
    Vendedoras podem buscar por telefone ou listar todos.
    """
    if getattr(current_user, "is_cliente", False):
        cliente = Cliente.query.get(current_user.id_cliente)
        return jsonify(cliente.to_dict() if cliente else {})

    if not getattr(current_user, "is_vendedora", False):
        return jsonify({"erro": "Acesso negado. Perfil nao autorizado."}), 403

    telefone = request.args.get("telefone")
    if telefone:
        tel_limpo = re.sub(r"\D", "", str(telefone).strip())
        cliente = Cliente.query.filter(
            (Cliente.telefone == telefone) | (Cliente.telefone == tel_limpo)
        ).first()
        if not cliente:
            return jsonify({"erro": "Cliente nao encontrado"}), 404
        return jsonify(cliente.to_dict())

    # Vendedora ou acesso administrativo
    clientes = Cliente.query.order_by(Cliente.nome).all()
    return jsonify([c.to_dict() for c in clientes])


@clientes_bp.route("/<int:id>", methods=["GET"])
@login_required
def obter(id):
    """Mitigação BOLA/IDOR: Cliente só pode acessar seus próprios dados."""
    if getattr(current_user, "is_cliente", False):
        if current_user.id_cliente != id:
            return jsonify({"erro": "Acesso nao permitido ao perfil solicitado"}), 403

    elif not getattr(current_user, "is_vendedora", False):
        return jsonify({"erro": "Acesso negado"}), 403

    cliente = Cliente.query.get_or_404(id)
    return jsonify(cliente.to_dict())


@clientes_bp.route("/", methods=["POST"])
@login_required
def cadastrar():
    """Mitigação VULN-01 e VULN-02: Cadastro no PDV restrito a vendedora autenticada com senha segura."""
    if not getattr(current_user, "is_vendedora", False):
        return jsonify({"erro": "Acesso restrito a vendedoras"}), 403

    data = request.get_json() or {}
    nome = (data.get("nome") or "").strip()
    telefone = (data.get("telefone") or "").strip()

    if not nome or not telefone:
        return jsonify({"erro": "nome e telefone sao obrigatorios"}), 400

    tel_limpo = re.sub(r"\D", "", telefone)
    senha = data.get("senha")
    senha_gerada = False

    if not senha:
        # Gera senha segura aleatória se a vendedora não especificou no caixa
        senha = secrets.token_urlsafe(8)
        senha_gerada = True
    elif len(str(senha)) < 8 or str(senha) == "1234":
        return jsonify({"erro": "A senha deve conter no minimo 8 caracteres e nao pode ser '1234'"}), 400

    cliente = Cliente(
        nome=nome,
        telefone=tel_limpo,
        email=data.get("email"),
        endereco=data.get("endereco"),
    )
    cliente.set_senha(str(senha))

    try:
        db.session.add(cliente)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"erro": "Telefone ou email ja cadastrado"}), 409

    resp_data = cliente.to_dict()
    if senha_gerada:
        resp_data["senha_inicial"] = senha
    return jsonify(resp_data), 201
