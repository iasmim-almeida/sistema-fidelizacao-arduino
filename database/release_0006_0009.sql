-- Ensaio por padrão. Após backup recuperável e aprovação individual,
-- habilite a confirmação abaixo e substitua ROLLBACK por COMMIT.
BEGIN;
SET LOCAL search_path = public, pg_catalog, pg_temp;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';
-- SET LOCAL itclube.backup_confirmado = 'sim';
LOCK TABLE public.alembic_version, public.usuario, public.produto, public.historico, public.auditoria IN ACCESS EXCLUSIVE MODE;
DO $$ BEGIN
 IF to_regclass('public.auditoria_legado') IS NOT NULL THEN
  LOCK TABLE public.auditoria_legado IN ACCESS EXCLUSIVE MODE;
 END IF;
END $$;
DO $$ BEGIN
 IF (SELECT count(*) FROM alembic_version) <> 1 OR
    (SELECT version_num FROM alembic_version) <> '0006_adaptar_neon' THEN
   RAISE EXCEPTION 'Revisão inicial deve ser 0006_adaptar_neon';
 END IF;
 IF current_setting('itclube.backup_confirmado', true) IS DISTINCT FROM 'sim' THEN
   RAISE EXCEPTION 'Confirme backup recuperável e aprovação individual antes do ensaio';
 END IF;
END $$;
-- Pré-condições físicas. Qualquer diferença aborta antes do primeiro DDL.
DO $structure$
DECLARE spec record; actual jsonb; expected jsonb;
BEGIN
 FOR spec IN SELECT * FROM (VALUES
 ('alembic_version', '{"version_num":"character varying(32)!"}'),
 ('usuario', '{"id_usuario":"integer!","nome":"character varying(100)!","telefone":"character varying(20)?","email":"character varying(100)?","endereco":"character varying(255)?","data_cadastro":"timestamp without time zone!","pontos_acumulados":"integer!","login":"character varying(50)!","senha_hash":"character varying(255)!","nivel_acesso":"character varying(20)!","cargo":"character varying(30)!","ativo":"boolean!","ultimo_login":"timestamp without time zone?","precisa_trocar_senha":"boolean!"}'),
 ('produto', '{"id_produto":"integer!","id_usuario":"integer?","nome_cupom":"character varying(100)!","descricao":"character varying(255)?","codigo":"character varying(50)!","validade":"date!","custo_pontos":"integer!","tipo":"character varying(30)!","valor_beneficio":"numeric(10,2)?","quantidade_total":"integer?","quantidade_disponivel":"integer?","status":"character varying(10)!","created_at":"timestamp without time zone!","updated_at":"timestamp without time zone!"}'),
 ('historico', '{"id_historico":"integer!","id_usuario":"integer!","id_produto":"integer?","tipo_movimentacao":"character varying(20)!","data_movimentacao":"timestamp without time zone!","pontos":"integer!","descricao":"character varying(255)?","saldo_anterior":"integer?","saldo_posterior":"integer?","origem":"character varying(50)?","valor_compra":"numeric(10,2)?"}'),
 ('auditoria', '{"id_auditoria":"integer!","id_usuario":"integer?","acao":"character varying(50)!","entidade":"character varying(50)!","entidade_id":"character varying(50)?","detalhes":"text?","ip":"character varying(45)?","user_agent":"character varying(255)?","data_hora":"timestamp without time zone!"}')
 ) AS t(tbl, columns) LOOP
  IF NOT EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relname=spec.tbl AND c.relkind='r') THEN
   RAISE EXCEPTION 'Tabela public.% ausente ou incompatível',spec.tbl;
  END IF;
  expected := spec.columns::jsonb;
  SELECT jsonb_object_agg(a.attname,
   (CASE WHEN spec.tbl='historico' AND a.attname='tipo_movimentacao' AND ty.typtype='e'
     THEN 'character varying(20)' ELSE format_type(a.atttypid,a.atttypmod) END)
    || CASE WHEN a.attnotnull THEN '!' ELSE '?' END) INTO actual
  FROM pg_attribute a JOIN pg_type ty ON ty.oid=a.atttypid
  WHERE a.attrelid=format('public.%I',spec.tbl)::regclass AND a.attnum>0 AND NOT a.attisdropped;
  IF actual IS DISTINCT FROM expected THEN
   RAISE EXCEPTION 'Estrutura divergente em public.%',spec.tbl;
  END IF;
 END LOOP;
 IF EXISTS(SELECT 1 FROM (VALUES ('usuario','id_usuario'),('produto','id_produto'),('historico','id_historico')) s(tbl,col)
  WHERE NOT EXISTS(SELECT 1 FROM pg_attribute a WHERE a.attrelid=format('public.%I',s.tbl)::regclass
   AND a.attname=s.col AND a.attidentity='a')) THEN
  RAISE EXCEPTION 'Esperadas chaves IDENTITY ALWAYS';
 END IF;
