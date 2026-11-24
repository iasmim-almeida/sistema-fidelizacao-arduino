"""Remove a coluna valor_compra da tabela historico.

Regra IT Clube: 1 compra = 1 ponto. Valores monetarios foram descontinuados
de ponta a ponta na aplicacao, nao interferindo na pontuacao e nao sendo persistidos.
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_remover_valor_compra"
down_revision = "0006_adaptar_neon"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tabelas = inspector.get_table_names()

    if "historico" in tabelas:
        colunas_historico = {c["name"] for c in inspector.get_columns("historico")}
        if "valor_compra" in colunas_historico:
            with op.batch_alter_table("historico") as batch:
                batch.drop_column("valor_compra")


def downgrade():
    raise RuntimeError(
        "A remoção de historico.valor_compra é irreversível sem restauração de backup. "
        "Recriar apenas a coluna não recuperaria os valores removidos."
    )
