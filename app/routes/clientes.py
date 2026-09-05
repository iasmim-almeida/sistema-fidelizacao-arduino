import re
import secrets
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy import desc, asc
from app.models.cliente import Cliente
from app.models.compra import Compra
from app.models.resgate import Resgate
from app.models.movimentacao_pontos import MovimentacaoPontos
from app.extensions import db
from app.services.rbac import permissao_requerida
from app.services.auditoria import registrar_auditoria
from app.services.pontos import registrar_movimentacao

clientes_bp = Blueprint("clientes", __name__)


@clientes_bp.route("/me", methods=["GET"])
@login_required
def me():
    """Retorna os dados do cliente atualmente autenticado."""
    if not getattr(current_user, "is_cliente", False):
        return jsonify({"erro": "Usuario autenticado nao e um cliente"}), 403
    cliente = db.session.get(Cliente, current_user.id_cliente)
    return jsonify(cliente.to_dict() if cliente else current_user.to_dict())


@clientes_bp.route("/", methods=["GET"])
@login_required
def listar():
    """
    Lista clientes com filtros, busca, ordenação e suporte a paginação.
    Clientes comuns acessam apenas os próprios dados.
    Vendedoras/administradores possuem acesso à lista completa.
    """
    if getattr(current_user, "is_cliente", False):
        cliente = db.session.get(Cliente, current_user.id_cliente)
        return jsonify(cliente.to_dict() if cliente else {})

    if not getattr(current_user, "is_vendedora", False):
        return jsonify({"erro": "Acesso negado. Perfil nao autorizado."}), 403

    if not current_user.tem_permissao("clientes.visualizar"):
        return jsonify({"erro": "Acesso negado. Requer permissão 'clientes.visualizar'."}), 403

    # Busca específica por telefone direto (retrocompatibilidade)
    telefone = request.args.get("telefone")
    if telefone:
        tel_limpo = re.sub(r"\D", "", str(telefone).strip())
        cliente = Cliente.query.filter(
            (Cliente.telefone == telefone) | (Cliente.telefone == tel_limpo)
        ).first()
        if not cliente:
            return jsonify({"erro": "Cliente nao encontrado"}), 404
        return jsonify(cliente.to_dict())

    query = Cliente.query

    # Busca textual (nome, telefone ou email)
    termo = request.args.get("q", "").strip()
    if termo:
        termo_limpo = re.sub(r"\D", "", termo)
        filtros = [Cliente.nome.ilike(f"%{termo}%"), Cliente.email.ilike(f"%{termo}%")]
        if termo_limpo:
            filtros.append(Cliente.telefone.ilike(f"%{termo_limpo}%"))
        else:
            filtros.append(Cliente.telefone.ilike(f"%{termo}%"))
        query = query.filter(db.or_(*filtros))

    # Filtro de status (ativo / inativo / todos)
    status = request.args.get("status", "").strip().lower()
    if status == "ativo":
        query = query.filter(Cliente.ativo == True)
    elif status == "inativo":
        query = query.filter(Cliente.ativo == False)

    # Filtro por faixa de pontos
    min_pontos = request.args.get("min_pontos", type=int)
    if min_pontos is not None:
        query = query.filter(Cliente.pontos_acumulados >= min_pontos)

    max_pontos = request.args.get("max_pontos", type=int)
    if max_pontos is not None:
        query = query.filter(Cliente.pontos_acumulados <= max_pontos)

    # Ordenação
    sort_by = request.args.get("sort_by", "nome").strip().lower()
    order = request.args.get("order", "asc").strip().lower()

    coluna = Cliente.nome
    if sort_by == "pontos":
        coluna = Cliente.pontos_acumulados
    elif sort_by == "data_cadastro":
        coluna = Cliente.data_cadastro

    query = query.order_by(desc(coluna) if order == "desc" else asc(coluna))

    # Paginação opcional
    page = request.args.get("page", type=int)
    per_page = request.args.get("per_page", type=int)

    if page is not None and per_page is not None:
        paginacao = query.paginate(page=page, per_page=min(per_page, 100), error_out=False)
        return jsonify({
            "total": paginacao.total,
            "page": paginacao.page,
            "pages": paginacao.pages,
            "per_page": paginacao.per_page,
            "items": [c.to_dict() for c in paginacao.items],
        })

    clientes = query.all()
    return jsonify([c.to_dict() for c in clientes])


