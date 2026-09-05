from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, jsonify
from flask_login import current_user
from sqlalchemy import func
from app.extensions import db
from app.models.cliente import Cliente
from app.models.compra import Compra
from app.models.resgate import Resgate
from app.routes.auth import vendedora_required, cliente_required
from app.services.rbac import permissao_requerida

main_bp = Blueprint("main", __name__)


# ---------- Entrada / Portal de Login Unificado ----------
@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        if getattr(current_user, "is_vendedora", False):
            return redirect(url_for("main.dashboard"))
        elif getattr(current_user, "is_cliente", False):
            return redirect(url_for("main.bemvindo"))
    return render_template("login.html")


@main_bp.route("/health")
def health():
    return {"status": "ok"}


@main_bp.route("/cadastro")
def cadastro():
    return redirect(url_for("auth.cadastrar_cliente_web"))


# ---------- Área Administrativa / Gestão da Loja ----------
@main_bp.route("/dashboard")
@vendedora_required
def dashboard():
    return render_template("vendedora/dashboard.html")


@main_bp.route("/api/dashboard/estatisticas")
@vendedora_required
def dashboard_estatisticas():
    """Agrega indicadores de negócio reais em tempo real para o dashboard administrativo."""
    total_clientes = Cliente.query.count()
    clientes_ativos = Cliente.query.filter_by(ativo=True).count()

    inicio_mes = datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=None
    )
    novos_clientes_mes = Cliente.query.filter(Cliente.data_cadastro >= inicio_mes).count()

    total_compras = Compra.query.count()
    faturamento_total = db.session.query(func.coalesce(func.sum(Compra.valor), 0)).scalar()
    faturamento_mes = db.session.query(func.coalesce(func.sum(Compra.valor), 0)).filter(
        Compra.data >= inicio_mes
    ).scalar()
    pontos_emitidos = db.session.query(func.coalesce(func.sum(Compra.pontos_gerados), 0)).scalar()

    total_resgates = Resgate.query.count()
    pontos_utilizados = db.session.query(func.coalesce(func.sum(Resgate.pontos_utilizados), 0)).scalar()
    saldo_circulacao = db.session.query(func.coalesce(func.sum(Cliente.pontos_acumulados), 0)).scalar()

    ultimas_compras = (
        db.session.query(Compra, Cliente.nome)
        .join(Cliente, Compra.id_cliente == Cliente.id_cliente)
        .order_by(Compra.data.desc())
        .limit(6)
        .all()
    )
    lista_compras = [
        {
            "id_compra": c[0].id_compra,
            "cliente_nome": c[1],
            "valor": float(c[0].valor),
            "pontos": c[0].pontos_gerados,
            "data": c[0].data.isoformat() if c[0].data else None,
        }
        for c in ultimas_compras
    ]

    ultimos_resgates = (
        db.session.query(Resgate, Cliente.nome)
        .join(Cliente, Resgate.id_cliente == Cliente.id_cliente)
        .order_by(Resgate.data.desc())
        .limit(6)
        .all()
    )
    lista_resgates = [
        {
            "id_resgate": r[0].id_resgate,
            "cliente_nome": r[1],
            "descricao": r[0].descricao_recompensa,
            "pontos": r[0].pontos_utilizados,
            "data": r[0].data.isoformat() if r[0].data else None,
        }
        for r in ultimos_resgates
    ]

    clientes_recentes = Cliente.query.order_by(Cliente.data_cadastro.desc()).limit(6).all()
    lista_clientes = [c.to_dict() for c in clientes_recentes]

    return jsonify({
        "total_clientes": total_clientes,
        "clientes_ativos": clientes_ativos,
        "novos_clientes_mes": novos_clientes_mes,
        "total_compras": total_compras,
        "faturamento_total": float(faturamento_total),
        "faturamento_mes": float(faturamento_mes),
        "pontos_emitidos": int(pontos_emitidos),
        "pontos_utilizados": int(pontos_utilizados),
        "saldo_circulacao": int(saldo_circulacao),
        "total_resgates": total_resgates,
        "ultimas_compras": lista_compras,
        "ultimos_resgates": lista_resgates,
        "clientes_recentes": lista_clientes,
    })


@main_bp.route("/clientes")
@vendedora_required
def v_clientes():
    return render_template("vendedora/clientes.html")


@main_bp.route("/funcionarios")
@vendedora_required
@permissao_requerida("funcionarios.visualizar")
def funcionarios():
    return render_template("vendedora/funcionarios.html")


@main_bp.route("/auditoria")
@vendedora_required
@permissao_requerida("auditoria.visualizar")
def auditoria():
    return render_template("vendedora/auditoria.html")


@main_bp.route("/pontuar")
@vendedora_required
def pontuar():
    return render_template("vendedora/pontos.html")


@main_bp.route("/resgate")
@vendedora_required
def resgate():
    return render_template("vendedora/resgate.html")


@main_bp.route("/gestao-recompensas")
@vendedora_required
def gestao_recompensas():
    return render_template("vendedora/recompensas.html")


@main_bp.route("/relatorios")
@vendedora_required
def relatorios():
    return render_template("vendedora/relatorios.html")


@main_bp.route("/alterar-senha")
@vendedora_required
def alterar_senha():
    return render_template("vendedora/alterar_senha.html")


# ---------- Área do CLIENTE (Autoatendimento & Pontos) ----------
@main_bp.route("/bemvindo")
@cliente_required
def bemvindo():
    return render_template("clientes/bemvindo.html")


@main_bp.route("/meuspontos")
@cliente_required
def meuspontos():
    return render_template("clientes/meuspontos.html")


@main_bp.route("/recompensas")
@cliente_required
def recompensas():
    return render_template("clientes/recompensas.html")


@main_bp.route("/historico")
@cliente_required
def historico():
    return render_template("clientes/historico.html")
