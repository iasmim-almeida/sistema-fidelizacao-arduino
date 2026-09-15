import re
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError
from app.extensions import db
from app.models.usuario import Usuario
from app.services.rbac import (
    permissao_requerida,
    normalizar_cargo,
    pode_gerenciar_cargo,
    ROLE_PROPRIETARIO,
    ROLE_GERENTE,
    ROLE_VENDEDOR,
    ROLES_VALIDOS,
)
from app.services.auditoria import registrar_auditoria
from app.forms import validar_politica_senha_admin

funcionarios_bp = Blueprint("funcionarios", __name__)


@funcionarios_bp.route("/", methods=["GET"])
@login_required
@permissao_requerida("funcionarios.visualizar")
def listar():
    """Lista todos os funcionários cadastrados no sistema."""
    query = Usuario.query

    status = request.args.get("status")
    if status == "ativo":
        query = query.filter_by(ativo=True)
    elif status == "inativo":
        query = query.filter_by(ativo=False)

    cargo = request.args.get("cargo")
    if cargo:
        cargo_norm = normalizar_cargo(cargo)
        query = query.filter(
            (Usuario.cargo == cargo_norm) | (Usuario.nivel_acesso == cargo_norm)
        )

    funcionarios = query.order_by(Usuario.nome.asc()).all()
    return jsonify([f.to_dict() for f in funcionarios])


@funcionarios_bp.route("/<int:id_usuario>", methods=["GET"])
@login_required
@permissao_requerida("funcionarios.visualizar")
def obter(id_usuario: int):
    """Consulta detalhes de um funcionário específico."""
    funcionario = db.session.get(Usuario, id_usuario)
    if not funcionario:
        return jsonify({"erro": "Funcionário não encontrado."}), 404
    return jsonify(funcionario.to_dict())


@funcionarios_bp.route("/", methods=["POST"])
@login_required
@permissao_requerida("funcionarios.criar")
def criar():
    """Cadastra um novo funcionário com senha segura e validação de hierarquia."""
    data = request.get_json(silent=True) or {}

    nome = str(data.get("nome", "")).strip()
    login = str(data.get("login", "")).strip().lower()
    email = str(data.get("email", "")).strip().lower() or None
    senha = str(data.get("senha", ""))
    cargo_solicitado = normalizar_cargo(data.get("cargo", ROLE_VENDEDOR))

    if len(nome) < 3:
        return jsonify({"erro": "O nome deve conter ao menos 3 caracteres."}), 400

    if not re.match(r"^[a-zA-Z0-9_.@-]{3,50}$", login):
        return jsonify({"erro": "O login deve conter entre 3 e 50 caracteres alfanuméricos."}), 400

    if cargo_solicitado not in ROLES_VALIDOS:
        return jsonify({"erro": f"Cargo inválido. Cargos permitidos: {', '.join(ROLES_VALIDOS)}."}), 400

    # Prevenção de Privilege Escalation: operador não pode criar usuário com cargo superior ou igual
    cargo_operador = getattr(current_user, "cargo", None) or getattr(current_user, "nivel_acesso", None)
    if not pode_gerenciar_cargo(cargo_operador, cargo_solicitado):
        return jsonify({"erro": f"Você não possui permissão para criar usuários com o cargo '{cargo_solicitado}'."}), 403

    # Validação rigorosa de senha
    valida, motivo = validar_politica_senha_admin(senha)
    if not valida:
        return jsonify({"erro": motivo}), 400

    # Verifica duplicidades
    if Usuario.query.filter_by(login=login).first():
        return jsonify({"erro": f"Já existe um funcionário com o login '{login}'."}), 409

    if email and Usuario.query.filter_by(email=email).first():
        return jsonify({"erro": f"Já existe um funcionário com o e-mail '{email}'."}), 409

    novo = Usuario(
        nome=nome,
        login=login,
        email=email,
        cargo=cargo_solicitado,
        nivel_acesso="gestor" if cargo_solicitado == ROLE_PROPRIETARIO else cargo_solicitado,
        ativo=True,
    )
    novo.set_senha(senha)

    try:
        db.session.add(novo)
        db.session.commit()

        registrar_auditoria(
            acao="CRIAR_FUNCIONARIO",
            entidade="usuario",
            entidade_id=novo.id_usuario,
            detalhes={"nome": nome, "login": login, "cargo": cargo_solicitado},
        )
        db.session.commit()

        return jsonify({
            "mensagem": "Funcionário cadastrado com sucesso.",
            "funcionario": novo.to_dict()
        }), 201
    except IntegrityError:
        db.session.rollback()
        return jsonify({"erro": "Conflito ao salvar funcionário no banco."}), 409
    except Exception:
        db.session.rollback()
        return jsonify({"erro": "Erro interno ao cadastrar funcionário."}), 500


