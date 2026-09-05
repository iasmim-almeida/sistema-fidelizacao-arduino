import logging
import re
from datetime import datetime, timezone
from functools import wraps
from flask import Blueprint, jsonify, request, redirect, url_for, render_template, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.extensions import db, limiter, csrf
from app.forms import CadastroClienteForm, validar_politica_senha_admin
from app.services.auditoria import registrar_auditoria

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__)


def vendedora_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.is_json or request.path.startswith("/api") or request.path.startswith("/auth"):
                return jsonify({"erro": "Nao autenticado. Faca login como vendedora."}), 401
            return redirect(url_for("main.index"))
        if not getattr(current_user, "is_vendedora", False):
            if request.is_json or request.path.startswith("/api") or request.path.startswith("/auth"):
                return jsonify({"erro": "Acesso negado. Requer perfil de vendedora/gestora."}), 403
            return redirect(url_for("main.bemvindo"))
        if not getattr(current_user, "ativo", True):
            if request.is_json or request.path.startswith("/api") or request.path.startswith("/auth"):
                return jsonify({"erro": "Conta inativa. Acesso negado."}), 403
            return redirect(url_for("main.index"))
        return f(*args, **kwargs)
    return decorated_function


def cliente_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.is_json or request.path.startswith("/api") or request.path.startswith("/auth"):
                return jsonify({"erro": "Nao autenticado. Faca login como cliente."}), 401
            return redirect(url_for("main.index"))
        if not getattr(current_user, "is_cliente", False):
            if request.is_json or request.path.startswith("/api") or request.path.startswith("/auth"):
                return jsonify({"erro": "Acesso negado. Requer perfil de cliente."}), 403
            return redirect(url_for("main.dashboard"))
        if not getattr(current_user, "ativo", True):
            if request.is_json or request.path.startswith("/api") or request.path.startswith("/auth"):
                return jsonify({"erro": "Conta desativada. Acesso negado."}), 403
            return redirect(url_for("main.index"))
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

        # Validação extra de telefone duplicado
        cliente_existente = Cliente.query.filter_by(telefone=telefone_limpo).first()
        if cliente_existente:
            flash("Este telefone ja esta cadastrado. Faca login.", "warning")
            return render_template("cadastro.html", form=form)

        # Criação segura com hash PBKDF2 (padrão do Werkzeug)
        cliente = Cliente(
            nome=form.nome.data.strip(),
            telefone=telefone_limpo,
            pontos_acumulados=0,
            ativo=True,
        )
        cliente.set_senha(senha)

        try:
            db.session.add(cliente)
            db.session.commit()
            logger.info("Novo cliente cadastrado com sucesso via formulario web: id=%s", cliente.id_cliente)
            flash("Cadastro realizado com sucesso! Voce ja pode fazer login.", "success")
            return redirect(url_for("main.index"))
        except Exception:
            db.session.rollback()
            logger.exception("Erro ao persistir novo cliente no banco.")
            flash("Ocorreu um erro ao salvar o cadastro. Tente novamente.", "danger")

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

    if usuario:
        if not getattr(usuario, "ativo", True):
            registrar_auditoria(
                acao="LOGIN_FALHA",
                entidade="usuario",
                entidade_id=usuario.id_usuario,
                detalhes={"motivo": "conta_inativa", "login": identificador},
            )
            db.session.commit()
            return jsonify({"erro": "Conta inativa. Entre em contato com a administração."}), 401

        if usuario.verificar_senha(senha):
            usuario.ultimo_login = datetime.now(timezone.utc).replace(tzinfo=None)
            db.session.commit()

            registrar_auditoria(
                acao="LOGIN_SUCESSO",
                entidade="usuario",
                entidade_id=usuario.id_usuario,
                detalhes={"login": usuario.login, "cargo": usuario.cargo},
            )
            db.session.commit()

            login_user(usuario)
            return jsonify({
                "mensagem": "Login de vendedora realizado com sucesso",
                "tipo": "vendedora",
                "redirect": "/dashboard",
                "usuario": usuario.to_dict(),
            })

    registrar_auditoria(
        acao="LOGIN_FALHA",
        entidade="usuario",
        entidade_id=None,
        detalhes={"login_tentado": identificador},
    )
    db.session.commit()
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

    if not getattr(cliente, "ativo", True):
        return jsonify({"erro": "Conta desativada. Entre em contato com a loja."}), 401

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
    if current_user.is_authenticated:
        registrar_auditoria(
            acao="LOGOUT",
            entidade="usuario" if getattr(current_user, "is_vendedora", False) else "cliente",
            entidade_id=current_user.get_id(),
        )
        db.session.commit()

    logout_user()
    session.clear()
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


# ---------- TROCA DE SENHA DO ADMINISTRADOR ----------
@auth_bp.route("/alterar-senha", methods=["POST"])
@auth_bp.route("/vendedora/alterar-senha", methods=["POST"])
@vendedora_required
@limiter.limit("5 per minute; 15 per hour")
def alterar_senha_admin():
    data = request.get_json(silent=True) if request.is_json else request.form.to_dict()
    if not isinstance(data, dict):
        return jsonify({"erro": "Formato de dados invalido. Envie um JSON ou formulario valido."}), 400

    senha_atual = str(data.get("senha_atual") or "").strip()
    nova_senha = str(data.get("nova_senha") or "").strip()
    confirmar_nova_senha = str(data.get("confirmar_nova_senha") or "").strip()

    if not senha_atual or not nova_senha or not confirmar_nova_senha:
        return jsonify({"erro": "Senha atual, nova senha e confirmacao sao campos obrigatorios."}), 400

    user = current_user._get_current_object()
    user_id = user.id_usuario
    user_login = user.login

    # 1. Validação da senha atual
    if not user.verificar_senha(senha_atual):
        logger.warning(
            "Tentativa de troca de senha com senha atual incorreta para usuario_id=%s",
            user_id
        )
        return jsonify({"erro": "A senha atual informada esta incorreta."}), 400

    # 2. Prevenção de reutilização da senha atual
    if user.verificar_senha(nova_senha):
        return jsonify({"erro": "A nova senha deve ser diferente da senha atual."}), 400

    # 3. Validação de confirmação
    if nova_senha != confirmar_nova_senha:
        return jsonify({"erro": "A confirmacao da nova senha nao confere."}), 400

    # 4. Política mínima de complexidade de senha
    valida, motivo = validar_politica_senha_admin(nova_senha)
    if not valida:
        return jsonify({"erro": motivo}), 400

    try:
        user.set_senha(nova_senha)
        user.precisa_trocar_senha = False
        db.session.commit()

        session.modified = True

        registrar_auditoria(
            acao="ALTERAR_SENHA",
            entidade="usuario",
            entidade_id=user_id,
            detalhes={"login": user_login},
        )
        db.session.commit()

        logger.info(
            "Senha de administrador alterada com sucesso. usuario_id=%s, login=%s",
            user_id,
            user_login
        )

        return jsonify({
            "status": "sucesso",
            "mensagem": "Senha do administrador alterada com sucesso."
        }), 200

    except Exception:
        db.session.rollback()
        logger.exception("Falha transacional ao atualizar senha de administrador")
        return jsonify({"erro": "Ocorreu um erro interno ao atualizar a senha. Tente novamente."}), 500
