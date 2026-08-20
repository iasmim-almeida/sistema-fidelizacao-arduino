"""Popula o banco: usuario admin (login por e-mail) + clientes de exemplo."""
from app import create_app
from app.extensions import db
from app.models.usuario import Usuario
from app.models.cliente import Cliente

app = create_app()

with app.app_context():
    db.create_all()

    if not Usuario.query.filter_by(email="admin@loja.com").first():
        u = Usuario(nome="Administrador", login="admin",
                    email="admin@loja.com", nivel_acesso="gestor")
        u.set_senha("1234")
        db.session.add(u)
        print("Usuario admin@loja.com criado (senha: 1234)")

    exemplos = [
        ("Ana Silva", "11999991111", "ana@ex.com", 280),
        ("Carlos Oliveira", "11988882222", "carlos@ex.com", 160),
    ]
    for nome, tel, email, pts in exemplos:
        if not Cliente.query.filter_by(telefone=tel).first():
            db.session.add(Cliente(nome=nome, telefone=tel, email=email, pontos_acumulados=pts))
            print(f"Cliente {nome} criado")

    db.session.commit()
    print("Seed concluido.")
