"""Evolucao do modelo de funcionarios, RBAC, soft delete, ledger de pontos e auditoria.

Revision ID: 0003_evolucao
Revises: 0002_recompensas
Create Date: 2026-09-05
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_evolucao"
down_revision = "0002_recompensas"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Atualizacao da tabela usuario
    with op.batch_alter_table("usuario") as batch_op:
        batch_op.add_column(
            sa.Column("cargo", sa.String(30), nullable=False, server_default="proprietario")
        )
        batch_op.add_column(
            sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch_op.add_column(
            sa.Column("data_cadastro", sa.DateTime(), nullable=False, server_default=sa.func.now())
        )
        batch_op.add_column(
            sa.Column("ultimo_login", sa.DateTime(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("precisa_trocar_senha", sa.Boolean(), nullable=False, server_default=sa.false())
        )

    # 2. Atualizacao da tabela cliente (soft delete)
    with op.batch_alter_table("cliente") as batch_op:
        batch_op.add_column(
            sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true())
        )

    # 3. Criacao da tabela movimentacao_pontos (Ledger transacional)
    op.create_table(
        "movimentacao_pontos",
        sa.Column("id_movimentacao", sa.Integer(), primary_key=True),
        sa.Column(
            "id_cliente",
            sa.Integer(),
            sa.ForeignKey("cliente.id_cliente", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tipo", sa.String(30), nullable=False),
        sa.Column("quantidade", sa.Integer(), nullable=False),
        sa.Column("saldo_anterior", sa.Integer(), nullable=False),
        sa.Column("saldo_posterior", sa.Integer(), nullable=False),
        sa.Column("origem", sa.String(50), nullable=False, server_default="sistema"),
        sa.Column("motivo", sa.String(255), nullable=True),
        sa.Column(
            "id_usuario",
            sa.Integer(),
            sa.ForeignKey("usuario.id_usuario", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "id_compra",
            sa.Integer(),
            sa.ForeignKey("compra.id_compra", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "id_resgate",
            sa.Integer(),
            sa.ForeignKey("resgate.id_resgate", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "id_recompensa",
            sa.Integer(),
            sa.ForeignKey("recompensa.id_recompensa", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("data_hora", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_movimentacao_pontos_id_cliente", "movimentacao_pontos", ["id_cliente"])
    op.create_index("ix_movimentacao_pontos_tipo", "movimentacao_pontos", ["tipo"])
    op.create_index("ix_movimentacao_pontos_id_usuario", "movimentacao_pontos", ["id_usuario"])
    op.create_index("ix_movimentacao_pontos_id_compra", "movimentacao_pontos", ["id_compra"])
    op.create_index("ix_movimentacao_pontos_id_resgate", "movimentacao_pontos", ["id_resgate"])
    op.create_index("ix_movimentacao_pontos_id_recompensa", "movimentacao_pontos", ["id_recompensa"])
    op.create_index("ix_movimentacao_pontos_data_hora", "movimentacao_pontos", ["data_hora"])

    # 4. Criacao da tabela auditoria
    op.create_table(
        "auditoria",
        sa.Column("id_auditoria", sa.Integer(), primary_key=True),
        sa.Column(
            "id_usuario",
            sa.Integer(),
            sa.ForeignKey("usuario.id_usuario", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("acao", sa.String(50), nullable=False),
        sa.Column("entidade", sa.String(50), nullable=False),
        sa.Column("entidade_id", sa.String(50), nullable=True),
        sa.Column("detalhes", sa.Text(), nullable=True),
        sa.Column("ip", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("data_hora", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_auditoria_id_usuario", "auditoria", ["id_usuario"])
    op.create_index("ix_auditoria_acao", "auditoria", ["acao"])
    op.create_index("ix_auditoria_entidade", "auditoria", ["entidade"])
    op.create_index("ix_auditoria_entidade_id", "auditoria", ["entidade_id"])
    op.create_index("ix_auditoria_data_hora", "auditoria", ["data_hora"])


def downgrade():
    op.drop_index("ix_auditoria_data_hora", table_name="auditoria")
    op.drop_index("ix_auditoria_entidade_id", table_name="auditoria")
    op.drop_index("ix_auditoria_entidade", table_name="auditoria")
    op.drop_index("ix_auditoria_acao", table_name="auditoria")
    op.drop_index("ix_auditoria_id_usuario", table_name="auditoria")
    op.drop_table("auditoria")

    op.drop_index("ix_movimentacao_pontos_data_hora", table_name="movimentacao_pontos")
    op.drop_index("ix_movimentacao_pontos_id_recompensa", table_name="movimentacao_pontos")
    op.drop_index("ix_movimentacao_pontos_id_resgate", table_name="movimentacao_pontos")
    op.drop_index("ix_movimentacao_pontos_id_compra", table_name="movimentacao_pontos")
    op.drop_index("ix_movimentacao_pontos_id_usuario", table_name="movimentacao_pontos")
    op.drop_index("ix_movimentacao_pontos_tipo", table_name="movimentacao_pontos")
    op.drop_index("ix_movimentacao_pontos_id_cliente", table_name="movimentacao_pontos")
    op.drop_table("movimentacao_pontos")

    with op.batch_alter_table("cliente") as batch_op:
        batch_op.drop_column("ativo")

    with op.batch_alter_table("usuario") as batch_op:
        batch_op.drop_column("precisa_trocar_senha")
        batch_op.drop_column("ultimo_login")
        batch_op.drop_column("data_cadastro")
        batch_op.drop_column("ativo")
        batch_op.drop_column("cargo")
