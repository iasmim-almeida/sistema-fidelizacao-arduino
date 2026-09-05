"""Popula o banco com funcionarios em diferentes cargos, clientes, compras, ledger e recompensas."""
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from flask_migrate import stamp
from app import create_app
from app.extensions import db
from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.models.compra import Compra
from app.models.recompensa import Recompensa
from app.models.resgate import Resgate
from app.models.movimentacao_pontos import MovimentacaoPontos
from app.models.auditoria import Auditoria

app = create_app()

with app.app_context():
    print("ATENCAO: seed.py e destrutivo e recriara todas as tabelas da aplicacao.")
    db.drop_all()
    db.create_all()
    # Mantém o banco recriado alinhado ao head do Alembic.
    stamp()

    agora = datetime.now(timezone.utc).replace(tzinfo=None)

    # 1. Usuários Administrativos (Proprietário, Gerente, Vendedor)
    admin = Usuario(
        nome="Camila Vendedora (Admin)",
        login="admin",
        email="admin@loja.com",
        cargo="proprietario",
        nivel_acesso="gestor",
        ativo=True,
    )
    admin.set_senha("FideliZa2026")

    gerente = Usuario(
        nome="Gabriela Gerente",
        login="gerente",
        email="gerente@loja.com",
        cargo="gerente",
        nivel_acesso="gerente",
        ativo=True,
    )
    gerente.set_senha("FideliZa2026")

    vendedor = Usuario(
        nome="Vinicius Vendedor",
        login="vendedora",
        email="vendedora@loja.com",
        cargo="vendedor",
        nivel_acesso="vendedor",
        ativo=True,
    )
    vendedor.set_senha("FideliZa2026")

    db.session.add_all([admin, gerente, vendedor])
    db.session.flush()

    print(f"Proprietário criado: admin@loja.com (senha: FideliZa2026)")
    print(f"Gerente criada: gerente@loja.com (senha: FideliZa2026)")
    print(f"Vendedor criado: vendedora@loja.com (senha: FideliZa2026)")

    # 2. Recompensas de Exemplo
    recompensa_brinde = Recompensa(
        id_usuario=admin.id_usuario,
        nome="Brinde FideliZa",
        custo_pontos=50,
        tipo="produto_fisico",
        valor_beneficio=None,
        validade=(agora + timedelta(days=180)).date(),
        quantidade_total=10,
        quantidade_disponivel=9,
        status="ativa",
    )
    recompensa_desconto = Recompensa(
        id_usuario=admin.id_usuario,
        nome="15% de Desconto",
        custo_pontos=100,
        tipo="desconto_percentual",
        valor_beneficio=Decimal("15.00"),
        validade=(agora + timedelta(days=90)).date(),
        quantidade_total=20,
        quantidade_disponivel=20,
        status="ativa",
    )
    db.session.add_all([recompensa_brinde, recompensa_desconto])
    db.session.flush()

    # 3. Clientes Exemplo com Senha, Histórico e Ledger de Pontos
    exemplos = [
        ("Ana Silva", "11999991111", "ana@ex.com", 280),
        ("Carlos Oliveira", "11988882222", "carlos@ex.com", 160),
    ]

    for nome, tel, email, pts in exemplos:
        cli = Cliente(nome=nome, telefone=tel, email=email, pontos_acumulados=pts, ativo=True)
        cli.set_senha("FideliZa2026")
        db.session.add(cli)
        db.session.flush()

        # Histórico de demonstração para Ana Silva
        if tel == "11999991111":
            c1 = Compra(
                id_cliente=cli.id_cliente,
                valor=Decimal("150.00"),
                pontos_gerados=150,
                data=agora - timedelta(days=5),
            )
            c2 = Compra(
                id_cliente=cli.id_cliente,
                valor=Decimal("180.00"),
                pontos_gerados=180,
                data=agora - timedelta(days=2),
            )
            db.session.add_all([c1, c2])
            db.session.flush()

            m1 = MovimentacaoPontos(
                id_cliente=cli.id_cliente,
                tipo="COMPRA",
                quantidade=150,
                saldo_anterior=0,
                saldo_posterior=150,
                origem="vendedora",
                motivo="Compra no valor de R$ 150.00",
                id_usuario=vendedor.id_usuario,
                id_compra=c1.id_compra,
                data_hora=agora - timedelta(days=5),
            )
            m2 = MovimentacaoPontos(
                id_cliente=cli.id_cliente,
                tipo="COMPRA",
                quantidade=180,
                saldo_anterior=150,
                saldo_posterior=330,
                origem="vendedora",
                motivo="Compra no valor de R$ 180.00",
                id_usuario=vendedor.id_usuario,
                id_compra=c2.id_compra,
                data_hora=agora - timedelta(days=2),
            )
            db.session.add_all([m1, m2])
            db.session.flush()

            r1 = Resgate(
                id_cliente=cli.id_cliente,
                id_recompensa=recompensa_brinde.id_recompensa,
                pontos_utilizados=50,
                descricao_recompensa=recompensa_brinde.nome,
                data=agora - timedelta(days=1),
            )
            db.session.add(r1)
            db.session.flush()

            m3 = MovimentacaoPontos(
                id_cliente=cli.id_cliente,
                tipo="RESGATE",
                quantidade=-50,
                saldo_anterior=330,
                saldo_posterior=280,
                origem="vendedora",
                motivo=f"Resgate da recompensa: {recompensa_brinde.nome}",
                id_usuario=admin.id_usuario,
                id_resgate=r1.id_resgate,
                id_recompensa=recompensa_brinde.id_recompensa,
                data_hora=agora - timedelta(days=1),
            )
            db.session.add(m3)

        # Histórico de demonstração para Carlos Oliveira
        if tel == "11988882222":
            c3 = Compra(
                id_cliente=cli.id_cliente,
                valor=Decimal("160.00"),
                pontos_gerados=160,
                data=agora - timedelta(days=3),
            )
            db.session.add(c3)
            db.session.flush()

            m4 = MovimentacaoPontos(
                id_cliente=cli.id_cliente,
                tipo="COMPRA",
                quantidade=160,
                saldo_anterior=0,
                saldo_posterior=160,
                origem="iot_device",
                motivo="Compra via terminal ESP8266",
                id_compra=c3.id_compra,
                data_hora=agora - timedelta(days=3),
            )
            db.session.add(m4)

        print(f"Cliente {nome} ({tel}) criado com pontos e extrato (senha: FideliZa2026)")

    # 4. Logs Iniciais de Auditoria
    db.session.add_all([
        Auditoria(
            id_usuario=admin.id_usuario,
            acao="CRIAR_RECOMPENSA",
            entidade="recompensa",
            entidade_id=str(recompensa_brinde.id_recompensa),
            detalhes='{"nome": "Brinde FideliZa", "custo_pontos": 50}',
            data_hora=agora - timedelta(days=6),
        ),
        Auditoria(
            id_usuario=admin.id_usuario,
            acao="CRIAR_RECOMPENSA",
            entidade="recompensa",
            entidade_id=str(recompensa_desconto.id_recompensa),
            detalhes='{"nome": "15% de Desconto", "custo_pontos": 100}',
            data_hora=agora - timedelta(days=6),
        ),
        Auditoria(
            id_usuario=admin.id_usuario,
            acao="VALIDAR_RESGATE",
            entidade="resgate",
            entidade_id="1",
            detalhes='{"id_cliente": 1, "pontos": 50}',
            data_hora=agora - timedelta(days=1),
        ),
    ])

    db.session.commit()
    print("Seed concluído com sucesso!")
