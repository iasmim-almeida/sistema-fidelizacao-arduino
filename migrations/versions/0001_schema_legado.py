"""Registra o schema legado do FideliZa.

Revision ID: 0001_schema_legado
Revises:
Create Date: 2026-09-03

Esta revisão é tolerante a tabelas já existentes para que bancos criados antes
da adoção do Alembic possam executar ``flask db upgrade`` sem perder dados.
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_schema_legado"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    existentes = set(sa.inspect(op.get_bind()).get_table_names())

    if "usuario" not in existentes:
        op.create_table(
            "usuario",
            sa.Column("id_usuario", sa.Integer(), primary_key=True),
            sa.Column("nome", sa.String(120), nullable=False),
            sa.Column("login", sa.String(80), nullable=False, unique=True),
            sa.Column("email", sa.String(120), nullable=True, unique=True),
            sa.Column("senha_hash", sa.String(255), nullable=False),
            sa.Column("nivel_acesso", sa.String(20), nullable=False, server_default="gestor"),
        )

    if "cliente" not in existentes:
        op.create_table(
            "cliente",
            sa.Column("id_cliente", sa.Integer(), primary_key=True),
            sa.Column("nome", sa.String(120), nullable=False),
            sa.Column("telefone", sa.String(20), nullable=False, unique=True),
            sa.Column("email", sa.String(120), nullable=True, unique=True),
            sa.Column("endereco", sa.String(200), nullable=True),
            sa.Column("senha_hash", sa.String(255), nullable=True),
            sa.Column("data_cadastro", sa.DateTime(), nullable=True),
            sa.Column("pontos_acumulados", sa.Integer(), nullable=False, server_default="0"),
        )

    if "compra" not in existentes:
        op.create_table(
            "compra",
            sa.Column("id_compra", sa.Integer(), primary_key=True),
            sa.Column("id_cliente", sa.Integer(), sa.ForeignKey("cliente.id_cliente"), nullable=False),
            sa.Column("data", sa.DateTime(), nullable=True),
            sa.Column("valor", sa.Numeric(10, 2), nullable=False),
            sa.Column("pontos_gerados", sa.Integer(), nullable=False, server_default="0"),
        )

    if "resgate" not in existentes:
        op.create_table(
            "resgate",
            sa.Column("id_resgate", sa.Integer(), primary_key=True),
            sa.Column("id_cliente", sa.Integer(), sa.ForeignKey("cliente.id_cliente"), nullable=False),
            sa.Column("data", sa.DateTime(), nullable=True),
            sa.Column("pontos_utilizados", sa.Integer(), nullable=False),
            sa.Column("descricao_recompensa", sa.String(200), nullable=False),
        )


def downgrade():
    op.drop_table("resgate")
    op.drop_table("compra")
    op.drop_table("cliente")
    op.drop_table("usuario")