@clientes_bp.route("/<int:id>", methods=["GET"])
@login_required
def obter(id):
    """
    Consulta o perfil detalhado do cliente.
    Clientes comuns só acessam o próprio perfil (proteção BOLA/IDOR).
    Retorna dados cadastrais, resumo de compras, resgates e saldo.
    """
    if getattr(current_user, "is_cliente", False):
        if current_user.id_cliente != id:
            return jsonify({"erro": "Acesso nao permitido ao perfil solicitado"}), 403

    elif not getattr(current_user, "is_vendedora", False):
        return jsonify({"erro": "Acesso negado"}), 403

    elif not current_user.tem_permissao("clientes.visualizar"):
        return jsonify({"erro": "Acesso negado. Requer permissão 'clientes.visualizar'."}), 403

    cliente = db.session.get(Cliente, id)
    if not cliente:
        return jsonify({"erro": "Cliente nao encontrado"}), 404

    dados = cliente.to_dict()

    # Métricas e histórico detalhado
    compras_count = Compra.query.filter_by(id_cliente=id).count()
    resgates_count = Resgate.query.filter_by(id_cliente=id).count()
    ultima_compra = Compra.query.filter_by(id_cliente=id).order_by(Compra.data.desc()).first()
    ultimo_resgate = Resgate.query.filter_by(id_cliente=id).order_by(Resgate.data.desc()).first()

    dados["total_compras"] = compras_count
    dados["total_resgates"] = resgates_count
    dados["ultima_compra"] = ultima_compra.to_dict() if ultima_compra else None
    dados["ultimo_resgate"] = ultimo_resgate.to_dict() if ultimo_resgate else None

    return jsonify(dados)


@clientes_bp.route("/", methods=["POST"])
@login_required
def cadastrar():
    """Cadastro no PDV restrito a vendedoras autenticadas com senha segura."""
    if not getattr(current_user, "is_vendedora", False):
        return jsonify({"erro": "Acesso restrito a vendedoras"}), 403

    if not current_user.tem_permissao("clientes.criar"):
        return jsonify({"erro": "Acesso negado. Requer permissão 'clientes.criar'."}), 403

    data = request.get_json() or {}
    nome = (data.get("nome") or "").strip()
    telefone = (data.get("telefone") or "").strip()

    if not nome or not telefone:
        return jsonify({"erro": "nome e telefone sao obrigatorios"}), 400

    tel_limpo = re.sub(r"\D", "", telefone)
    if len(tel_limpo) < 10 or len(tel_limpo) > 11:
        return jsonify({"erro": "Telefone invalido. Informe o DDD e o numero com 10 ou 11 digitos."}), 400

    if Cliente.query.filter((Cliente.telefone == telefone) | (Cliente.telefone == tel_limpo)).first():
        return jsonify({"erro": "Ja existe um cliente cadastrado com este telefone."}), 409

    email = (data.get("email") or "").strip().lower() or None
    if email and Cliente.query.filter_by(email=email).first():
        return jsonify({"erro": "Ja existe um cliente cadastrado com este e-mail."}), 409

    senha = data.get("senha")
    senha_gerada = False

    if not senha:
        senha = secrets.token_urlsafe(8)
        senha_gerada = True
    elif len(str(senha)) < 8 or str(senha) == "1234":
        return jsonify({"erro": "A senha deve conter no minimo 8 caracteres e nao pode ser '1234'"}), 400

    cliente = Cliente(
        nome=nome,
        telefone=tel_limpo,
        email=email,
        endereco=data.get("endereco"),
        ativo=True,
    )
    cliente.set_senha(str(senha))

    try:
        db.session.add(cliente)
        db.session.commit()

        registrar_auditoria(
            acao="CRIAR_CLIENTE",
            entidade="cliente",
            entidade_id=cliente.id_cliente,
            detalhes={"nome": nome, "telefone": tel_limpo, "email": email},
        )
        db.session.commit()

        res = cliente.to_dict()
        if senha_gerada:
            res["senha_gerada_automatica"] = senha
        return jsonify(res), 201

    except Exception:
        db.session.rollback()
        return jsonify({"erro": "Erro ao persistir cliente no banco de dados."}), 500


