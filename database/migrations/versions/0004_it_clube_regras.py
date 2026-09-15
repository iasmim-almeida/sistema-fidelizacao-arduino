"""Migracao de regras de negocio IT Clube - Desacoplamento financeiro e autoatendimento de cliente.

Revision ID: 0004_it_clube_regras
Revises: 0003_evolucao
Create Date: 2026-09-15
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_it_clube_regras"
down_revision = "0003_evolucao"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Garantir campo de email com unicidade na tabela cliente
    with op.batch_alter_table("cliente") as batch_op:
        # Se a coluna email já existe no SQLite local, criamos o índice único
        try:
            batch_op.create_unique_constraint("uq_cliente_email", ["email"])
        except Exception:
            pass

    # 2. Atualizar server default de pontos_gerados na tabela compra para 1 (Regra IT Clube: 1 compra = 1 ponto)
    with op.batch_alter_table("compra") as batch_op:
        try:
            batch_op.alter_column(
                "pontos_gerados",
                existing_type=sa.Integer(),
                server_default="1",
                nullable=False
            )
        except Exception:
            pass


def downgrade():
    with op.batch_alter_table("compra") as batch_op:
        try:
            batch_op.alter_column(
                "pontos_gerados",
                existing_type=sa.Integer(),
                server_default=None,
                nullable=False
            )
        except Exception:
            pass

    with op.batch_alter_table("cliente") as batch_op:
        try:
            batch_op.drop_constraint("uq_cliente_email", type_="unique")
        except Exception:
            pass
