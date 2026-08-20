from flask import Blueprint, render_template, redirect

main_bp = Blueprint("main", __name__)


# ---------- Entrada / Login ----------
@main_bp.route("/")
def index():
    return render_template("login.html")


@main_bp.route("/health")
def health():
    return {"status": "ok"}


# ---------- Area da VENDEDORA ----------
@main_bp.route("/dashboard")
def dashboard():
    return render_template("vendedora/dashboard.html")


@main_bp.route("/clientes")
def v_clientes():
    return render_template("vendedora/clientes.html")


@main_bp.route("/pontuar")
def pontuar():
    return render_template("vendedora/pontos.html")


@main_bp.route("/resgate")
def resgate():
    return render_template("vendedora/resgate.html")


@main_bp.route("/relatorios")
def relatorios():
    return render_template("vendedora/relatorios.html")


# ---------- Area do CLIENTE ----------
@main_bp.route("/bemvindo")
def bemvindo():
    return render_template("clientes/bemvindo.html")


@main_bp.route("/meuspontos")
def meuspontos():
    return render_template("clientes/meuspontos.html")


@main_bp.route("/recompensas")
def recompensas():
    return render_template("clientes/recompensas.html")


@main_bp.route("/historico")
def historico():
    return render_template("clientes/historico.html")