@clientes_bp.route("/<int:id>", methods=["PUT", "PATCH"])
@login_required
def editar(id):
    """Atualização cadastral do cliente protegida por RBAC."""
    if not getattr(current_user, "is_vendedora", False):
        return jsonify({"erro": "Acesso negado"}), 403

    if not current_user.tem_permissao("clientes.editar"):
        return jsonify({"erro": "Acesso negado. Requer permissão 'clientes.editar'."}), 403

    cliente = db.session.get(Cliente, id)
    if not cliente:
        return jsonify({"erro": "Cliente nao encontrado"}), 404

    data = request.get_json(silent=True) or {}
    alteracoes = {}

    if "nome" in data:
        novo_nome = str(data["nome"]).strip()
        if len(novo_nome) < 3:
            return jsonify({"erro": "O nome deve conter ao menos 3 caracteres."}), 400
        alteracoes["nome_anterior"] = cliente.nome
        cliente.nome = novo_nome
        alteracoes["nome_novo"] = novo_nome

    if "telefone" in data:
        novo_tel = re.sub(r"\D", "", str(data["telefone"]).strip())
        if len(novo_tel) < 10 or len(novo_tel) > 11:
            return jsonify({"erro": "Telefone inválido (deve conter DDD + 8 ou 9 dígitos)."}), 400
        duplicado = Cliente.query.filter(Cliente.telefone == novo_tel, Cliente.id_cliente != id).first()
        if duplicado:
            return jsonify({"erro": "Já existe outro cliente com este telefone."}), 409
        alteracoes["telefone_anterior"] = cliente.telefone
        cliente.telefone = novo_tel
        alteracoes["telefone_novo"] = novo_tel

    if "email" in data:
        novo_email = str(data["email"]).strip().lower() or None
        if novo_email:
            duplicado = Cliente.query.filter(Cliente.email == novo_email, Cliente.id_cliente != id).first()
            if duplicado:
                return jsonify({"erro": "Já existe outro cliente com este e-mail."}), 409
        alteracoes["email_anterior"] = cliente.email
        cliente.email = novo_email
        alteracoes["email_novo"] = novo_email

    if "endereco" in data:
        cliente.endereco = str(data["endereco"]).strip() or None

    try:
        db.session.commit()
        registrar_auditoria(
            acao="EDITAR_CLIENTE",
            entidade="cliente",
            entidade_id=cliente.id_cliente,
            detalhes=alteracoes,
        )
        db.session.commit()
        return jsonify({
            "mensagem": "Cliente atualizado com sucesso.",
            "cliente": cliente.to_dict(),
        })
    except Exception:
        db.session.rollback()
        return jsonify({"erro": "Erro ao atualizar dados do cliente."}), 500


@clientes_bp.route("/<int:id>/status", methods=["POST"])
@login_required
def alterar_status(id):
    """Desativação ou reativação (soft delete) de cliente."""
    if not getattr(current_user, "is_vendedora", False):
        return jsonify({"erro": "Acesso negado"}), 403

    if not current_user.tem_permissao("clientes.desativar"):
        return jsonify({"erro": "Acesso negado. Requer permissão 'clientes.desativar'."}), 403

    cliente = db.session.get(Cliente, id)
    if not cliente:
        return jsonify({"erro": "Cliente nao encontrado"}), 404

    data = request.get_json(silent=True) or {}
    novo_status = bool(data.get("ativo", not cliente.ativo))
    motivo = str(data.get("motivo", "")).strip()

    status_anterior = cliente.ativo
    cliente.ativo = novo_status
    acao = "ATIVAR_CLIENTE" if novo_status else "DESATIVAR_CLIENTE"

    try:
        db.session.commit()
        registrar_auditoria(
            acao=acao,
            entidade="cliente",
            entidade_id=cliente.id_cliente,
            detalhes={"status_anterior": status_anterior, "novo_status": novo_status, "motivo": motivo},
        )
        db.session.commit()
        return jsonify({
            "mensagem": f"Cliente {'ativado' if novo_status else 'desativado'} com sucesso.",
            "cliente": cliente.to_dict(),
        })
    except Exception:
        db.session.rollback()
        return jsonify({"erro": "Erro ao alterar status do cliente."}), 500


