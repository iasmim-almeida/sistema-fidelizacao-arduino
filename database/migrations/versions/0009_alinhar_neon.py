"""Alinha constraints sem reconstruir tabelas ou alterar dados e identidades."""

from alembic import op
import sqlalchemy as sa

revision = "0009_alinhar_neon"
down_revision = "0008_consolidar_schema"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError("0009 requer PostgreSQL para preservar o contrato operacional")
    # ALTER TABLE preserva IDENTITY e sequências. Violações abortam a transação.
    email_unique = bind.execute(sa.text("""
        SELECT EXISTS(SELECT 1 FROM pg_index i JOIN pg_attribute a
        ON a.attrelid=i.indrelid AND a.attnum=i.indkey[0]
        WHERE i.indrelid='usuario'::regclass AND i.indisunique
        AND i.indisvalid AND i.indisready AND i.indnkeyatts=1
        AND i.indpred IS NULL AND i.indexprs IS NULL AND a.attname='email')
    """)).scalar()
    if not email_unique:
        op.create_unique_constraint("uq_usuario_email", "usuario", ["email"])

    for table, column, target, action in (
        ("produto", "id_usuario", "usuario", "SET NULL"),
        ("historico", "id_usuario", "usuario", "RESTRICT"),
        ("historico", "id_produto", "produto", "SET NULL"),
    ):
        foreign_keys = sa.inspect(bind).get_foreign_keys(table)
        matching = [fk for fk in foreign_keys if fk["constrained_columns"] == [column]]
        equivalent = [fk for fk in matching if fk["referred_table"] == target
                      and fk["referred_columns"] == [column]
                      and fk.get("options", {}).get("ondelete", "NO ACTION").upper() == action]
        if len(matching) == 1 and equivalent:
            continue
        for fk in matching:
            op.drop_constraint(fk["name"], table, type_="foreignkey")
        op.create_foreign_key(f"fk_{table}_{column}", table, target, [column], [column], ondelete=action)

    for table, name, condition, marker in (
        ("historico", "chk_historico_tipo", "tipo_movimentacao IN ('COMPRA', 'RESGATE', 'AJUSTE_POSITIVO', 'AJUSTE_NEGATIVO', 'ESTORNO', 'EXPIRACAO')", "tipo_movimentacao"),
        ("produto", "chk_produto_valor_beneficio", "(tipo = 'produto_fisico' AND valor_beneficio IS NULL) OR (tipo = 'desconto_percentual' AND valor_beneficio IS NOT NULL AND valor_beneficio > 0 AND valor_beneficio <= 100) OR (tipo = 'desconto_valor_fixo' AND valor_beneficio IS NOT NULL AND valor_beneficio > 0)", "valor_beneficio"),
    ):
        for check in sa.inspect(bind).get_check_constraints(table):
            if marker in check["sqltext"]:
                op.drop_constraint(check["name"], table, type_="check")
        if table == "historico":
            kind = next(c for c in sa.inspect(bind).get_columns(table) if c["name"] == "tipo_movimentacao")
            invalid = bind.execute(sa.text("SELECT count(*) FROM historico WHERE tipo_movimentacao::text NOT IN ('COMPRA','RESGATE','AJUSTE_POSITIVO','AJUSTE_NEGATIVO','ESTORNO','EXPIRACAO')")).scalar()
            if invalid:
                raise RuntimeError("Tipos históricos incompatíveis; nenhuma normalização automática")
            if not isinstance(kind["type"], sa.String) or kind["type"].length != 20 or isinstance(kind["type"], sa.Enum):
                op.alter_column(table, "tipo_movimentacao", type_=sa.String(20), postgresql_using="tipo_movimentacao::text")
        op.create_check_constraint(name, table, condition)

    column = next(c for c in sa.inspect(bind).get_columns("historico") if c["name"] == "chave_idempotencia")
    if not isinstance(column["type"], sa.String) or column["type"].length != 128 or not column["nullable"]:
        raise RuntimeError("chave_idempotencia deve ser VARCHAR(128) nullable; intervenção explícita necessária")

    # Os demais índices e checks de produto são estabelecidos pela revisão 0008.
    # Confere os índices por colunas, inclusive em bancos com nomes preexistentes.
    for table, columns, unique in (
        ("historico", ["chave_idempotencia"], True),
        ("historico", ["id_usuario"], False),
        ("historico", ["id_produto"], False),
        ("historico", ["tipo_movimentacao"], False),
        ("historico", ["data_movimentacao"], False),
        ("produto", ["id_usuario"], False),
        ("produto", ["validade"], False),
        ("produto", ["status"], False),
    ):
        indexes = sa.inspect(bind).get_indexes(table)
        if not any(i["column_names"] == columns and (not unique or i["unique"])
                   and not i.get("dialect_options", {}).get("postgresql_where") for i in indexes):
            op.create_index(f"ix_{table}_{columns[0]}", table, columns, unique=unique)

    bind.execute(sa.text("""
DO $indexes$ DECLARE candidate record; BEGIN
 FOR candidate IN
 SELECT n.nspname, a.relname
 FROM pg_index i JOIN pg_class a ON a.oid=i.indexrelid JOIN pg_namespace n ON n.oid=a.relnamespace
 WHERE n.nspname=current_schema()
 AND a.relname IN ('ix_produto_id_usuario','ix_produto_validade','ix_produto_status',
 'ix_historico_id_usuario','ix_historico_id_produto','ix_historico_tipo_movimentacao',
 'ix_historico_data_movimentacao','ix_historico_chave_idempotencia')
 AND NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conindid=i.indexrelid)
 AND EXISTS(SELECT 1 FROM pg_index other WHERE other.indrelid=i.indrelid
 AND other.indexrelid<>i.indexrelid AND other.indisvalid AND other.indisready AND other.indisunique=i.indisunique
 AND (other.indexrelid<i.indexrelid OR NOT EXISTS(SELECT 1 FROM pg_class survivor
 WHERE survivor.oid=other.indexrelid AND survivor.relname IN
 ('ix_produto_id_usuario','ix_produto_validade','ix_produto_status',
 'ix_historico_id_usuario','ix_historico_id_produto','ix_historico_tipo_movimentacao',
 'ix_historico_data_movimentacao','ix_historico_chave_idempotencia')))
 AND other.indnkeyatts=i.indnkeyatts AND other.indnatts=i.indnatts
 AND other.indkey=i.indkey AND other.indclass=i.indclass AND other.indcollation=i.indcollation
 AND other.indoption=i.indoption AND other.indpred IS NOT DISTINCT FROM i.indpred
 AND other.indexprs IS NOT DISTINCT FROM i.indexprs)
 LOOP EXECUTE format('DROP INDEX %I.%I',candidate.nspname,candidate.relname); END LOOP;
END $indexes$;
    """))
    valid_key = bind.execute(sa.text("""
        SELECT count(*) FROM pg_index i JOIN pg_attribute a
        ON a.attrelid=i.indrelid AND a.attnum=i.indkey[0]
        WHERE i.indrelid='historico'::regclass AND i.indisunique AND i.indisvalid AND i.indisready
        AND i.indnkeyatts=1 AND i.indpred IS NULL AND i.indexprs IS NULL AND a.attname='chave_idempotencia'
    """)).scalar()
    if not valid_key:
        raise RuntimeError("Índice único válido de idempotência ausente")


def downgrade():
    raise RuntimeError("Reversão das garantias de integridade requer revisão e backup")
