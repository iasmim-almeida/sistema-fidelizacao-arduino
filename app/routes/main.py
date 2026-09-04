from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user
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
    return render_template("login.html")


@main_bp.route("/health")
def health():
    return {"status": "ok"}


@main_bp.route("/cadastro")
def cadastro():
    return redirect(url_for("auth.cadastrar_cliente_web"))


# ---------- Área da VENDEDORA (Administradora da Loja) ----------
@main_bp.route("/dashboard")
@vendedora_required
def dashboard():
    return render_template("vendedora/dashboard.html")


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


@main_bp.route("/relatorios")
@vendedora_required
def relatorios():
    return render_template("vendedora/relatorios.html")


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
