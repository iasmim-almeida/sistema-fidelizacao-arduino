"""Popula o banco: usuario admin (login por e-mail) + clientes de exemplo com senha e compras."""
from decimal import Decimal
from datetime import datetime, timedelta
from app import create_app
from app.extensions import db
from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.models.compra import Compra
from app.models.resgate import Resgate

app = create_app()

with app.app_context():
    # Recria as tabelas para garantir a nova coluna senha_hash
    db.drop_all()
    db.create_all()

    # 1. Usuário Gestor / Vendedora (Admin)
    admin = Usuario(
        nome="Camila Vendedora (Admin)",
        login="admin",
        email="admin@loja.com",
        nivel_acesso="gestor",
    )
    admin.set_senha("1234")
    db.session.add(admin)
    print("Vendedora admin@loja.com criada (senha: 1234)")

    # 2. Clientes Exemplo com Senha e Histórico
    exemplos = [
        ("Ana Silva", "11999991111", "ana@ex.com", 280),
        ("Carlos Oliveira", "11988882222", "carlos@ex.com", 160),
    ]

    for nome, tel, email, pts in exemplos:
        cli = Cliente(nome=nome, telefone=tel, email=email, pontos_acumulados=pts)
        cli.set_senha("1234")
        db.session.add(cli)
        db.session.flush()

        # Histórico de demonstração para Ana Silva
        if tel == "11999991111":
            c1 = Compra(
                id_cliente=cli.id_cliente,
                valor=Decimal("150.00"),
                pontos_gerados=150,
                data=datetime.utcnow() - timedelta(days=5),
            )
            c2 = Compra(
                id_cliente=cli.id_cliente,
                valor=Decimal("180.00"),
                pontos_gerados=180,
                data=datetime.utcnow() - timedelta(days=2),
            )
            r1 = Resgate(
                id_cliente=cli.id_cliente,
                pontos_utilizados=50,
                descricao_recompensa="Brinde Simples",
                data=datetime.utcnow() - timedelta(days=1),
            )
            db.session.add_all([c1, c2, r1])

        # Histórico de demonstração para Carlos Oliveira
        if tel == "11988882222":
            c3 = Compra(
                id_cliente=cli.id_cliente,
                valor=Decimal("160.00"),
                pontos_gerados=160,
                data=datetime.utcnow() - timedelta(days=3),
            )
            db.session.add(c3)

        print(f"Cliente {nome} ({tel}) criado (senha: 1234)")

    db.session.commit()
    print("Seed concluído com sucesso!")
