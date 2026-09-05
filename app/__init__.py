import os
from flask import Flask, jsonify, request, redirect
from flask_login import current_user
from flask_wtf.csrf import CSRFError
from app.config import config_by_name
from app.extensions import db, login_manager, migrate, csrf, limiter

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")


def create_app(config_name: str = "development") -> Flask:
    app = Flask(
        __name__,
        template_folder=os.path.join(FRONTEND_DIR, "templates"),
        static_folder=os.path.join(FRONTEND_DIR, "static"),
    )
    app.config.from_object(config_by_name.get(config_name, config_by_name["development"]))

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)

    # Alerta de segurança: SECRET_KEY padrão em uso
    if app.config.get("SECRET_KEY") == "dev-secret-key" and not app.config.get("TESTING"):
        import warnings
        warnings.warn(
            "⚠ SECRET_KEY esta usando o valor padrao 'dev-secret-key'. "
            "Defina uma chave segura via variavel de ambiente SECRET_KEY ou arquivo .env.",
            stacklevel=2,
        )

    # Se rota /api nao autenticada -> 401 JSON; senao redireciona ao login
    @login_manager.unauthorized_handler
    def unauthorized():
        if request.path.startswith("/api") or request.path.startswith("/auth"):
            return jsonify({"erro": "Nao autenticado"}), 401
        return redirect("/")

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        if request.path.startswith("/api"):
            if not current_user.is_authenticated:
                return jsonify({"erro": "Nao autenticado"}), 401
            return jsonify({"erro": "Token CSRF ausente ou invalido"}), 400
        if request.is_json:
            return jsonify({"erro": "Token CSRF ausente ou invalido"}), 400
        return error.description, 400

    @app.errorhandler(500)
    def internal_error(error):
        if request.path.startswith("/api") or request.path.startswith("/auth"):
            return jsonify({"erro": "Ocorreu um erro interno no servidor."}), 500
        return "Ocorreu um erro interno. Tente novamente mais tarde.", 500

    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if "Content-Security-Policy" not in response.headers:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
                "font-src 'self' https://cdnjs.cloudflare.com https://fonts.gstatic.com; "
                "img-src 'self' data:; "
                "connect-src 'self'; "
                "frame-ancestors 'self';"
            )
        return response

    from app.models import cliente, compra, recompensa, resgate, usuario, movimentacao_pontos, auditoria  # noqa: F401

    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.clientes import clientes_bp
    from app.routes.compras import compras_bp
    from app.routes.resgates import resgates_bp
    from app.routes.recompensas import recompensas_bp
    from app.routes.funcionarios import funcionarios_bp
    from app.routes.auditoria import auditoria_bp

    # O endpoint IoT ESP8266 precisa de isenção de CSRF para envio de pontuação via hardware
    csrf.exempt(compras_bp)

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(clientes_bp, url_prefix="/api/clientes")
    app.register_blueprint(compras_bp, url_prefix="/api/compras")
    app.register_blueprint(resgates_bp, url_prefix="/api/resgates")
    app.register_blueprint(recompensas_bp, url_prefix="/api/recompensas")
    app.register_blueprint(funcionarios_bp, url_prefix="/api/funcionarios")
    app.register_blueprint(auditoria_bp, url_prefix="/api/auditoria")

    return app
