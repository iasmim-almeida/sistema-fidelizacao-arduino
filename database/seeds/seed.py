"""Carga inicial segura para testes do IT Clube."""

import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app import create_app
from app.extensions import db
from app.models.usuario import Usuario


ADMIN_LOGIN = os.getenv("SEED_ADMIN_LOGIN", "vendedora")
ADMIN_PASSWORD = os.getenv("SEED_ADMIN_PASSWORD", "")
CLIENT_LOGIN = os.getenv("SEED_CLIENT_LOGIN", "ana.silva")
CLIENT_PASSWORD = os.getenv("SEED_CLIENT_PASSWORD", "")


def obter_ou_criar_usuario(login: str, **dados) -> Usuario:
    usuario = Usuario.query.filter_by(login=login).first()
    if usuario is None:
        usuario = Usuario(login=login, **dados)
        db.session.add(usuario)
    else:
        for campo, valor in dados.items():
            setattr(usuario, campo, valor)
    return usuario


env = os.getenv("FLASK_ENV", "development").lower()

if env == "production":
    print("ERRO DE SEGURANCA: Execucao de seeds de demonstracao bloqueada em ambiente de PRODUCAO!")
    print("Para criar a conta da vendedora/administradora de forma segura em producao, use:")
    print("  flask create-vendedora")
    print("Ou acesse a interface web em /setup no primeiro acesso.")
    sys.exit(1)

if not ADMIN_PASSWORD or not CLIENT_PASSWORD:
    print("ERRO: SEED_ADMIN_PASSWORD e SEED_CLIENT_PASSWORD sao obrigatorias para dados de demonstracao.")
    sys.exit(1)

app = create_app(env)
with app.app_context():
    admin = obter_ou_criar_usuario(
        ADMIN_LOGIN,
        nome="Vendedora Administradora",
        email="vendedora@itclube.com.br",
        nivel_acesso="ADMIN",
        cargo="vendedora",
        ativo=True,
    )
    admin.set_senha(ADMIN_PASSWORD)

    ana = obter_ou_criar_usuario(
        CLIENT_LOGIN,
        nome="Ana Silva",
        telefone="11999991111",
        email="ana@ex.com",
        nivel_acesso="CLIENTE",
        cargo="cliente",
        pontos_acumulados=280,
        ativo=True,
    )
    ana.set_senha(CLIENT_PASSWORD)
    ana.pontos_acumulados = 280

    db.session.commit()
    print(f"Carga de demonstracao finalizada com sucesso (ambiente: {env}).")
    print(f"Vendedora (Admin): login={ADMIN_LOGIN}")
    print(f"Cliente: login={CLIENT_LOGIN} telefone=11999991111 pontos=280")