END $structure$;
DO $index_structure$ DECLARE spec record; BEGIN
 FOR spec IN SELECT * FROM (VALUES
 ('ix_produto_id_usuario','produto','id_usuario',false),
 ('ix_produto_validade','produto','validade',false),
 ('ix_produto_status','produto','status',false),
 ('ix_historico_id_usuario','historico','id_usuario',false),
 ('ix_historico_id_produto','historico','id_produto',false),
 ('ix_historico_tipo_movimentacao','historico','tipo_movimentacao',false),
 ('ix_historico_data_movimentacao','historico','data_movimentacao',false),
 ('ix_historico_chave_idempotencia','historico','chave_idempotencia',true)
 ) s(name,tbl,col,uniq) LOOP
 IF to_regclass(format('public.%I',spec.name)) IS NOT NULL AND NOT EXISTS(
  SELECT 1 FROM pg_index i JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=i.indkey[0]
  WHERE i.indexrelid=to_regclass(format('public.%I',spec.name))
  AND i.indrelid=format('public.%I',spec.tbl)::regclass AND a.attname=spec.col
  AND i.indisvalid AND i.indisready AND i.indisunique=spec.uniq
  AND i.indnkeyatts=1 AND i.indnatts=1 AND i.indpred IS NULL AND i.indexprs IS NULL
 ) THEN RAISE EXCEPTION 'Índice public.% incompatível',spec.name; END IF;
 END LOOP;
END $index_structure$;
CREATE TEMP TABLE release_rows ON COMMIT DROP AS
 SELECT 'usuario' AS tabela, to_jsonb(u) AS dados FROM usuario u
 UNION ALL SELECT 'produto', to_jsonb(p) FROM produto p
 UNION ALL SELECT 'historico', to_jsonb(h) - 'valor_compra' FROM historico h;
CREATE TEMP TABLE release_identity ON COMMIT DROP AS
 SELECT table_name, column_name, is_identity, identity_generation, column_default
 FROM information_schema.columns WHERE table_schema = current_schema()
 AND table_name IN ('usuario','produto','historico') AND column_name IN ('id_usuario','id_produto','id_historico');
CREATE TEMP TABLE release_sequences ON COMMIT DROP AS
 SELECT schemaname, sequencename, last_value FROM pg_sequences WHERE schemaname=current_schema()
 AND (schemaname||'.'||sequencename)::regclass IN (
 pg_get_serial_sequence('usuario','id_usuario')::regclass,
 pg_get_serial_sequence('produto','id_produto')::regclass,
 pg_get_serial_sequence('historico','id_historico')::regclass);

ALTER TABLE historico DROP COLUMN IF EXISTS valor_compra;
ALTER TABLE historico ADD COLUMN IF NOT EXISTS chave_idempotencia VARCHAR(128);
DO $$ DECLARE c record; BEGIN
 FOR c IN SELECT conname FROM pg_constraint WHERE conrelid='produto'::regclass AND contype='c'
 AND pg_get_constraintdef(oid) LIKE '%valor_beneficio%' LOOP
  EXECUTE format('ALTER TABLE produto DROP CONSTRAINT %I', c.conname);
 END LOOP;
 FOR c IN SELECT conname FROM pg_constraint WHERE conrelid='historico'::regclass AND contype='c'
 AND pg_get_constraintdef(oid) LIKE '%tipo_movimentacao%' LOOP
  EXECUTE format('ALTER TABLE historico DROP CONSTRAINT %I', c.conname);
 END LOOP;
 IF EXISTS(SELECT 1 FROM historico WHERE tipo_movimentacao::text NOT IN
 ('COMPRA','RESGATE','AJUSTE_POSITIVO','AJUSTE_NEGATIVO','ESTORNO','EXPIRACAO')) THEN
 RAISE EXCEPTION 'Tipos históricos incompatíveis'; END IF;
