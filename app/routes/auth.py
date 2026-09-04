import re
from functools import wraps
from flask import Blueprint, jsonify, request, redirect, url_for, render_template, flash
from flask_login import login_user, logout_user, login_required, current_user
from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.extensions import db, limiter, csrf
from app.forms import CadastroClienteForm

auth_bp = Blueprint("auth", __name__)


def vendedora_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.path.startswith("/api") or request.path.startswith("/auth"):
                return jsonify({"erro": "Nao autenticado. Faca login como vendedora."}), 401
            return redirect(url_for("main.index"))
        if not getattr(current_user, "is_vendedora", False):
            if request.path.startswith("/api"):
                return jsonify({"erro": "Acesso negado. Requer perfil de vendedora/gestora."}), 403
            return redirect(url_for("main.bemvindo"))
        return f(*args, **kwargs)
    return decorated_function


def cliente_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.path.startswith("/api") or request.path.startswith("/auth"):
                return jsonify({"erro": "Nao autenticado. Faca login como cliente."}), 401
            return redirect(url_for("main.index"))
        if not getattr(current_user, "is_cliente", False):
            if request.path.startswith("/api"):
                return jsonify({"erro": "Acesso negado. Requer perfil de cliente."}), 403
            return redirect(url_for("main.dashboard"))
        return f(*args, **kwargs)
    return decorated_function


# ---------- CADASTRO PÚBLICO DE CLIENTES (WEB) ----------
@auth_bp.route("/cadastro", methods=["GET", "POST"])
@limiter.limit("5 per minute; 30 per hour")
def cadastrar_cliente_web():
    """Rota segura de auto-cadastro para clientes finais."""
    if current_user.is_authenticated:
        if getattr(current_user, "is_vendedora", False):
            return redirect(url_for("main.dashboard"))
        return redirect(url_for("main.bemvindo"))

    form = CadastroClienteForm()

    if form.validate_on_submit():
        telefone_limpo = re.sub(r"\D", "", form.telefone.data.strip())
        senha = form.senha.data

        # Mitigação VULN-02: Rejeição de senhas nulas, fracas ou o padrão "1234"
        if not senha or senha == "1234" or len(senha) < 8:
            flash("A senha deve possuir ao menos 8 caracteres e nao pode ser '1234'.", "error")
            return render_template("cadastro.html", form=form)

        novo_cliente = Cliente(
            nome=form.nome.data.strip(),
            telefone=telefone_limpo,
            pontos_acumulados=0,
        )
        # Mitigação VULN-02: Gera hash forte Werkzeug/pbkdf2
        novo_cliente.set_senha(senha)

        try:
            db.session.add(novo_cliente)
            db.session.commit()
            flash("Cadastro realizado com sucesso! Faca login para acessar seus pontos.", "success")
            return redirect(url_for("main.index"))
        except Exception:
            db.session.rollback()
            flash("Ocorreu um erro ao salvar o cadastro. Verifique se o telefone ja esta cadastrado.", "error")

    return render_template("cadastro.html", form=form)


# ---------- LOGIN DA VENDEDORA (ADMIN) ----------
@auth_bp.route("/login", methods=["POST"])
@auth_bp.route("/vendedora/login", methods=["POST"])
@csrf.exempt
@limiter.limit("10 per minute")
def login_vendedora():
    data = request.get_json() or {}
    identificador = (data.get("email") or data.get("login") or "").strip()
    senha = str(data.get("senha", ""))

    if not identificador or not senha:
        return jsonify({"erro": "E-mail/login e senha sao obrigatorios"}), 400

    usuario = Usuario.query.filter(
        (Usuario.email == identificador) | (Usuario.login == identificador)
    ).first()

    if usuario and usuario.verificar_senha(senha):
        login_user(usuario)
        return jsonify({
            "mensagem": "Login de vendedora realizado com sucesso",
            "tipo": "vendedora",
            "redirect": "/dashboard",
            "usuario": usuario.to_dict(),
        })

    return jsonify({"erro": "Credenciais de vendedora invalidas"}), 401


# ---------- LOGIN DO CLIENTE ----------
@auth_bp.route("/cliente/login", methods=["POST"])
@csrf.exempt
@limiter.limit("10 per minute")
def login_cliente():
    data = request.get_json() or {}
    identificador = str(data.get("telefone") or data.get("email") or data.get("login") or "").strip()
    senha = str(data.get("senha", "")).strip()

    if not identificador or not senha:
        return jsonify({"erro": "Telefone/e-mail e senha sao obrigatorios"}), 400

    # Limpeza para buscar por telefone puro (somente números) ou correspondência direta
    tel_limpo = re.sub(r"\D", "", identificador)

    cliente = None
    if tel_limpo:
        cliente = Cliente.query.filter(
            (Cliente.telefone == identificador) | (Cliente.telefone == tel_limpo)
        ).first()

    if not cliente and "@" in identificador:
        cliente = Cliente.query.filter_by(email=identificador).first()

    # Mitigação VULN-06: Resposta uniforme para impedir enumeração de usuários (CWE-204)
    if not cliente or not cliente.verificar_senha(senha):
        return jsonify({"erro": "Telefone ou senha invalidos."}), 401

    login_user(cliente)
    return jsonify({
        "mensagem": "Login de cliente realizado com sucesso",
        "tipo": "cliente",
        "redirect": "/bemvindo",
        "cliente": cliente.to_dict(),
    })


# ---------- LOGOUT UNIFICADO ----------
@auth_bp.route("/logout", methods=["POST"])
@csrf.exempt
@login_required
def logout():
    logout_user()
    if request.is_json or request.path.startswith("/api") or request.path.startswith("/auth"):
        return jsonify({"mensagem": "Logout realizado com sucesso", "redirect": "/"})
    return redirect(url_for("main.index"))


# ---------- DADOS DA SESSÃO ATUAL ----------
@auth_bp.route("/me", methods=["GET"])
def me():
    if not current_user.is_authenticated:
        return jsonify({"autenticado": False, "erro": "Nenhum usuario logado"}), 401
    return jsonify({
        "autenticado": True,
        "tipo": getattr(current_user, "tipo", "desconhecido"),
        "usuario": current_user.to_dict(),
    })
