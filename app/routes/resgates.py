import re
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import update

from app.extensions import db
from app.models.cliente import Cliente
from app.models.recompensa import Recompensa, data_local_atual
from app.models.resgate import Resgate
from app.models.movimentacao_pontos import MovimentacaoPontos
from app.services.auditoria import registrar_auditoria


resgates_bp = Blueprint("resgates", __name__)
CHAVES_PERMITIDAS = {"id_cliente", "telefone", "id_recompensa"}


@resgates_bp.route("/", methods=["GET"])
@login_required
def listar():
    """Segrega o histórico: cliente vê o próprio; vendedora vê o global."""
    query = Resgate.query

    if getattr(current_user, "is_cliente", False):
        query = query.filter_by(id_cliente=current_user.id_cliente)
    elif getattr(current_user, "is_vendedora", False):
        id_cliente = request.args.get("id_cliente", type=int)
        if id_cliente:
            query = query.filter_by(id_cliente=id_cliente)
    else:
        return jsonify({"erro": "Acesso não autorizado"}), 403

    resgates = query.order_by(Resgate.data.desc()).all()
    return jsonify([r.to_dict() for r in resgates])


def _identificar_cliente(data):
    if getattr(current_user, "is_cliente", False):
        id_informado = data.get("id_cliente")
        if id_informado is not None and id_informado != current_user.id_cliente:
            return None, (jsonify({"erro": "Cliente não pode resgatar para outra conta"}), 403)
        return current_user.id_cliente, None

    if not getattr(current_user, "is_vendedora", False):
        return None, (jsonify({"erro": "Perfil sem permissão para efetuar resgates"}), 403)

    if not getattr(current_user, "ativo", True):
        return None, (jsonify({"erro": "Conta inativa. Operação não permitida."}), 403)

    if not current_user.tem_permissao("resgates.validar"):
        return None, (jsonify({"erro": "Acesso negado. Requer permissão 'resgates.validar'."}), 403)

    alvo_id = data.get("id_cliente")
    if isinstance(alvo_id, bool) or (alvo_id is not None and not isinstance(alvo_id, int)):
        return None, (jsonify({"erro": "id_cliente deve ser um número inteiro"}), 400)

    if not alvo_id and data.get("telefone"):
        identificador = str(data["telefone"]).strip()
        tel_limpo = re.sub(r"\D", "", identificador)
        encontrado = Cliente.query.filter(
            (Cliente.telefone == identificador) | (Cliente.telefone == tel_limpo)
        ).first()
        alvo_id = encontrado.id_cliente if encontrado else None

    if not alvo_id:
        return None, (jsonify({"erro": "Cliente não informado para o resgate"}), 400)
    return alvo_id, None


