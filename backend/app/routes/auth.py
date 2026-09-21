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
        cliente_existente = Cliente.query.filter_by(telefone=telefone_limpo).first()
        if cliente_existente:
            flash("Este telefone ja esta cadastrado. Faca login.", "warning")
            return render_template("cadastro.html", form=form)

        if email_limpo and Cliente.query.filter_by(email=email_limpo).first():
            flash("Este e-mail ja esta cadastrado. Faca login.", "warning")
            return render_template("cadastro.html", form=form)

        # Criação segura com hash PBKDF2 (padrão do Werkzeug)
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
    identificador = (data.get("email") or data.get("login") or "").strip()
    senha = str(data.get("senha", ""))

    if not identificador or not senha:
        return jsonify({"erro": "E-mail/login e senha sao obrigatorios"}), 400

    usuario = Usuario.query.filter(
        (Usuario.email == identificador) | (Usuario.login == identificador)
    ).first()

    if usuario and getattr(usuario, "is_vendedora", False):
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
    cliente = Cliente.query.filter_by(login=identificador).first()
    if tel_limpo:
        cliente = cliente or Cliente.query.filter(
            (Cliente.telefone == identificador) | (Cliente.telefone == tel_limpo)
        ).first()

    if not cliente and "@" in identificador:
        cliente = Cliente.query.filter_by(email=identificador).first()

    # Mitigação VULN-06 e Segregação de Perfis: Resposta uniforme e validação de perfil cliente
    if not cliente or not getattr(cliente, "is_cliente", False) or not cliente.verificar_senha(senha):
        return jsonify({"erro": "Telefone ou senha invalidos."}), 401

    if not getattr(cliente, "ativo", True):
        return jsonify({"erro": "Conta desativada. Entre em contato com a loja."}), 401

    login_user(cliente)
    cliente.ultimo_login = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.commit()

    precisa_trocar = bool(getattr(cliente, "precisa_trocar_senha", False))

    return jsonify({
        "mensagem": "Cadastro realizado pela equipe da loja: solicitada a troca de senha no primeiro acesso." if precisa_trocar else "Login de cliente realizado com sucesso",
        "tipo": "cliente",
        "precisa_trocar_senha": precisa_trocar,
        "cadastrado_por_vendedora": precisa_trocar,
        "redirect": "/cliente/trocar-senha" if precisa_trocar else "/bemvindo",
        "cliente": cliente.to_dict(),
    })


# ---------- LOGOUT UNIFICADO ----------
@auth_bp.route("/logout", methods=["GET", "POST"])
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


# ---------- CADASTRO INICIAL SEGURO (SETUP VENDEDORA ADMIN) ----------
def sistema_precisa_setup() -> bool:
    """Retorna True se ainda não houver nenhuma vendedora/administradora cadastrada."""
    return Usuario.query.filter(Usuario.nivel_acesso != "CLIENTE").first() is None


@auth_bp.route("/setup", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def setup():
    """Cadastro inicial seguro da Vendedora (Admin).
    Permitido estritamente quando não existe nenhuma administradora cadastrada no sistema.
    """
    from app.services.rbac import ROLE_VENDEDORA

    precisa = sistema_precisa_setup()

    if request.method == "GET":
        if not precisa:
            flash("O cadastro inicial já foi realizado. Efetue login.", "info")
            return redirect(url_for("main.index"))
        return render_template("setup.html")

    # POST
    if not precisa:
        if request.is_json:
            return jsonify({"erro": "Cadastro inicial já concluído. O sistema já possui administradora configurada."}), 403
        flash("O cadastro inicial já foi realizado.", "warning")
        return redirect(url_for("main.index"))

    data = request.get_json(silent=True) if request.is_json else request.form
    nome = str(data.get("nome", "")).strip()
    login = str(data.get("login", "")).strip().lower()
    email = str(data.get("email", "")).strip().lower()
    senha = str(data.get("senha", ""))
    confirmar_senha = str(data.get("confirmar_senha", ""))

    erros = []
    if len(nome) < 3:
        erros.append("O nome deve ter pelo menos 3 caracteres.")
    if not re.match(r"^[a-zA-Z0-9_.@-]{3,50}$", login):
        erros.append("O login deve ter entre 3 e 50 caracteres alfanuméricos.")
    if not email or "@" not in email:
        erros.append("Informe um e-mail válido.")
    if senha != confirmar_senha:
        erros.append("A confirmação de senha não confere.")

    valida_senha, msg_senha = validar_politica_senha_admin(senha)
    if not valida_senha:
        erros.append(msg_senha)

    if erros:
        msg_total = " ".join(erros)
        if request.is_json:
            return jsonify({"erro": msg_total}), 400
        for err in erros:
            flash(err, "danger")
        return render_template("setup.html", nome=nome, login=login, email=email), 400

    # Verifica duplicidade
    if Usuario.query.filter((Usuario.login == login) | (Usuario.email == email)).first():
        msg_dup = "Já existe um usuário com esse login ou e-mail."
        if request.is_json:
            return jsonify({"erro": msg_dup}), 409
        flash(msg_dup, "danger")
        return render_template("setup.html", nome=nome, login=login, email=email), 409

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

        registrar_auditoria(
            acao="CADASTRO_INICIAL_VENDEDORA_ADMIN",
            entidade="usuario",
            entidade_id=vendedora.id_usuario,
            detalhes={"login": login, "email": email, "cargo": ROLE_VENDEDORA, "metodo": "setup_seguro"},
            usuario_id=vendedora.id_usuario,
        )
        db.session.commit()

        login_user(vendedora)

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
        return render_template("setup.html", nome=nome, login=login, email=email), 500
