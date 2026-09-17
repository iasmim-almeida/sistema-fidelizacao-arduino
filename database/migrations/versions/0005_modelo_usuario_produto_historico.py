"""Consolida o banco em usuario, produto e historico."""

from alembic import op
import sqlalchemy as sa


revision = "0005_modelo_novo"
down_revision = "0004_it_clube_regras"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    existentes = set(sa.inspect(bind).get_table_names())
    antigos = {
        "usuario": "usuario_legado",
        "cliente": "cliente_legado",
        "recompensa": "produto_legado",
        "compra": "compra_legado",
        "resgate": "resgate_legado",
        "movimentacao_pontos": "movimentacao_legado",
        "auditoria": "auditoria_legado",
    }
    for origem, destino in antigos.items():
        if origem in existentes:
            op.rename_table(origem, destino)

    op.create_table(
        "usuario",
        sa.Column("id_usuario", sa.Integer(), primary_key=True),
        sa.Column("telefone", sa.String(20), unique=True),
        sa.Column("nome", sa.String(100), nullable=False),
        sa.Column("email", sa.String(100), unique=True),
        sa.Column("endereco", sa.String(255)),
        sa.Column("data_cadastro", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("pontos_acumulados", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("login", sa.String(50), nullable=False, unique=True),
        sa.Column("senha_hash", sa.String(255), nullable=False),
        sa.Column("nivel_acesso", sa.String(20), nullable=False),
        sa.Column("cargo", sa.String(30), nullable=False, server_default="proprietario"),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("ultimo_login", sa.DateTime()),
        sa.Column("precisa_trocar_senha", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.CheckConstraint("pontos_acumulados >= 0", name="chk_usuario_pontos"),
        sa.CheckConstraint("nivel_acesso IN ('CLIENTE', 'ADMIN')", name="chk_usuario_nivel"),
    )
    op.create_table(
        "produto",
        sa.Column("id_produto", sa.Integer(), primary_key=True),
        sa.Column("id_usuario", sa.Integer(), sa.ForeignKey("usuario.id_usuario", ondelete="SET NULL")),
        sa.Column("nome_cupom", sa.String(100), nullable=False),
        sa.Column("descricao", sa.String(255)),
        sa.Column("codigo", sa.String(50), nullable=False, unique=True),
        sa.Column("validade", sa.Date(), nullable=False),
        sa.Column("custo_pontos", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(30), nullable=False, server_default="produto_fisico"),
        sa.Column("valor_beneficio", sa.Numeric(10, 2)),
        sa.Column("quantidade_total", sa.Integer()),
        sa.Column("quantidade_disponivel", sa.Integer()),
        sa.Column("status", sa.String(10), nullable=False, server_default="ativa"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "historico",
        sa.Column("id_historico", sa.Integer(), primary_key=True),
        sa.Column("id_usuario", sa.Integer(), sa.ForeignKey("usuario.id_usuario", ondelete="CASCADE"), nullable=False),
        sa.Column("id_produto", sa.Integer(), sa.ForeignKey("produto.id_produto", ondelete="SET NULL")),
        sa.Column("tipo_movimentacao", sa.String(20), nullable=False),
        sa.Column("data_movimentacao", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("pontos", sa.Integer(), nullable=False),
        sa.Column("descricao", sa.String(255)),
        sa.Column("valor_compra", sa.Numeric(10, 2)),
        sa.Column("saldo_anterior", sa.Integer()),
        sa.Column("saldo_posterior", sa.Integer()),
        sa.Column("origem", sa.String(50)),
        sa.CheckConstraint("tipo_movimentacao IN ('COMPRA', 'RESGATE', 'AJUSTE_POSITIVO', 'AJUSTE_NEGATIVO', 'ESTORNO', 'EXPIRACAO')", name="chk_historico_tipo"),
    )
    op.create_table(
        "auditoria",
        sa.Column("id_auditoria", sa.Integer(), primary_key=True),
        sa.Column("id_usuario", sa.Integer(), sa.ForeignKey("usuario.id_usuario", ondelete="SET NULL")),
        sa.Column("acao", sa.String(50), nullable=False),
        sa.Column("entidade", sa.String(50), nullable=False),
        sa.Column("entidade_id", sa.String(50)),
        sa.Column("detalhes", sa.Text()),
        sa.Column("ip", sa.String(45)),
        sa.Column("user_agent", sa.String(255)),
        sa.Column("data_hora", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    bind.execute(sa.text("""
        INSERT INTO usuario (nome, email, data_cadastro, login, senha_hash, nivel_acesso, cargo, ativo, ultimo_login, precisa_trocar_senha, pontos_acumulados)
        SELECT nome, email, COALESCE(data_cadastro, CURRENT_TIMESTAMP), login, senha_hash,
               'ADMIN', COALESCE(cargo, 'proprietario'), COALESCE(ativo, TRUE), ultimo_login,
               COALESCE(precisa_trocar_senha, FALSE), 0
        FROM usuario_legado
    """))
    bind.execute(sa.text("""
        INSERT INTO usuario (nome, telefone, email, endereco, data_cadastro, pontos_acumulados, login, senha_hash, nivel_acesso, cargo, ativo)
        SELECT c.nome, c.telefone, c.email, c.endereco, COALESCE(c.data_cadastro, CURRENT_TIMESTAMP), c.pontos_acumulados,
               'cliente_' || c.id_cliente,
               COALESCE(c.senha_hash, '!cliente_sem_senha!'), 'CLIENTE', 'cliente', COALESCE(c.ativo, TRUE)
        FROM cliente_legado c
    """))
    bind.execute(sa.text("""
        INSERT INTO produto (id_produto, id_usuario, nome_cupom, descricao, codigo, validade, custo_pontos, tipo, valor_beneficio, quantidade_total, quantidade_disponivel, status, created_at, updated_at)
         SELECT id_recompensa,
             (SELECT u.id_usuario FROM usuario_legado ul JOIN usuario u ON u.login = ul.login WHERE ul.id_usuario = r.id_usuario),
             r.nome, NULL, 'RECOMPENSA-' || r.id_recompensa, r.validade, r.custo_pontos, r.tipo, r.valor_beneficio,
             r.quantidade_total, r.quantidade_disponivel, r.status, r.created_at, r.updated_at
         FROM produto_legado r
    """))
    bind.execute(sa.text("""
        INSERT INTO historico (id_usuario, tipo_movimentacao, data_movimentacao, pontos, descricao, valor_compra, saldo_anterior, saldo_posterior, origem)
        SELECT u.id_usuario, 'COMPRA', c.data, c.pontos_gerados, 'Compra migrada', c.valor, NULL, NULL, 'migracao'
        FROM compra_legado c
        JOIN cliente_legado cl ON cl.id_cliente = c.id_cliente
        JOIN usuario u ON u.telefone = cl.telefone AND u.nivel_acesso = 'CLIENTE'
    """))
    bind.execute(sa.text("""
        INSERT INTO historico (id_usuario, id_produto, tipo_movimentacao, data_movimentacao, pontos, descricao, origem)
        SELECT u.id_usuario, r.id_recompensa, 'RESGATE', r.data, -r.pontos_utilizados, r.descricao_recompensa, 'migracao'
        FROM resgate_legado r
        JOIN cliente_legado cl ON cl.id_cliente = r.id_cliente
        JOIN usuario u ON u.telefone = cl.telefone AND u.nivel_acesso = 'CLIENTE'
    """))
    bind.execute(sa.text("""
        INSERT INTO historico (id_usuario, id_produto, tipo_movimentacao, data_movimentacao, pontos, descricao, saldo_anterior, saldo_posterior, origem)
        SELECT u.id_usuario, mp.id_recompensa, mp.tipo, mp.data_hora, mp.quantidade, mp.motivo, mp.saldo_anterior, mp.saldo_posterior, mp.origem
        FROM movimentacao_legado mp
        JOIN cliente_legado cl ON cl.id_cliente = mp.id_cliente
        JOIN usuario u ON u.telefone = cl.telefone AND u.nivel_acesso = 'CLIENTE'
        WHERE mp.tipo NOT IN ('COMPRA', 'RESGATE')
    """))
    bind.execute(sa.text("""
        INSERT INTO auditoria (id_auditoria, id_usuario, acao, entidade, entidade_id, detalhes, ip, user_agent, data_hora)
        SELECT id_auditoria, id_usuario, acao, entidade, entidade_id, detalhes, ip, user_agent, data_hora
        FROM auditoria_legado
    """))
    if bind.dialect.name == "postgresql":
        bind.execute(sa.text("""
            SELECT setval(
                pg_get_serial_sequence('usuario', 'id_usuario'),
                COALESCE((SELECT MAX(id_usuario) FROM usuario), 1),
                true
            )
        """))
        bind.execute(sa.text("""
            SELECT setval(
                pg_get_serial_sequence('produto', 'id_produto'),
                COALESCE((SELECT MAX(id_produto) FROM produto), 1),
                true
            )
        """))
        bind.execute(sa.text("""
            SELECT setval(
                pg_get_serial_sequence('historico', 'id_historico'),
                COALESCE((SELECT MAX(id_historico) FROM historico), 1),
                true
            )
        """))
    for tabela in (
        "movimentacao_legado",
        "resgate_legado",
        "compra_legado",
        "produto_legado",
        "cliente_legado",
        "usuario_legado",
    ):
        op.drop_table(tabela)


def downgrade():
    raise RuntimeError("A migracao 0005 e irreversivel automaticamente; restaure o backup do banco legado.")