@funcionarios_bp.route("/<int:id_usuario>", methods=["PUT", "PATCH"])
@login_required
@permissao_requerida("funcionarios.editar")
def editar(id_usuario: int):
    """Atualiza dados cadastrais ou cargo de um funcionário."""
    funcionario = db.session.get(Usuario, id_usuario)
    if not funcionario:
        return jsonify({"erro": "Funcionário não encontrado."}), 404

    data = request.get_json(silent=True) or {}
    cargo_operador = getattr(current_user, "cargo", None) or getattr(current_user, "nivel_acesso", None)

    # Impede edição de usuário com cargo superior (a menos que seja o próprio proprietário)
    if not pode_gerenciar_cargo(cargo_operador, funcionario.cargo) and current_user.id_usuario != id_usuario:
        return jsonify({"erro": "Você não tem permissão para editar este funcionário."}), 403

    alteracoes = {}

    if "nome" in data:
        novo_nome = str(data["nome"]).strip()
        if len(novo_nome) < 3:
            return jsonify({"erro": "O nome deve conter ao menos 3 caracteres."}), 400
        alteracoes["nome_anterior"] = funcionario.nome
        funcionario.nome = novo_nome
        alteracoes["nome_novo"] = novo_nome

    if "email" in data:
        novo_email = str(data["email"]).strip().lower() or None
        if novo_email and novo_email != funcionario.email:
            if Usuario.query.filter(Usuario.email == novo_email, Usuario.id_usuario != id_usuario).first():
                return jsonify({"erro": f"E-mail '{novo_email}' já está em uso."}), 409
        alteracoes["email_anterior"] = funcionario.email
        funcionario.email = novo_email
        alteracoes["email_novo"] = novo_email

    if "cargo" in data:
        novo_cargo = normalizar_cargo(data["cargo"])
        if novo_cargo not in ROLES_VALIDOS:
            return jsonify({"erro": f"Cargo inválido: '{data['cargo']}'."}), 400

        # Usuário não pode alterar o próprio cargo
        if current_user.id_usuario == id_usuario:
            return jsonify({"erro": "Não é permitido alterar o próprio cargo."}), 403

        # Exige permissão específica para alterar cargo
        if not current_user.tem_permissao("funcionarios.alterar_permissao"):
            return jsonify({"erro": "Você não possui permissão para alterar cargos."}), 403

        if not pode_gerenciar_cargo(cargo_operador, novo_cargo):
            return jsonify({"erro": f"Você não pode promover para o cargo '{novo_cargo}'."}), 403

        alteracoes["cargo_anterior"] = funcionario.cargo
        funcionario.cargo = novo_cargo
        funcionario.nivel_acesso = "gestor" if novo_cargo == ROLE_PROPRIETARIO else novo_cargo
        alteracoes["cargo_novo"] = novo_cargo

    try:
        db.session.commit()
        registrar_auditoria(
            acao="EDITAR_FUNCIONARIO",
            entidade="usuario",
            entidade_id=funcionario.id_usuario,
            detalhes=alteracoes,
        )
        db.session.commit()
        return jsonify({
            "mensagem": "Funcionário atualizado com sucesso.",
            "funcionario": funcionario.to_dict()
        })
    except Exception:
        db.session.rollback()
        return jsonify({"erro": "Erro ao atualizar funcionário."}), 500