@clientes_bp.route("/<int:id>/pontos/ajuste", methods=["POST"])
@login_required
def ajustar_pontos(id):
    """
    Ajuste manual auditável de pontos (Adicionar / Remover).
    Exige quantidade > 0, motivo obrigatório, validação de saldo não negativo
    e registro imutável no ledger de movimentações.
    """
    if not getattr(current_user, "is_vendedora", False):
        return jsonify({"erro": "Acesso negado. Requer perfil administrativo."}), 403

    data = request.get_json(silent=True) or {}
    operacao = str(data.get("operacao") or data.get("tipo") or "").strip().lower()
    motivo = str(data.get("motivo") or "").strip()

    if not motivo:
        return jsonify({"erro": "O motivo do ajuste é obrigatório."}), 400

    try:
        quantidade_bruta = int(data.get("quantidade", 0))
    except (ValueError, TypeError):
        return jsonify({"erro": "Quantidade de pontos inválida."}), 400

    if quantidade_bruta <= 0:
        return jsonify({"erro": "A quantidade de pontos deve ser um número inteiro maior que zero."}), 400

    if operacao in ("adicionar", "credito", "positivo", "ajuste_positivo"):
        if not current_user.tem_permissao("pontos.adicionar"):
            return jsonify({"erro": "Acesso negado. Requer permissão 'pontos.adicionar'."}), 403
        tipo_ledger = "AJUSTE_POSITIVO"
        delta = quantidade_bruta
    elif operacao in ("remover", "debito", "negativo", "ajuste_negativo", "estorno"):
        if not current_user.tem_permissao("pontos.remover"):
            return jsonify({"erro": "Acesso negado. Requer permissão 'pontos.remover'."}), 403
        tipo_ledger = "AJUSTE_NEGATIVO"
        delta = -quantidade_bruta
    else:
        return jsonify({"erro": "Operação inválida. Escolha 'adicionar' ou 'remover'."}), 400

    try:
        sucesso, movimentacao, erro = registrar_movimentacao(
            cliente_id=id,
            tipo=tipo_ledger,
            quantidade=delta,
            origem=f"manual_{current_user.login}",
            motivo=motivo,
            usuario_id=current_user.id_usuario,
        )

        if not sucesso:
            db.session.rollback()
            return jsonify({"erro": erro}), 400

        db.session.commit()

        registrar_auditoria(
            acao=f"AJUSTE_PONTOS_{'CREDITO' if delta > 0 else 'DEBITO'}",
            entidade="cliente",
            entidade_id=id,
            detalhes={
                "quantidade": delta,
                "motivo": motivo,
                "saldo_anterior": movimentacao.saldo_anterior,
                "saldo_posterior": movimentacao.saldo_posterior,
            },
        )
        db.session.commit()

        return jsonify({
            "mensagem": f"Pontos {'adicionados' if delta > 0 else 'removidos'} com sucesso.",
            "movimentacao": movimentacao.to_dict(),
            "saldo_atual": movimentacao.saldo_posterior,
        }), 200

    except Exception:
        db.session.rollback()
        return jsonify({"erro": "Erro ao processar ajuste de pontos."}), 500


@clientes_bp.route("/<int:id>/extrato", methods=["GET"])
@login_required
def extrato(id):
    """
    Retorna o extrato / ledger de movimentações de pontos do cliente.
    Segregado: cliente vê apenas o próprio extrato; vendedoras com permissão veem o extrato do cliente.
    """
    if getattr(current_user, "is_cliente", False):
        if current_user.id_cliente != id:
            return jsonify({"erro": "Acesso negado ao extrato de outro cliente."}), 403
    elif not getattr(current_user, "is_vendedora", False):
        return jsonify({"erro": "Acesso negado."}), 403
    elif not current_user.tem_permissao("pontos.visualizar"):
        return jsonify({"erro": "Acesso negado. Requer permissão 'pontos.visualizar'."}), 403

    cliente = db.session.get(Cliente, id)
    if not cliente:
        return jsonify({"erro": "Cliente não encontrado."}), 404

    movimentacoes = MovimentacaoPontos.query.filter_by(id_cliente=id).order_by(
        MovimentacaoPontos.data_hora.desc()
    ).all()

    return jsonify({
        "id_cliente": cliente.id_cliente,
        "nome": cliente.nome,
        "saldo_atual": cliente.pontos_acumulados,
        "ativo": cliente.ativo,
        "extrato": [m.to_dict() for m in movimentacoes],
    })
