from datetime import datetime
from flask import Blueprint, jsonify, request
from flask_login import login_required
from app.models.auditoria import Auditoria
from app.services.rbac import permissao_requerida

auditoria_bp = Blueprint("auditoria", __name__)


@auditoria_bp.route("/", methods=["GET"])
@login_required
@permissao_requerida("auditoria.visualizar")
def listar():
    """Consulta paginada e filtrada dos logs de auditoria administrativa."""
    query = Auditoria.query

    usuario_id = request.args.get("usuario_id", type=int)
    if usuario_id:
        query = query.filter_by(id_usuario=usuario_id)

    acao = request.args.get("acao")
    if acao:
        query = query.filter(Auditoria.acao.ilike(f"%{acao.strip()}%"))

    entidade = request.args.get("entidade")
    if entidade:
        query = query.filter_by(entidade=entidade.strip().lower())

    entidade_id = request.args.get("entidade_id")
    if entidade_id:
        query = query.filter_by(entidade_id=str(entidade_id).strip())

    data_inicio = request.args.get("data_inicio")
    if data_inicio:
        try:
            dt_ini = datetime.fromisoformat(data_inicio.strip())
            query = query.filter(Auditoria.data_hora >= dt_ini)
        except ValueError:
            pass

    data_fim = request.args.get("data_fim")
    if data_fim:
        try:
            dt_fim = datetime.fromisoformat(data_fim.strip())
            query = query.filter(Auditoria.data_hora <= dt_fim)
        except ValueError:
            pass

    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 25, type=int), 100)

    paginacao = query.order_by(Auditoria.data_hora.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        "total": paginacao.total,
        "page": paginacao.page,
        "pages": paginacao.pages,
        "per_page": paginacao.per_page,
        "items": [item.to_dict() for item in paginacao.items],
    })
