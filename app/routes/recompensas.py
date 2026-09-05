from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.recompensa import (
    STATUS_RECOMPENSA,
    TIPOS_RECOMPENSA,
    Recompensa,
    data_local_atual,
)
from app.routes.auth import vendedora_required
from app.services.auditoria import registrar_auditoria


recompensas_bp = Blueprint("recompensas", __name__)

MAX_PONTOS = 1_000_000_000
MAX_ESTOQUE = 1_000_000_000
MAX_VALOR_BENEFICIO = Decimal("99999999.99")
CAMPO_PROTEGIDOS = {
    "id_recompensa",
    "id_usuario",
    "quantidade_disponivel",
    "created_at",
    "updated_at",
}
CAMPO_PERMITIDOS = {
    "nome",
    "custo_pontos",
    "tipo",
    "valor_beneficio",
    "validade",
    "quantidade_total",
    "status",
}


def _inteiro(data, campo, atual=None):
    valor = data.get(campo, atual)
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise ValueError(f"{campo} deve ser um número inteiro")
    return valor


def _decimal_positivo(valor, tipo):
    if isinstance(valor, bool) or valor is None:
        raise ValueError("valor_beneficio é obrigatório para recompensas de desconto")
    try:
        decimal_val = Decimal(str(valor))
    except (InvalidOperation, TypeError):
        raise ValueError("valor_beneficio inválido") from None
    if decimal_val <= 0:
        raise ValueError("valor_beneficio deve ser maior que zero")
    if tipo == "desconto_percentual" and decimal_val > Decimal("100.00"):
        raise ValueError("desconto percentual não pode ser maior que 100%")
    if decimal_val > MAX_VALOR_BENEFICIO:
        raise ValueError("valor_beneficio excede o limite máximo permitido")
    return decimal_val