@funcionarios_bp.route("/<int:id_usuario>/status", methods=["POST"])
@login_required
@permissao_requerida("funcionarios.desativar")
def alterar_status(id_usuario: int):
    """Ativa ou desativa um funcionário (soft disable)."""
    funcionario = db.session.get(Usuario, id_usuario)
    if not funcionario:
        return jsonify({"erro": "Funcionário não encontrado."}), 404

    # Usuário não pode desativar a própria conta
    if current_user.id_usuario == id_usuario:
        return jsonify({"erro": "Você não pode desativar sua própria conta."}), 400

    data = request.get_json(silent=True) or {}
    novo_status = bool(data.get("ativo", not funcionario.ativo))

    # Protege contra desativação do último proprietário ativo
    if not novo_status and funcionario.is_proprietario:
        proprietarios_ativos = Usuario.query.filter(
            (Usuario.cargo == ROLE_PROPRIETARIO) | (Usuario.nivel_acesso == "gestor"),
            Usuario.ativo == True,
            Usuario.id_usuario != id_usuario
        ).count()
        if proprietarios_ativos == 0:
            return jsonify({"erro": "Não é possível desativar o único proprietário/administrador ativo do sistema."}), 400

    cargo_operador = getattr(current_user, "cargo", None) or getattr(current_user, "nivel_acesso", None)
    if not pode_gerenciar_cargo(cargo_operador, funcionario.cargo):
        return jsonify({"erro": "Você não possui permissão para alterar o status deste funcionário."}), 403

    funcionario.ativo = novo_status
    acao_auditoria = "ATIVAR_FUNCIONARIO" if novo_status else "DESATIVAR_FUNCIONARIO"

    try:
        db.session.commit()
        registrar_auditoria(
            acao=acao_auditoria,
            entidade="usuario",
            entidade_id=funcionario.id_usuario,
            detalhes={"status_anterior": not novo_status, "novo_status": novo_status}
        )
        db.session.commit()
        return jsonify({
            "mensagem": f"Funcionário {'ativado' if novo_status else 'desativado'} com sucesso.",
            "funcionario": funcionario.to_dict()
        })
    except Exception:
        db.session.rollback()
        return jsonify({"erro": "Erro ao alterar status do funcionário."}), 500


@funcionarios_bp.route("/<int:id_usuario>/reset-senha", methods=["POST"])
@login_required
@permissao_requerida("funcionarios.editar")
def reset_senha(id_usuario: int):
    """Redefine a senha de um funcionário por um administrador."""
    funcionario = db.session.get(Usuario, id_usuario)
    if not funcionario:
        return jsonify({"erro": "Funcionário não encontrado."}), 404

    cargo_operador = getattr(current_user, "cargo", None) or getattr(current_user, "nivel_acesso", None)
    if not pode_gerenciar_cargo(cargo_operador, funcionario.cargo) and current_user.id_usuario != id_usuario:
        return jsonify({"erro": "Você não possui permissão para redefinir a senha deste funcionário."}), 403

    data = request.get_json(silent=True) or {}
    nova_senha = str(data.get("nova_senha", ""))

    valida, motivo = validar_politica_senha_admin(nova_senha)
    if not valida:
        return jsonify({"erro": motivo}), 400

    funcionario.set_senha(nova_senha)
    funcionario.precisa_trocar_senha = True

    try:
        db.session.commit()
        registrar_auditoria(
            acao="REDEFINIR_SENHA_FUNCIONARIO",
            entidade="usuario",
            entidade_id=funcionario.id_usuario,
            detalhes={"motivo": "Redefinição administrativa"}
        )
        db.session.commit()
        return jsonify({"mensagem": "Senha do funcionário redefinida com sucesso."})
    except Exception:
        db.session.rollback()
        return jsonify({"erro": "Erro ao redefinir senha do funcionário."}), 500
