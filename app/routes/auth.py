from flask import Blueprint, jsonify, request
from flask_login import login_user, logout_user, login_required, current_user
from app.models.usuario import Usuario

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    # Aceita e-mail OU login (o front FideliZa usa e-mail)
    identificador = data.get("email") or data.get("login")
    senha = data.get("senha", "")

    usuario = Usuario.query.filter(
        (Usuario.email == identificador) | (Usuario.login == identificador)
    ).first()

    if usuario and usuario.verificar_senha(senha):
        login_user(usuario)
        return jsonify({"mensagem": "Login realizado", "usuario": usuario.to_dict()})
    return jsonify({"erro": "Credenciais invalidas"}), 401


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return jsonify({"mensagem": "Logout realizado"})


@auth_bp.route("/me", methods=["GET"])
@login_required
def me():
    return jsonify(current_user.to_dict())