@resgates_bp.route("/", methods=["POST"])
@login_required
def registrar():
    """Debita saldo e estoque de forma atômica usando o custo persistido e registra no ledger."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"erro": "O corpo da requisição deve ser um objeto JSON"}), 400

    campos_invalidos = set(data) - CHAVES_PERMITIDAS
    if campos_invalidos:
        return jsonify({
            "erro": "O resgate aceita apenas id_recompensa e a identificação do cliente; "
            "custo e descrição são definidos pelo servidor"
        }), 400

    id_recompensa = data.get("id_recompensa")
    if isinstance(id_recompensa, bool) or not isinstance(id_recompensa, int):
        return jsonify({"erro": "id_recompensa deve ser um número inteiro"}), 400

    alvo_id, erro = _identificar_cliente(data)
    if erro:
        return erro

    try:
        recompensa_query = Recompensa.query.with_for_update().filter_by(
            id_recompensa=id_recompensa
        )
        if getattr(current_user, "is_vendedora", False):
            # A entrega administrativa só opera recompensas da própria gestora.
            recompensa_query = recompensa_query.filter_by(id_usuario=current_user.id_usuario)
        recompensa = recompensa_query.first()

        if not recompensa:
            db.session.rollback()
            return jsonify({"erro": "Recompensa não encontrada"}), 404

        cliente = Cliente.query.with_for_update().filter_by(id_cliente=alvo_id).first()
        if not cliente:
            db.session.rollback()
            return jsonify({"erro": "Cliente não encontrado"}), 404

        if not getattr(cliente, "ativo", True):
            db.session.rollback()
            return jsonify({"erro": "Cliente inativo. Resgate não permitido."}), 400

        if recompensa.status != "ativa":
            db.session.rollback()
            return jsonify({"erro": "Recompensa temporariamente indisponível"}), 409
        if recompensa.esta_expirada:
            db.session.rollback()
            return jsonify({"erro": "Recompensa expirada"}), 409
        if recompensa.esta_esgotada:
            db.session.rollback()
            return jsonify({"erro": "Recompensa esgotada"}), 409
        if cliente.pontos_acumulados < recompensa.custo_pontos:
            saldo_atual = cliente.pontos_acumulados
            custo = recompensa.custo_pontos
            db.session.rollback()
            return jsonify({
                "erro": "Pontos insuficientes",
                "saldo_atual": saldo_atual,
                "custo_recompensa": custo,
            }), 400

        saldo_anterior = cliente.pontos_acumulados

        # Além do FOR UPDATE (efetivo no PostgreSQL), os UPDATEs condicionais
        # impedem estoque/saldo negativos inclusive no SQLite de desenvolvimento.
        estoque = db.session.execute(
            update(Recompensa)
            .where(
                Recompensa.id_recompensa == recompensa.id_recompensa,
                Recompensa.status == "ativa",
                Recompensa.validade >= data_local_atual(),
                Recompensa.quantidade_disponivel > 0,
            )
            .values(
                quantidade_disponivel=Recompensa.quantidade_disponivel - 1,
                updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            .execution_options(synchronize_session=False)
        )
        if estoque.rowcount != 1:
            db.session.rollback()
            return jsonify({"erro": "Recompensa não está mais disponível"}), 409

        saldo = db.session.execute(
            update(Cliente)
            .where(
                Cliente.id_cliente == cliente.id_cliente,
                Cliente.pontos_acumulados >= recompensa.custo_pontos,
            )
            .values(pontos_acumulados=Cliente.pontos_acumulados - recompensa.custo_pontos)
            .execution_options(synchronize_session=False)
        )
        if saldo.rowcount != 1:
            db.session.rollback()
            return jsonify({"erro": "Pontos insuficientes"}), 400

        resgate = Resgate(
            id_cliente=cliente.id_cliente,
            id_recompensa=recompensa.id_recompensa,
            pontos_utilizados=recompensa.custo_pontos,
            descricao_recompensa=recompensa.nome,
        )
        db.session.add(resgate)
        db.session.flush()

        # Registro no Ledger de Movimentação de Pontos
        origem = "vendedora" if getattr(current_user, "is_vendedora", False) else "cliente"
        usuario_id = current_user.id_usuario if getattr(current_user, "is_vendedora", False) else None
        mov = MovimentacaoPontos(
            id_cliente=cliente.id_cliente,
            tipo="RESGATE",
            quantidade=-recompensa.custo_pontos,
            saldo_anterior=saldo_anterior,
            saldo_posterior=saldo_anterior - recompensa.custo_pontos,
            origem=origem,
            motivo=f"Resgate da recompensa: {recompensa.nome}",
            id_usuario=usuario_id,
            id_resgate=resgate.id_resgate,
            id_recompensa=recompensa.id_recompensa,
            data_hora=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.session.add(mov)

        # Registro em auditoria
        registrar_auditoria(
            acao="VALIDAR_RESGATE",
            entidade="resgate",
            entidade_id=resgate.id_resgate,
            detalhes={
                "id_cliente": cliente.id_cliente,
                "id_recompensa": recompensa.id_recompensa,
                "pontos": recompensa.custo_pontos,
                "saldo_posterior": saldo_anterior - recompensa.custo_pontos,
            },
            usuario_id=usuario_id,
        )

        db.session.refresh(cliente)
        db.session.refresh(recompensa)
        resposta = {
            "status": "sucesso",
            "resgate": resgate.to_dict(),
            "cliente": cliente.to_dict(),
            "recompensa": recompensa.to_dict(saldo_cliente=cliente.pontos_acumulados),
            "saldo_atualizado": cliente.pontos_acumulados,
        }
        db.session.commit()
        return jsonify(resposta), 201

    except Exception:
        db.session.rollback()
        return jsonify({"erro": "Falha transacional ao processar resgate"}), 500