END $$;
ALTER TABLE historico ALTER COLUMN tipo_movimentacao TYPE VARCHAR(20) USING tipo_movimentacao::text;
ALTER TABLE historico ADD CONSTRAINT chk_historico_tipo CHECK
 (tipo_movimentacao IN ('COMPRA','RESGATE','AJUSTE_POSITIVO','AJUSTE_NEGATIVO','ESTORNO','EXPIRACAO'));
ALTER TABLE produto ADD CONSTRAINT chk_produto_valor_beneficio CHECK (
 (tipo='produto_fisico' AND valor_beneficio IS NULL) OR
 (tipo='desconto_percentual' AND valor_beneficio IS NOT NULL AND valor_beneficio>0 AND valor_beneficio<=100) OR
 (tipo='desconto_valor_fixo' AND valor_beneficio IS NOT NULL AND valor_beneficio>0));

DO $$ DECLARE spec record; fk record; BEGIN
 FOR spec IN SELECT * FROM (VALUES
 ('produto','id_usuario','usuario','SET NULL'),
 ('historico','id_usuario','usuario','RESTRICT'),
 ('historico','id_produto','produto','SET NULL')) AS t(tbl,col,target,action) LOOP
  IF (SELECT count(*) FROM pg_constraint c JOIN pg_attribute a
      ON a.attrelid=c.conrelid AND a.attnum=ANY(c.conkey)
      WHERE c.conrelid=format('public.%I',spec.tbl)::regclass AND c.contype='f' AND a.attname=spec.col)=1
   AND EXISTS(SELECT 1 FROM pg_constraint c JOIN pg_attribute a
      ON a.attrelid=c.conrelid AND a.attnum=c.conkey[1]
      JOIN pg_attribute b ON b.attrelid=c.confrelid AND b.attnum=c.confkey[1]
      WHERE c.conrelid=format('public.%I',spec.tbl)::regclass AND c.contype='f'
      AND cardinality(c.conkey)=1 AND cardinality(c.confkey)=1
      AND c.confrelid=format('public.%I',spec.target)::regclass AND a.attname=spec.col AND b.attname=spec.col
      AND c.confdeltype=CASE WHEN spec.action='RESTRICT' THEN 'r'::"char" ELSE 'n'::"char" END) THEN
   CONTINUE;
  END IF;
  FOR fk IN SELECT c.conname FROM pg_constraint c JOIN pg_attribute a
   ON a.attrelid=c.conrelid AND a.attnum=ANY(c.conkey)
   WHERE c.conrelid=spec.tbl::regclass AND c.contype='f' AND a.attname=spec.col LOOP
   EXECUTE format('ALTER TABLE %I DROP CONSTRAINT %I',spec.tbl,fk.conname);
  END LOOP;
  EXECUTE format('ALTER TABLE %I ADD CONSTRAINT %I FOREIGN KEY (%I) REFERENCES %I (%I) ON DELETE %s',
   spec.tbl,'fk_'||spec.tbl||'_'||spec.col,spec.col,spec.target,spec.col,spec.action);
 END LOOP;
 IF NOT EXISTS(SELECT 1 FROM pg_index i JOIN pg_attribute a ON a.attrelid=i.indrelid
 AND a.attnum=i.indkey[0] WHERE i.indrelid='public.usuario'::regclass AND i.indisunique
 AND i.indisvalid AND i.indisready AND i.indnkeyatts=1 AND i.indexprs IS NULL
 AND i.indpred IS NULL AND a.attname='email') THEN
 ALTER TABLE usuario ADD CONSTRAINT uq_usuario_email UNIQUE(email);
 END IF;
END $$;

