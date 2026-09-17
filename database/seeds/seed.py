"""Carga inicial segura para testes do IT Clube."""

import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app import create_app
from app.extensions import db
from app.models.auditoria import Auditoria
from app.models.usuario import Usuario


ADMIN_LOGIN = "admin"
ADMIN_PASSWORD = "ITClube2026"
CLIENT_LOGIN = "ana.silva"
CLIENT_PASSWORD = "ITClube2026"


def obter_ou_criar_usuario(login: str, **dados) -> Usuario:
    usuario = Usuario.query.filter_by(login=login).first()
    if usuario is None:
        usuario = Usuario(login=login, **dados)
        db.session.add(usuario)
    else:
        for campo, valor in dados.items():
            setattr(usuario, campo, valor)
    return usuario


app = create_app("production")
with app.app_context():
    admin = obter_ou_criar_usuario(
        ADMIN_LOGIN,
        nome="Administrador IT Clube",
        email="admin@loja.com",
        nivel_acesso="ADMIN",
        cargo="proprietario",
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

    db.session.flush()
    if not Auditoria.query.filter_by(
        acao="SEED_DEMONSTRACAO",
        entidade="usuario",
        entidade_id=str(ana.id_usuario),
    ).first():
        db.session.add(Auditoria(
            id_usuario=admin.id_usuario,
            acao="SEED_DEMONSTRACAO",
            entidade="usuario",
            entidade_id=str(ana.id_usuario),
            detalhes='{"conta": "Ana Silva", "pontos": 280}',
        ))

    db.session.commit()
    print("Administrador: login=admin senha=ITClube2026")
    print("Cliente: login=ana.silva senha=ITClube2026 telefone=11999991111 pontos=280")
