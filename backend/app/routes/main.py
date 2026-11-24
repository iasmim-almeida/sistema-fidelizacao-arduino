from datetime import datetime, timedelta, timezone
from flask import Blueprint, render_template, redirect, url_for, jsonify, request
from flask_login import current_user
from sqlalchemy import func
from app.extensions import db
from app.models.cliente import Cliente
from app.models.compra import Compra
from app.models.resgate import Resgate
from app.routes.auth import vendedora_required, cliente_required

main_bp = Blueprint("main", __name__)


# ---------- Entrada / Portal de Login Unificado ----------
@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        if getattr(current_user, "is_vendedora", False):
            return redirect(url_for("main.dashboard"))
        elif getattr(current_user, "is_cliente", False):
            return redirect(url_for("main.bemvindo"))

    from app.routes.auth import sistema_precisa_setup
    if sistema_precisa_setup():
        return redirect(url_for("auth.setup"))

    return render_template("login.html")


@main_bp.route("/health")
def health():
    """Health check com verificação de conectividade ao banco de dados."""
    try:
        db.session.execute(db.text("SELECT 1"))
        return jsonify({"status": "healthy", "database": "connected"}), 200
    except Exception:
        return jsonify({"status": "unhealthy", "database": "disconnected"}), 503


@main_bp.route("/setup", methods=["GET", "POST"])
def setup():
    return redirect(url_for("auth.setup"), code=307 if request.method == "POST" else 302)


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
    clientes = Cliente.query.filter(Cliente.nivel_acesso == "CLIENTE")
    total_clientes = clientes.count()
    clientes_ativos = clientes.filter(Cliente.ativo.is_(True)).count()

    inicio_mes = datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=None
    )
    novos_clientes_mes = clientes.filter(Cliente.data_cadastro >= inicio_mes).count()

    total_compras = Compra.query.filter_by(tipo_movimentacao="COMPRA").count()
    pontos_emitidos = db.session.query(func.coalesce(func.sum(Compra.pontos_gerados), 0)).filter(Compra.tipo_movimentacao == "COMPRA").scalar()

    total_resgates = Resgate.query.filter_by(tipo_movimentacao="RESGATE").count()
    pontos_utilizados = db.session.query(func.coalesce(func.sum(Resgate.pontos_utilizados), 0)).filter(Resgate.tipo_movimentacao == "RESGATE").scalar()
    saldo_circulacao = (
        db.session.query(func.coalesce(func.sum(Cliente.pontos_acumulados), 0))
        .filter(Cliente.nivel_acesso == "CLIENTE")
        .scalar()
    )

    ultimas_compras = (
        db.session.query(Compra, Cliente.nome)
        .filter(Compra.tipo_movimentacao == "COMPRA")
        .join(Cliente, Compra.id_cliente == Cliente.id_cliente)
        .filter(Cliente.nivel_acesso == "CLIENTE")
        .order_by(Compra.data.desc())
        .limit(6)
        .all()
    )
    lista_compras = [
        {
            "id_compra": c[0].id_compra,
            "cliente_nome": c[1],
            "pontos": c[0].pontos_gerados,
            "data": c[0].data.isoformat() if c[0].data else None,
        }
        for c in ultimas_compras
    ]

    ultimos_resgates = (
        db.session.query(Resgate, Cliente.nome)
        .filter(Resgate.tipo_movimentacao == "RESGATE")
        .join(Cliente, Resgate.id_cliente == Cliente.id_cliente)
        .filter(Cliente.nivel_acesso == "CLIENTE")
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

    clientes_recentes = clientes.order_by(Cliente.data_cadastro.desc()).limit(6).all()
    lista_clientes = [c.to_dict() for c in clientes_recentes]

    return jsonify({
        "total_clientes": total_clientes,
        "clientes_ativos": clientes_ativos,
        "novos_clientes_mes": novos_clientes_mes,
        "total_compras": total_compras,
        "pontos_emitidos": int(pontos_emitidos),
        "pontos_utilizados": int(pontos_utilizados),
        "saldo_circulacao": int(saldo_circulacao),
        "total_resgates": total_resgates,
        "ultimas_compras": lista_compras,
        "ultimos_resgates": lista_resgates,
        "clientes_recentes": lista_clientes,
    })


@main_bp.route("/api/relatorios/indicadores")
@vendedora_required
def relatorios_indicadores():
    """Calcula os indicadores acadêmicos somente com clientes e movimentos válidos."""
    dias = request.args.get("dias", default=30, type=int)
    if dias is None or dias < 1 or dias > 3650:
        return jsonify({"erro": "dias deve estar entre 1 e 3650"}), 400

    agora = datetime.now(timezone.utc).replace(tzinfo=None)
    inicio_periodo = agora - timedelta(days=dias)
    clientes = Cliente.query.filter(Cliente.nivel_acesso == "CLIENTE")
    total_clientes_cadastrados = clientes.count()
    clientes_ativos = clientes.filter(Cliente.ativo.is_(True)).count()

    compras_periodo = Compra.query.join(
        Cliente, Compra.id_cliente == Cliente.id_cliente
    ).filter(
        Compra.tipo_movimentacao == "COMPRA",
        Compra.data >= inicio_periodo,
        Cliente.nivel_acesso == "CLIENTE",
    )
    quantidade_compras = compras_periodo.count()
    clientes_com_compra = compras_periodo.with_entities(
        func.count(func.distinct(Compra.id_cliente))
    ).scalar() or 0

    pontos_emitidos = compras_periodo.with_entities(
        func.coalesce(func.sum(Compra.pontos_gerados), 0)
    ).scalar() or 0
    resgates_periodo = Resgate.query.join(
        Cliente, Resgate.id_cliente == Cliente.id_cliente
    ).filter(
        Resgate.tipo_movimentacao == "RESGATE",
        Resgate.data >= inicio_periodo,
        Cliente.nivel_acesso == "CLIENTE",
    )
    quantidade_resgates = resgates_periodo.count()
    pontos_resgatados = resgates_periodo.with_entities(
        func.coalesce(func.sum(func.abs(Resgate.pontos_utilizados)), 0)
    ).scalar() or 0

    frequencia_recompra = quantidade_compras / clientes_ativos if clientes_ativos else 0.0
    indice_resgate = int(pontos_resgatados) / int(pontos_emitidos) * 100 if pontos_emitidos else 0.0

    rotatividade_aplicavel = dias >= 30
    clientes_com_compra_30_dias = Compra.query.join(
        Cliente, Compra.id_cliente == Cliente.id_cliente
    ).filter(
        Compra.tipo_movimentacao == "COMPRA",
        Compra.data >= agora - timedelta(days=30),
        Cliente.nivel_acesso == "CLIENTE",
    ).with_entities(
        func.count(func.distinct(Compra.id_cliente))
    ).scalar() or 0
    clientes_sem_compra_30_dias = max(
        total_clientes_cadastrados - int(clientes_com_compra_30_dias),
        0,
    )
    taxa_rotatividade = None
    if rotatividade_aplicavel:
        taxa_rotatividade = (
            clientes_sem_compra_30_dias / total_clientes_cadastrados * 100
            if total_clientes_cadastrados
            else 0.0
        )

    return jsonify({
        "periodo_dias": dias,
        "clientes_ativos": clientes_ativos,
        "total_clientes_cadastrados": total_clientes_cadastrados,
        "clientes_com_compra": int(clientes_com_compra),
        "clientes_com_compra_ultimos_30_dias": int(clientes_com_compra_30_dias),
        "clientes_sem_compra_ultimos_30_dias": clientes_sem_compra_30_dias,
        "quantidade_compras": quantidade_compras,
        "quantidade_resgates": quantidade_resgates,
        "pontos_emitidos": int(pontos_emitidos),
        "pontos_resgatados": int(pontos_resgatados),
        "frequencia_recompra": round(frequencia_recompra, 2),
        "rotatividade_aplicavel": rotatividade_aplicavel,
        "taxa_rotatividade": round(taxa_rotatividade, 2) if taxa_rotatividade is not None else None,
        "indice_resgate": round(indice_resgate, 2),
    })


@main_bp.route("/clientes")
@vendedora_required
def v_clientes():
    return render_template("vendedora/clientes.html")


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


@main_bp.route("/perfil")
@cliente_required
def perfil():
    return render_template("clientes/perfil.html")


@main_bp.route("/cliente/trocar-senha")
@cliente_required
def cliente_trocar_senha():
    return render_template("clientes/trocar_senha.html")


@main_bp.route("/trocar-senha")
def trocar_senha():
    if not current_user.is_authenticated:
        return redirect(url_for("main.index"))
    if getattr(current_user, "is_cliente", False):
        return redirect(url_for("main.cliente_trocar_senha"))
    elif getattr(current_user, "is_vendedora", False):
        return redirect(url_for("main.alterar_senha"))
    return redirect(url_for("main.index"))