DO $checks$ DECLARE spec record; BEGIN
 FOR spec IN SELECT * FROM (VALUES
 ('chk_produto_custo','custo_pontos > 0'),
 ('chk_produto_tipo', $$tipo IN ('produto_fisico','desconto_percentual','desconto_valor_fixo')$$),
 ('chk_produto_status', $$status IN ('ativa','pausada')$$),
 ('chk_produto_quantidade_total','quantidade_total IS NULL OR quantidade_total >= 0'),
 ('chk_produto_quantidade_disponivel','quantidade_disponivel IS NULL OR (quantidade_disponivel >= 0 AND (quantidade_total IS NULL OR quantidade_disponivel <= quantidade_total))')
 ) AS t(name,definition) LOOP
 IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conrelid='produto'::regclass AND conname=spec.name) THEN
 EXECUTE format('ALTER TABLE produto ADD CONSTRAINT %I CHECK (%s)',spec.name,spec.definition);
 END IF;
 END LOOP;
END $checks$;
CREATE INDEX IF NOT EXISTS ix_produto_id_usuario ON produto(id_usuario);
CREATE INDEX IF NOT EXISTS ix_produto_validade ON produto(validade);
CREATE INDEX IF NOT EXISTS ix_produto_status ON produto(status);
CREATE INDEX IF NOT EXISTS ix_historico_id_usuario ON historico(id_usuario);
CREATE INDEX IF NOT EXISTS ix_historico_id_produto ON historico(id_produto);
CREATE INDEX IF NOT EXISTS ix_historico_tipo_movimentacao ON historico(tipo_movimentacao);
CREATE INDEX IF NOT EXISTS ix_historico_data_movimentacao ON historico(data_movimentacao);
CREATE UNIQUE INDEX IF NOT EXISTS ix_historico_chave_idempotencia ON historico(chave_idempotencia);
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
DROP TABLE IF EXISTS auditoria;
DROP TABLE IF EXISTS auditoria_legado;

DO $$ BEGIN
 IF EXISTS (
  (SELECT * FROM release_rows EXCEPT ALL
   (SELECT 'usuario',to_jsonb(u) FROM usuario u UNION ALL SELECT 'produto',to_jsonb(p) FROM produto p
    UNION ALL SELECT 'historico',to_jsonb(h)-'chave_idempotencia' FROM historico h))
  UNION ALL
  ((SELECT 'usuario',to_jsonb(u) FROM usuario u UNION ALL SELECT 'produto',to_jsonb(p) FROM produto p
    UNION ALL SELECT 'historico',to_jsonb(h)-'chave_idempotencia' FROM historico h) EXCEPT ALL SELECT * FROM release_rows)
 ) THEN RAISE EXCEPTION 'Registros de negócio divergentes'; END IF;
 IF EXISTS(SELECT * FROM release_identity EXCEPT
 SELECT table_name,column_name,is_identity,identity_generation,column_default FROM information_schema.columns
 WHERE table_schema=current_schema()) THEN RAISE EXCEPTION 'IDENTITY alterada'; END IF;
 IF EXISTS(SELECT * FROM release_sequences EXCEPT
 SELECT schemaname,sequencename,last_value FROM pg_sequences WHERE schemaname=current_schema()) THEN
 RAISE EXCEPTION 'Sequência alterada'; END IF;
 IF NOT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema()
 AND table_name='historico' AND column_name='chave_idempotencia' AND data_type='character varying'
 AND character_maximum_length=128 AND is_nullable='YES') THEN RAISE EXCEPTION 'Contrato idempotência inválido'; END IF;
 IF EXISTS(SELECT 1 FROM pg_constraint WHERE conrelid IN ('usuario'::regclass,'produto'::regclass,'historico'::regclass)
 AND NOT convalidated) THEN RAISE EXCEPTION 'Constraint não validada'; END IF;
END $$;
DO $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM pg_index i JOIN pg_attribute a
 ON a.attrelid=i.indrelid AND a.attnum=i.indkey[0]
 WHERE i.indrelid='public.historico'::regclass AND i.indisunique AND i.indisvalid AND i.indisready
 AND i.indnkeyatts=1 AND i.indpred IS NULL AND i.indexprs IS NULL AND a.attname='chave_idempotencia') THEN
 RAISE EXCEPTION 'Índice único válido de idempotência ausente'; END IF;
END $$;
UPDATE alembic_version SET version_num='0009_alinhar_neon' WHERE version_num='0006_adaptar_neon';
SELECT version_num FROM alembic_version;
ROLLBACK;
