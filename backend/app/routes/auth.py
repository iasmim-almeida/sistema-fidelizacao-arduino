import hmac
import logging
import re
import threading
from datetime import datetime, timezone
from functools import wraps
from flask import Blueprint, current_app, jsonify, request, redirect, url_for, render_template, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.extensions import db, limiter, csrf
from app.forms import CadastroClienteForm, validar_politica_senha_admin

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__)
_SETUP_LOCK = threading.Lock()


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
        if getattr(current_user, "precisa_trocar_senha", False):
            rotas_permitidas = ("main.cliente_trocar_senha", "main.trocar_senha", "clientes.alterar_minha_senha", "auth.logout")
            if request.endpoint not in rotas_permitidas:
                if request.is_json or request.path.startswith("/api"):
                    return jsonify({
                        "erro": "Troca de senha obrigatória no primeiro acesso.",
                        "precisa_trocar_senha": True,
                        "redirect": url_for("main.cliente_trocar_senha"),
                    }), 403
                return redirect(url_for("main.cliente_trocar_senha"))
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
        email_limpo = form.email.data.strip().lower() if form.email.data else None
        senha = form.senha.data

        # Validação extra de telefone duplicado
        cliente_existente = Cliente.query.filter_by(telefone=telefone_limpo, nivel_acesso="CLIENTE").first()
        if cliente_existente:
            flash("Este telefone ja esta cadastrado. Faca login.", "warning")
            return render_template("cadastro.html", form=form)

        if email_limpo and Cliente.query.filter_by(email=email_limpo, nivel_acesso="CLIENTE").first():
            flash("Este e-mail ja esta cadastrado. Faca login.", "warning")
            return render_template("cadastro.html", form=form)

        # O modelo usa o algoritmo de hash de senha seguro fornecido pelo Werkzeug.
        cliente = Cliente(
            nome=form.nome.data.strip(),
            telefone=telefone_limpo,
            login=telefone_limpo,
            email=email_limpo,
            pontos_acumulados=0,
            ativo=True,
            cargo="cliente",
            nivel_acesso="CLIENTE",
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
    identificador = (data.get("identificador") or data.get("email") or data.get("login") or "").strip()
    senha = str(data.get("senha", ""))

    if not identificador or not senha:
        return jsonify({"erro": "E-mail/login e senha sao obrigatorios"}), 400

    usuario = Usuario.query.filter(
        (Usuario.email == identificador) | (Usuario.login == identificador)
    ).first()

    if usuario and getattr(usuario, "is_vendedora", False):
        if not getattr(usuario, "ativo", True):
            logger.warning("Login administrativo recusado para conta inativa: usuario_id=%s", usuario.id_usuario)
            return jsonify({"erro": "Conta inativa. Entre em contato com a administração."}), 401

        if usuario.verificar_senha(senha):
            usuario.ultimo_login = datetime.now(timezone.utc).replace(tzinfo=None)
            db.session.commit()

            login_user(usuario)
            logger.info("Login administrativo concluído: usuario_id=%s", usuario.id_usuario)
            return jsonify({
                "mensagem": "Login de vendedora realizado com sucesso",
                "tipo": "vendedora",
                "redirect": "/dashboard",
                "usuario": usuario.to_dict(),
            })

    logger.warning("Tentativa de login administrativo recusada: ip=%s", request.remote_addr)
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
    cliente = Cliente.query.filter_by(login=identificador, nivel_acesso="CLIENTE").first()
    if tel_limpo:
        cliente = cliente or Cliente.query.filter(
            Cliente.nivel_acesso == "CLIENTE",
            (Cliente.telefone == identificador) | (Cliente.telefone == tel_limpo)
        ).first()

    if not cliente and "@" in identificador:
        cliente = Cliente.query.filter_by(email=identificador, nivel_acesso="CLIENTE").first()

    # A resposta uniforme evita enumeração de contas.
    if not cliente or not getattr(cliente, "is_cliente", False) or not cliente.verificar_senha(senha):
        return jsonify({"erro": "Telefone ou senha invalidos."}), 401

    if not getattr(cliente, "ativo", True):
        return jsonify({"erro": "Conta desativada. Entre em contato com a loja."}), 401

    login_user(cliente)
    cliente.ultimo_login = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.commit()

    precisa_trocar = bool(getattr(cliente, "precisa_trocar_senha", False))

    return jsonify({
        "mensagem": "Cadastro administrativo: solicitada a troca de senha no primeiro acesso." if precisa_trocar else "Login de cliente realizado com sucesso",
        "tipo": "cliente",
        "precisa_trocar_senha": precisa_trocar,
        "cadastrado_por_vendedora": precisa_trocar,
        "redirect": "/cliente/trocar-senha" if precisa_trocar else "/bemvindo",
        "cliente": cliente.to_dict(),
    })


# ---------- LOGOUT UNIFICADO ----------
@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    usuario_id = current_user.get_id()
    logout_user()
    session.clear()
    logger.info("Sessão encerrada: usuario=%s", usuario_id)
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


# ---------- CADASTRO INICIAL SEGURO (SETUP VENDEDORA ADMIN) ----------
def sistema_precisa_setup() -> bool:
    """Retorna True se ainda não houver nenhuma vendedora/administradora cadastrada."""
    return Usuario.query.filter(Usuario.nivel_acesso != "CLIENTE").first() is None


def obter_token_setup_esperado() -> str:
    """Retorna o token de bootstrap se configurado na variável de ambiente INITIAL_SETUP_TOKEN."""
    return str(current_app.config.get("INITIAL_SETUP_TOKEN") or "").strip()


def validar_setup_token(token_informado: str | None) -> tuple[bool, str | None]:
    """Valida o token de setup e falha de forma fechada quando obrigatório."""
    token_esperado = obter_token_setup_esperado()
    if not token_esperado:
        if current_app.config.get("REQUIRE_INITIAL_SETUP_TOKEN", False):
            return False, "Setup indisponível: INITIAL_SETUP_TOKEN não está configurado."
        return True, None
    if not token_informado or not hmac.compare_digest(token_informado.strip(), token_esperado):
        return False, "Token de autorização de setup inválido ou ausente."
    return True, None


@auth_bp.route("/setup", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def setup():
    """Cadastro inicial seguro da Vendedora (Admin).
    Permitido estritamente quando não existe nenhuma administradora cadastrada no sistema.
    """
    from app.services.rbac import ROLE_VENDEDORA

    precisa = sistema_precisa_setup()
    token_esperado = obter_token_setup_esperado()
    token_obrigatorio = current_app.config.get("REQUIRE_INITIAL_SETUP_TOKEN", False)
    setup_token_required = bool(token_esperado) or token_obrigatorio
    # Token de setup NUNCA aceito via query string para evitar vazamento em logs, Referer e historico do navegador

    if request.method == "GET":
        if not precisa:
            flash("O cadastro inicial já foi realizado. Efetue login.", "info")
            return redirect(url_for("main.index"))
        if token_obrigatorio and not token_esperado:
            logger.error("Setup bloqueado: INITIAL_SETUP_TOKEN ausente em ambiente protegido")
            return "Setup indisponível por configuração de segurança.", 503
        return render_template(
            "setup.html",
            setup_token_required=setup_token_required,
            setup_token="",
        )

    # POST
    if not precisa:
        if request.is_json:
            return jsonify({"erro": "Cadastro inicial já concluído. O sistema já possui administradora configurada."}), 403
        flash("O cadastro inicial já foi realizado. Efetue login.", "warning")
        return redirect(url_for("main.index"))

    if token_obrigatorio and not token_esperado:
        logger.error("Setup bloqueado: INITIAL_SETUP_TOKEN ausente em ambiente protegido")
        return jsonify({"erro": "Setup indisponível por configuração de segurança."}), 503

    data = request.get_json(silent=True) if request.is_json else request.form
    nome = " ".join(str(data.get("nome", "")).strip().split())
    login = str(data.get("login", "")).strip().lower()
    email = str(data.get("email", "")).strip().lower()
    senha = str(data.get("senha", ""))
    confirmar_senha = str(data.get("confirmar_senha", ""))
    token_informado = str(data.get("setup_token") or "").strip()

    erros = []
    if len(nome) < 3:
        erros.append("O nome deve ter pelo menos 3 caracteres.")
    if len(nome) > 100:
        erros.append("O nome deve conter no máximo 100 caracteres.")
    if not re.match(r"^[a-zA-Z0-9_.@-]{3,50}$", login):
        erros.append("O login deve ter entre 3 e 50 caracteres alfanuméricos.")
    if not email or len(email) > 100 or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        erros.append("Informe um e-mail válido com até 100 caracteres.")
    if senha != confirmar_senha:
        erros.append("A confirmação de senha não confere.")

    valida_tok, msg_tok = validar_setup_token(token_informado)
    if not valida_tok:
        if request.is_json:
            return jsonify({"erro": msg_tok}), 403
        flash(msg_tok, "danger")
        return render_template(
            "setup.html",
            nome=nome,
            login=login,
            email=email,
            setup_token_required=setup_token_required,
            setup_token=token_informado,
        ), 403

    valida_senha, msg_senha = validar_politica_senha_admin(senha)
    if not valida_senha:
        erros.append(msg_senha)

    if erros:
        msg_total = " ".join(erros)
        if request.is_json:
            return jsonify({"erro": msg_total}), 400
        for err in erros:
            flash(err, "danger")
        return render_template(
            "setup.html",
            nome=nome,
            login=login,
            email=email,
            setup_token_required=setup_token_required,
            setup_token=token_informado,
        ), 400

    # Verifica duplicidade
    if Usuario.query.filter((Usuario.login == login) | (Usuario.email == email)).first():
        msg_dup = "Já existe um usuário com esse login ou e-mail."
        if request.is_json:
            return jsonify({"erro": msg_dup}), 409
        flash(msg_dup, "danger")
        return render_template(
            "setup.html",
            nome=nome,
            login=login,
            email=email,
            setup_token_required=setup_token_required,
            setup_token=token_informado,
        ), 409

    # Proteção de Concorrência (Race Condition): Serializa em threads e em PostgreSQL (advisory lock)
    with _SETUP_LOCK:
        try:
            if db.engine.dialect.name == "postgresql":
                db.session.execute(db.text("SELECT pg_advisory_xact_lock(742918)"))
        except Exception as e:
            logger.warning("Falha ao invocar pg_advisory_xact_lock: %s", e)

        # Re-verifica atomicamente se outro processo ou thread concluiu o setup
        if not sistema_precisa_setup():
            db.session.rollback()
            msg_travado = "Cadastro inicial já concluído. O sistema já possui administradora configurada."
            if request.is_json:
                return jsonify({"erro": msg_travado}), 403
            flash(msg_travado, "warning")
            return redirect(url_for("main.index"))

        vendedora = Usuario(
            nome=nome,
            login=login,
            email=email,
            cargo=ROLE_VENDEDORA,
            nivel_acesso="ADMIN",
            ativo=True,
            precisa_trocar_senha=False,
        )
        vendedora.set_senha(senha)

        try:
            db.session.add(vendedora)
            db.session.commit()

            login_user(vendedora)
            logger.info("Cadastro inicial concluído: usuario_id=%s", vendedora.id_usuario)

            if request.is_json:
                return jsonify({
                    "mensagem": "Cadastro inicial da Vendedora (Admin) realizado com sucesso!",
                    "redirect": "/dashboard",
                    "usuario": vendedora.to_dict(),
                }), 201

            flash("Cadastro inicial concluído com sucesso! Bem-vinda ao IT Clube.", "success")
            return redirect(url_for("main.dashboard"))
        except Exception:
            db.session.rollback()
            logger.exception("Falha no cadastro inicial seguro")
            if request.is_json:
                return jsonify({"erro": "Erro interno ao processar cadastro inicial."}), 500
            flash("Erro ao salvar cadastro inicial. Tente novamente.", "danger")
            return render_template(
                "setup.html",
                nome=nome,
                login=login,
                email=email,
                setup_token_required=setup_token_required,
                setup_token=token_informado,
            ), 500
