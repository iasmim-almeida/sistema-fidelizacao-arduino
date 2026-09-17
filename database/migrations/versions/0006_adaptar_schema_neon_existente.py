"""Adapta o schema Neon ja provisionado ao modelo da aplicacao."""

from alembic import op
import sqlalchemy as sa


revision = "0006_adaptar_neon"
down_revision = "0005_modelo_novo"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    usuario = {column["name"] for column in inspector.get_columns("usuario")}
    with op.batch_alter_table("usuario") as batch:
        if "cargo" not in usuario:
            batch.add_column(sa.Column("cargo", sa.String(30), nullable=False, server_default="proprietario"))
        if "ativo" not in usuario:
            batch.add_column(sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()))
        if "ultimo_login" not in usuario:
            batch.add_column(sa.Column("ultimo_login", sa.DateTime(), nullable=True))
        if "precisa_trocar_senha" not in usuario:
            batch.add_column(sa.Column("precisa_trocar_senha", sa.Boolean(), nullable=False, server_default=sa.false()))

    produto = {column["name"] for column in inspector.get_columns("produto")}
    with op.batch_alter_table("produto") as batch:
        if "id_usuario" not in produto:
            batch.add_column(sa.Column("id_usuario", sa.Integer(), nullable=True))
        if "custo_pontos" not in produto:
            batch.add_column(sa.Column("custo_pontos", sa.Integer(), nullable=False, server_default="1"))
        if "tipo" not in produto:
            batch.add_column(sa.Column("tipo", sa.String(30), nullable=False, server_default="produto_fisico"))
        if "valor_beneficio" not in produto:
            batch.add_column(sa.Column("valor_beneficio", sa.Numeric(10, 2), nullable=True))
        if "quantidade_total" not in produto:
            batch.add_column(sa.Column("quantidade_total", sa.Integer(), nullable=True))
        if "quantidade_disponivel" not in produto:
            batch.add_column(sa.Column("quantidade_disponivel", sa.Integer(), nullable=True))
        if "status" not in produto:
            batch.add_column(sa.Column("status", sa.String(10), nullable=False, server_default="ativa"))
        if "created_at" not in produto:
            batch.add_column(sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()))
        if "updated_at" not in produto:
            batch.add_column(sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()))

    historico = {column["name"] for column in inspector.get_columns("historico")}
    with op.batch_alter_table("historico") as batch:
        if "valor_compra" not in historico:
            batch.add_column(sa.Column("valor_compra", sa.Numeric(10, 2), nullable=True))
        if "saldo_anterior" not in historico:
            batch.add_column(sa.Column("saldo_anterior", sa.Integer(), nullable=True))
        if "saldo_posterior" not in historico:
            batch.add_column(sa.Column("saldo_posterior", sa.Integer(), nullable=True))
        if "origem" not in historico:
            batch.add_column(sa.Column("origem", sa.String(50), nullable=True))

    if "auditoria" not in inspector.get_table_names():
        op.create_table(
            "auditoria",
            sa.Column("id_auditoria", sa.Integer(), primary_key=True),
            sa.Column("id_usuario", sa.Integer(), sa.ForeignKey("usuario.id_usuario", ondelete="SET NULL"), nullable=True),
            sa.Column("acao", sa.String(50), nullable=False),
            sa.Column("entidade", sa.String(50), nullable=False),
            sa.Column("entidade_id", sa.String(50), nullable=True),
            sa.Column("detalhes", sa.Text(), nullable=True),
            sa.Column("ip", sa.String(45), nullable=True),
            sa.Column("user_agent", sa.String(255), nullable=True),
            sa.Column("data_hora", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )


def downgrade():
    raise RuntimeError("A adaptacao do schema Neon deve ser revertida manualmente apos backup.")