def _validar_payload(data, recompensa=None):
    if not isinstance(data, dict):
        raise ValueError("O corpo da requisição deve ser um objeto JSON")

    chaves = set(data.keys())
    protegidos = chaves.intersection(CAMPO_PROTEGIDOS)
    if protegidos:
        raise ValueError(
            f"Os seguintes campos são de leitura exclusiva e não podem ser enviados: {', '.join(sorted(protegidos))}"
        )

    desconhecidos = chaves - CAMPO_PERMITIDOS
    if desconhecidos:
        raise ValueError(
            f"Campos desconhecidos: {', '.join(sorted(desconhecidos))}"
        )

    criando = recompensa is None
    obrigatorios = {"nome", "custo_pontos", "tipo", "validade", "quantidade_total"}
    if criando and not obrigatorios.issubset(chaves):
        faltantes = obrigatorios - chaves
        raise ValueError(
            f"Campos obrigatórios ausentes: {', '.join(sorted(faltantes))}"
        )

    nome = data.get("nome", recompensa.nome if recompensa else "").strip()
    if not nome:
        raise ValueError("nome não pode ser vazio")
    if len(nome) > 120:
        raise ValueError("nome não pode ter mais de 120 caracteres")

    custo = _inteiro(data, "custo_pontos", recompensa.custo_pontos if recompensa else None)
    if custo <= 0:
        raise ValueError("custo_pontos deve ser maior que zero")
    if custo > MAX_PONTOS:
        raise ValueError("custo_pontos deve não exceder 1000000000")

    tipo = data.get("tipo", recompensa.tipo if recompensa else None)
    if tipo not in TIPOS_RECOMPENSA:
        raise ValueError("tipo de recompensa inválido")

    valor_original = data.get(
        "valor_beneficio",
        recompensa.valor_beneficio if recompensa else None,
    )
    valor_beneficio = None if tipo == "produto_fisico" else _decimal_positivo(valor_original, tipo)

    validade_original = data.get(
        "validade",
        recompensa.validade.isoformat() if recompensa else None,
    )
    if not isinstance(validade_original, str):
        raise ValueError("validade deve estar no formato AAAA-MM-DD")
    try:
        validade = datetime.strptime(validade_original, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("validade deve ser uma data válida no formato AAAA-MM-DD") from None
    if (criando or "validade" in data) and validade < data_local_atual():
        raise ValueError("validade não pode estar no passado")

    quantidade_total = _inteiro(
        data,
        "quantidade_total",
        recompensa.quantidade_total if recompensa else None,
    )
    if quantidade_total < 0 or quantidade_total > MAX_ESTOQUE:
        raise ValueError("quantidade_total deve estar entre zero e 1000000000")

    if recompensa:
        quantidade_utilizada = recompensa.quantidade_total - recompensa.quantidade_disponivel
        if quantidade_total < quantidade_utilizada:
            raise ValueError(
                f"quantidade_total não pode ser menor que as {quantidade_utilizada} unidades já resgatadas"
            )
        quantidade_disponivel = quantidade_total - quantidade_utilizada
    else:
        quantidade_disponivel = quantidade_total

    status = data.get("status", recompensa.status if recompensa else None)
    if status not in STATUS_RECOMPENSA:
        raise ValueError("status deve ser 'ativa' ou 'pausada'")

    return {
        "nome": nome,
        "custo_pontos": custo,
        "tipo": tipo,
        "valor_beneficio": valor_beneficio,
        "validade": validade,
        "quantidade_total": quantidade_total,
        "quantidade_disponivel": quantidade_disponivel,
        "status": status,
    }


@recompensas_bp.route("/", methods=["GET"])
@login_required
def listar():
    if getattr(current_user, "is_vendedora", False):
        if not getattr(current_user, "ativo", True):
            return jsonify({"erro": "Conta inativa."}), 403
        recompensas = (
            Recompensa.query.filter_by(id_usuario=current_user.id_usuario)
            .order_by(Recompensa.created_at.desc(), Recompensa.id_recompensa.desc())
            .all()
        )
        return jsonify([r.to_dict(incluir_proprietario=True) for r in recompensas])

    if getattr(current_user, "is_cliente", False):
        if not getattr(current_user, "ativo", True):
            return jsonify({"erro": "Conta inativa."}), 403
        # Expiradas ficam no histórico administrativo, mas não poluem o catálogo.
        recompensas = (
            Recompensa.query.filter(Recompensa.validade >= data_local_atual())
            .order_by(Recompensa.status, Recompensa.custo_pontos, Recompensa.nome)
            .all()
        )
        return jsonify([r.to_dict(saldo_cliente=current_user.pontos_acumulados) for r in recompensas])

    return jsonify({"erro": "Acesso não autorizado"}), 403


@recompensas_bp.route("/<int:id_recompensa>", methods=["GET"])
@login_required
def obter(id_recompensa):
    query = Recompensa.query.filter_by(id_recompensa=id_recompensa)
    if getattr(current_user, "is_vendedora", False):
        if not getattr(current_user, "ativo", True):
            return jsonify({"erro": "Conta inativa."}), 403
        recompensa = query.filter_by(id_usuario=current_user.id_usuario).first_or_404()
        return jsonify(recompensa.to_dict(incluir_proprietario=True))
    if getattr(current_user, "is_cliente", False):
        if not getattr(current_user, "ativo", True):
            return jsonify({"erro": "Conta inativa."}), 403
        recompensa = query.filter(Recompensa.validade >= data_local_atual()).first_or_404()
        return jsonify(recompensa.to_dict(saldo_cliente=current_user.pontos_acumulados))
    return jsonify({"erro": "Acesso não autorizado"}), 403


@recompensas_bp.route("/", methods=["POST"])
@vendedora_required
def criar():
    if not current_user.tem_permissao("recompensas.criar"):
        return jsonify({"erro": "Acesso negado. Requer permissão 'recompensas.criar'."}), 403

    try:
        valores = _validar_payload(request.get_json(silent=True))
    except ValueError as erro:
        return jsonify({"erro": str(erro)}), 400

    recompensa = Recompensa(id_usuario=current_user.id_usuario, **valores)
    try:
        db.session.add(recompensa)
        db.session.commit()

        registrar_auditoria(
            acao="CRIAR_RECOMPENSA",
            entidade="recompensa",
            entidade_id=recompensa.id_recompensa,
            detalhes={"nome": recompensa.nome, "custo_pontos": recompensa.custo_pontos, "tipo": recompensa.tipo},
        )
        db.session.commit()

    except IntegrityError:
        db.session.rollback()
        return jsonify({"erro": "Não foi possível salvar a recompensa"}), 409
    except Exception:
        db.session.rollback()
        return jsonify({"erro": "Falha ao salvar a recompensa"}), 500

    return jsonify(recompensa.to_dict(incluir_proprietario=True)), 201


@recompensas_bp.route("/<int:id_recompensa>", methods=["PATCH"])
@vendedora_required
def editar(id_recompensa):
    if not current_user.tem_permissao("recompensas.editar") and not current_user.tem_permissao("recompensas.desativar"):
        return jsonify({"erro": "Acesso negado. Requer permissão 'recompensas.editar'."}), 403

    # O filtro pelo proprietário retorna 404 e evita enumeração/IDOR.
    recompensa = (
        Recompensa.query.with_for_update()
        .filter_by(
            id_recompensa=id_recompensa,
            id_usuario=current_user.id_usuario,
        )
        .first_or_404()
    )

    try:
        valores = _validar_payload(request.get_json(silent=True), recompensa)
    except ValueError as erro:
        return jsonify({"erro": str(erro)}), 400

    for campo, valor in valores.items():
        setattr(recompensa, campo, valor)

    try:
        db.session.commit()
        registrar_auditoria(
            acao="EDITAR_RECOMPENSA",
            entidade="recompensa",
            entidade_id=recompensa.id_recompensa,
            detalhes={"status": recompensa.status, "quantidade_disponivel": recompensa.quantidade_disponivel},
        )
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"erro": "Não foi possível atualizar a recompensa"}), 409
    except Exception:
        db.session.rollback()
        return jsonify({"erro": "Falha ao atualizar a recompensa"}), 500

    return jsonify(recompensa.to_dict(incluir_proprietario=True))
