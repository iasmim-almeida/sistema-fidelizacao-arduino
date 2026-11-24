"""Consolida o schema operacional em usuario, produto e historico.

Remove as tabelas de auditoria operacional, corrige os índices declarados nos
models e adiciona suporte opcional a idempotência de compras. A exclusão das
tabelas de auditoria é uma decisão de requisito e exige backup antes de ser
aplicada em qualquer banco persistente.
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_consolidar_schema"
down_revision = "0007_remover_valor_compra"
branch_labels = None
depends_on = None


def _criar_indice_se_ausente(inspector, tabela, nome, colunas, unique=False):
    existentes = {indice["name"] for indice in inspector.get_indexes(tabela)}
    if nome not in existentes:
        op.create_index(nome, tabela, colunas, unique=unique)


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tabelas = set(inspector.get_table_names())

    if "historico" in tabelas:
        colunas = {coluna["name"] for coluna in inspector.get_columns("historico")}
        if "chave_idempotencia" not in colunas:
            with op.batch_alter_table("historico") as batch:
                batch.add_column(sa.Column("chave_idempotencia", sa.String(128), nullable=True))

    inspector = sa.inspect(bind)
    tabelas = set(inspector.get_table_names())

    if "produto" in tabelas:
        checks_existentes = {
            check.get("name") for check in inspector.get_check_constraints("produto")
        }
        checks_produto = {
            "chk_produto_custo": "custo_pontos > 0",
            "chk_produto_tipo": (
                "tipo IN ('produto_fisico', 'desconto_percentual', 'desconto_valor_fixo')"
            ),
            "chk_produto_status": "status IN ('ativa', 'pausada')",
            "chk_produto_quantidade_total": (
                "quantidade_total IS NULL OR quantidade_total >= 0"
            ),
            "chk_produto_quantidade_disponivel": (
                "quantidade_disponivel IS NULL OR "
                "(quantidade_disponivel >= 0 AND "
                "(quantidade_total IS NULL OR quantidade_disponivel <= quantidade_total))"
            ),
            "chk_produto_valor_beneficio": (
                "(tipo = 'produto_fisico' AND valor_beneficio IS NULL) OR "
                "(tipo = 'desconto_percentual' AND valor_beneficio > 0 AND valor_beneficio <= 100) OR "
                "(tipo = 'desconto_valor_fixo' AND valor_beneficio > 0)"
            ),
        }
        with op.batch_alter_table("produto") as batch:
            for nome, condicao in checks_produto.items():
                if nome not in checks_existentes:
                    batch.create_check_constraint(nome, condicao)

        inspector = sa.inspect(bind)
        _criar_indice_se_ausente(inspector, "produto", "ix_produto_id_usuario", ["id_usuario"])
        _criar_indice_se_ausente(inspector, "produto", "ix_produto_validade", ["validade"])
        _criar_indice_se_ausente(inspector, "produto", "ix_produto_status", ["status"])

    if "historico" in tabelas:
        _criar_indice_se_ausente(inspector, "historico", "ix_historico_id_usuario", ["id_usuario"])
        _criar_indice_se_ausente(inspector, "historico", "ix_historico_id_produto", ["id_produto"])
        _criar_indice_se_ausente(
            inspector,
            "historico",
            "ix_historico_tipo_movimentacao",
            ["tipo_movimentacao"],
        )
        _criar_indice_se_ausente(
            inspector,
            "historico",
            "ix_historico_data_movimentacao",
            ["data_movimentacao"],
        )
        _criar_indice_se_ausente(
            inspector,
            "historico",
            "ix_historico_chave_idempotencia",
            ["chave_idempotencia"],
            unique=True,
        )

    for tabela in ("auditoria", "auditoria_legado"):
        if tabela in tabelas:
            op.drop_table(tabela)


def downgrade():
    raise RuntimeError(
        "A migração 0008 remove dados de auditoria operacional e não possui downgrade automático. "
        "Restaure o backup validado para recuperar esses dados."
    )
