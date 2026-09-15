"""Adiciona recompensas persistentes e vincula resgates.

Revision ID: 0002_recompensas
Revises: 0001_schema_legado
Create Date: 2026-09-03
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_recompensas"
down_revision = "0001_schema_legado"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "recompensa",
        sa.Column("id_recompensa", sa.Integer(), primary_key=True),
        sa.Column(
            "id_usuario",
            sa.Integer(),
            sa.ForeignKey("usuario.id_usuario", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("custo_pontos", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(30), nullable=False),
        sa.Column("valor_beneficio", sa.Numeric(10, 2), nullable=True),
        sa.Column("validade", sa.Date(), nullable=False),
        sa.Column("quantidade_total", sa.Integer(), nullable=False),
        sa.Column("quantidade_disponivel", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="ativa"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("custo_pontos > 0", name="ck_recompensa_custo_positivo"),
        sa.CheckConstraint(
            "tipo IN ('produto_fisico', 'desconto_percentual', 'desconto_valor_fixo')",
            name="ck_recompensa_tipo",
        ),
        sa.CheckConstraint("status IN ('ativa', 'pausada')", name="ck_recompensa_status"),
        sa.CheckConstraint("quantidade_total >= 0", name="ck_recompensa_quantidade_total"),
        sa.CheckConstraint(
            "quantidade_disponivel >= 0 AND quantidade_disponivel <= quantidade_total",
            name="ck_recompensa_quantidade_disponivel",
        ),
        sa.CheckConstraint(
            "(tipo = 'produto_fisico' AND valor_beneficio IS NULL) OR "
            "(tipo = 'desconto_percentual' AND valor_beneficio > 0 AND valor_beneficio <= 100) OR "
            "(tipo = 'desconto_valor_fixo' AND valor_beneficio > 0)",
            name="ck_recompensa_valor_beneficio",
        ),
    )
    op.create_index("ix_recompensa_id_usuario", "recompensa", ["id_usuario"])
    op.create_index("ix_recompensa_status", "recompensa", ["status"])
    op.create_index("ix_recompensa_validade", "recompensa", ["validade"])

    with op.batch_alter_table("resgate") as batch_op:
        batch_op.add_column(sa.Column("id_recompensa", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_resgate_recompensa",
            "recompensa",
            ["id_recompensa"],
            ["id_recompensa"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_resgate_id_recompensa", ["id_recompensa"])


def downgrade():
    with op.batch_alter_table("resgate") as batch_op:
        batch_op.drop_index("ix_resgate_id_recompensa")
        batch_op.drop_constraint("fk_resgate_recompensa", type_="foreignkey")
        batch_op.drop_column("id_recompensa")

    op.drop_index("ix_recompensa_validade", table_name="recompensa")
    op.drop_index("ix_recompensa_status", table_name="recompensa")
    op.drop_index("ix_recompensa_id_usuario", table_name="recompensa")
    op.drop_table("recompensa")
