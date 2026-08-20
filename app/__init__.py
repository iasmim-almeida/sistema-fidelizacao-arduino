import os
from flask import Flask, jsonify, request, redirect
from app.config import config_by_name
from app.extensions import db, login_manager, migrate

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")


def create_app(config_name: str = "development") -> Flask:
    app = Flask(
        __name__,
        template_folder=os.path.join(FRONTEND_DIR, "templates"),
        static_folder=os.path.join(FRONTEND_DIR, "static"),
    )
    app.config.from_object(config_by_name[config_name])

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    # Se rota /api nao autenticada -> 401 JSON; senao redireciona ao login
    @login_manager.unauthorized_handler
    def unauthorized():
        if request.path.startswith("/api") or request.path.startswith("/auth"):
            return jsonify({"erro": "Nao autenticado"}), 401
        return redirect("/")

    from app.models import cliente, compra, resgate, usuario  # noqa: F401

    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.clientes import clientes_bp
    from app.routes.compras import compras_bp
    from app.routes.resgates import resgates_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(clientes_bp, url_prefix="/api/clientes")
    app.register_blueprint(compras_bp, url_prefix="/api/compras")
    app.register_blueprint(resgates_bp, url_prefix="/api/resgates")

    return app
