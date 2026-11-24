"""Comparação integral de catálogos em bancos locais descartáveis clonados."""
import os
from pathlib import Path
import unittest
import psycopg2
from psycopg2 import sql
from flask_migrate import upgrade
from app import create_app
from app.config import TestingConfig

ROOT = Path(__file__).resolve().parents[2]
SQL = (ROOT / 'database/release_0006_0009.sql').read_text()
APPROVED_SQL = SQL.replace('\n-- SET LOCAL itclube.backup_confirmado', '\nSET LOCAL itclube.backup_confirmado')
CONNECTION = 'host=127.0.0.1 port=55439 user=dd '


def snapshot(connection):
    queries = {
        'tables': "SELECT relname,relkind,relpersistence,relrowsecurity,relforcerowsecurity FROM pg_class WHERE relnamespace='public'::regnamespace AND relkind IN ('r','p') ORDER BY relname",
        'columns': "SELECT c.relname,a.attnum,a.attname,format_type(a.atttypid,a.atttypmod),a.attnotnull,a.attidentity,a.attgenerated,pg_get_expr(d.adbin,d.adrelid),a.attcollation::regcollation::text FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum WHERE c.relnamespace='public'::regnamespace AND c.relkind IN ('r','p') AND a.attnum>0 AND NOT a.attisdropped ORDER BY c.relname,a.attnum",
        'constraints': "SELECT conrelid::regclass::text,conname,contype,pg_get_constraintdef(oid),convalidated,condeferrable,condeferred,confupdtype,confdeltype,confmatchtype FROM pg_constraint WHERE connamespace='public'::regnamespace ORDER BY conrelid::regclass::text,conname",
        'indexes': "SELECT t.relname,c.relname,pg_get_indexdef(i.indexrelid),i.indisunique,i.indisvalid,i.indisready,i.indislive,i.indnkeyatts,i.indnatts,i.indkey::text,i.indclass::text,i.indcollation::text,i.indoption::text,pg_get_expr(i.indpred,i.indrelid),pg_get_expr(i.indexprs,i.indrelid) FROM pg_index i JOIN pg_class t ON t.oid=i.indrelid JOIN pg_class c ON c.oid=i.indexrelid WHERE t.relnamespace='public'::regnamespace ORDER BY t.relname,c.relname",
        'sequences': "SELECT schemaname,sequencename,data_type::text,start_value,min_value,max_value,increment_by,cycle,cache_size,last_value FROM pg_sequences WHERE schemaname='public' ORDER BY sequencename",
        'sequence_ownership': "SELECT c.relname,t.relname,a.attname,d.deptype FROM pg_depend d JOIN pg_class c ON c.oid=d.objid JOIN pg_class t ON t.oid=d.refobjid JOIN pg_attribute a ON a.attrelid=t.oid AND a.attnum=d.refobjsubid WHERE c.relkind='S' AND c.relnamespace='public'::regnamespace AND d.classid='pg_class'::regclass AND d.refclassid='pg_class'::regclass ORDER BY c.relname",
        'enums': "SELECT t.typname,e.enumlabel,e.enumsortorder FROM pg_type t JOIN pg_enum e ON e.enumtypid=t.oid WHERE t.typnamespace='public'::regnamespace ORDER BY t.typname,e.enumsortorder",
    }
    result = {}
    with connection.cursor() as cursor:
        for name, query in queries.items():
            cursor.execute(query)
            result[name] = cursor.fetchall()
        for table in ('usuario','produto','historico','alembic_version'):
            cursor.execute(sql.SQL('SELECT to_jsonb(t) FROM public.{} t ORDER BY to_jsonb(t)::text').format(sql.Identifier(table)))
            result[table] = cursor.fetchall()
        cursor.execute("SELECT sequencename FROM pg_sequences WHERE schemaname='public' ORDER BY sequencename")
        for (sequence,) in cursor.fetchall():
            cursor.execute(sql.SQL('SELECT last_value,is_called FROM public.{}').format(sql.Identifier(sequence)))
            result['state_' + sequence] = cursor.fetchall()
    return result


@unittest.skipUnless(os.getenv('ITCLUBE_TEST_POSTGRES'), 'Cluster descartável requerido')
class ReleaseParityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if '127.0.0.1:55439/' not in os.environ['ITCLUBE_TEST_POSTGRES']:
            raise RuntimeError('Permitido somente cluster descartável na porta 55439')
        cls.control = psycopg2.connect(CONNECTION + 'dbname=release_api')
        cls.control.autocommit = True
        cls.template = 'itclube_parity_template'
        with cls.control.cursor() as cursor:
            cursor.execute('DROP DATABASE IF EXISTS itclube_parity_template')
            cursor.execute("CREATE DATABASE itclube_parity_template TEMPLATE template0 ENCODING 'UTF8'")
        conn = psycopg2.connect(CONNECTION + 'dbname=' + cls.template)
        with conn, conn.cursor() as cursor:
            baseline = (ROOT / 'database/schema/schema_postgresql.sql').read_text()
            baseline = baseline.replace('SERIAL PRIMARY KEY', 'INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY')
            baseline = baseline.replace('    chave_idempotencia  VARCHAR(128),', '    valor_compra NUMERIC(10,2),')
            baseline = baseline[:baseline.index('CREATE UNIQUE INDEX IF NOT EXISTS ix_historico_chave_idempotencia')]
            cursor.execute(baseline)
            cursor.execute("CREATE TABLE alembic_version(version_num VARCHAR(32) PRIMARY KEY); INSERT INTO alembic_version VALUES ('0006_adaptar_neon')")
            cursor.execute("CREATE TABLE auditoria(id_auditoria INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,id_usuario INTEGER REFERENCES usuario(id_usuario),acao VARCHAR(50) NOT NULL,entidade VARCHAR(50) NOT NULL,entidade_id VARCHAR(50),detalhes TEXT,ip VARCHAR(45),user_agent VARCHAR(255),data_hora TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)")
            cursor.execute("ALTER TABLE usuario DROP CONSTRAINT usuario_email_key; ALTER TABLE produto DROP CONSTRAINT produto_id_usuario_fkey; ALTER TABLE historico DROP CONSTRAINT historico_id_usuario_fkey; ALTER TABLE historico ADD FOREIGN KEY(id_usuario) REFERENCES usuario(id_usuario) ON DELETE CASCADE")
            cursor.execute("ALTER TABLE historico DROP CONSTRAINT chk_historico_tipo; CREATE TYPE movimento_legado AS ENUM('COMPRA','RESGATE'); ALTER TABLE historico ALTER COLUMN tipo_movimentacao TYPE movimento_legado USING tipo_movimentacao::movimento_legado")
            cursor.execute("INSERT INTO usuario(nome,login,senha_hash,nivel_acesso,pontos_acumulados,data_cadastro) VALUES ('Fixture','fixture','hash-ficticio','CLIENTE',1,'2026-01-01')")
            cursor.execute("INSERT INTO historico(id_usuario,tipo_movimentacao,pontos,valor_compra,data_movimentacao) VALUES (1,'COMPRA',1,20,'2026-01-01')")
            cursor.execute("INSERT INTO auditoria(acao,entidade) VALUES ('fixture','fixture')")
        conn.close()

    @classmethod
    def tearDownClass(cls):
        cls.control.close()

    def database(self, name):
        with self.control.cursor() as cursor:
            cursor.execute(sql.SQL('DROP DATABASE IF EXISTS {}').format(sql.Identifier(name)))
            cursor.execute(sql.SQL('CREATE DATABASE {} TEMPLATE {}').format(sql.Identifier(name),sql.Identifier(self.template)))
        conn = psycopg2.connect(CONNECTION + 'dbname=' + name)
        conn.autocommit = True
        self.addCleanup(conn.close)
        return conn

    def test_integral_parity(self):
        a = self.database('itclube_parity_a')
        b = self.database('itclube_parity_b')
        before = snapshot(a)
        self.assertEqual(before, snapshot(b))
        previous = TestingConfig.SQLALCHEMY_DATABASE_URI
        try:
            TestingConfig.SQLALCHEMY_DATABASE_URI = 'postgresql://dd@127.0.0.1:55439/itclube_parity_a'
            app = create_app('testing')
            with app.app_context():
                upgrade()
                from app.extensions import db
                db.session.remove()
                db.engine.dispose()
        finally:
            TestingConfig.SQLALCHEMY_DATABASE_URI = previous
        with b.cursor() as cursor:
            cursor.execute(APPROVED_SQL.replace('\nROLLBACK;', '\nCOMMIT;'))
        first, second = snapshot(a), snapshot(b)
        for table in ('usuario','produto'):
            self.assertEqual(before[table], first[table])
        old_history = [{k:v for k,v in row[0].items() if k!='valor_compra'} for row in before['historico']]
        new_history = [{k:v for k,v in row[0].items() if k!='chave_idempotencia'} for row in first['historico']]
        self.assertEqual(old_history, new_history)
        for category in first:
            with self.subTest(category=category):
                self.assertEqual(first[category], second[category])

    def test_structure_abort_and_rollback(self):
        conn = self.database('itclube_parity_abort')
        with conn.cursor() as cursor:
            cursor.execute('ALTER TABLE public.produto ADD COLUMN inesperada INTEGER')
            before = snapshot(conn)
            with self.assertRaises(psycopg2.Error):
                cursor.execute(APPROVED_SQL.replace('\nROLLBACK;', '\nCOMMIT;'))
            cursor.execute('ROLLBACK')
            self.assertEqual(before, snapshot(conn))

    def test_default_dry_run(self):
        conn = self.database('itclube_parity_dry')
        before = snapshot(conn)
        with conn.cursor() as cursor:
            cursor.execute(APPROVED_SQL)
        self.assertEqual(before, snapshot(conn))

    def test_late_failure_restores_destructive_ddl(self):
        conn = self.database('itclube_parity_late_abort')
        with conn.cursor() as cursor:
            cursor.execute('CREATE TABLE public.audit_dependency(id INTEGER REFERENCES auditoria(id_auditoria))')
            before = snapshot(conn)
            with self.assertRaises(psycopg2.Error):
                cursor.execute(APPROVED_SQL.replace('\nROLLBACK;', '\nCOMMIT;'))
            cursor.execute('ROLLBACK')
            self.assertEqual(before, snapshot(conn))
            cursor.execute('SELECT count(*) FROM public.auditoria')
            self.assertEqual(cursor.fetchone()[0], 1)

    def test_audit_maintenance_lock(self):
        conn = self.database('itclube_parity_audit_lock')
        blocker = psycopg2.connect(CONNECTION + 'dbname=itclube_parity_audit_lock')
        try:
            with blocker.cursor() as cursor:
                cursor.execute('LOCK TABLE public.auditoria IN ACCESS SHARE MODE')
            with conn.cursor() as cursor:
                with self.assertRaises(psycopg2.errors.LockNotAvailable):
                    cursor.execute(APPROVED_SQL.replace("lock_timeout = '5s'", "lock_timeout = '50ms'"))
                cursor.execute('ROLLBACK')
        finally:
            blocker.rollback()
            blocker.close()

    def test_unique_include_partial_and_dedup(self):
        conn = self.database('itclube_parity_indexes')
        with conn.cursor() as cursor:
            cursor.execute("CREATE UNIQUE INDEX include_email ON public.usuario(login) INCLUDE(email); CREATE UNIQUE INDEX partial_email ON public.usuario(email) WHERE email IS NOT NULL")
            cursor.execute("CREATE INDEX existing_status ON public.produto(status); ALTER TABLE public.produto ADD CONSTRAINT unrelated_cost CHECK(custo_pontos < 1000000)")
            cursor.execute(APPROVED_SQL.replace('\nROLLBACK;', '\nCOMMIT;'))
            cursor.execute("SELECT count(*) FROM pg_index i JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=i.indkey[0] WHERE i.indrelid='public.usuario'::regclass AND i.indisunique AND i.indisvalid AND i.indnkeyatts=1 AND i.indpred IS NULL AND a.attname='email'")
            self.assertEqual(cursor.fetchone()[0], 1)
            cursor.execute("SELECT count(*) FROM pg_constraint WHERE conrelid='public.produto'::regclass AND conname='unrelated_cost'")
            self.assertEqual(cursor.fetchone()[0], 1)
            cursor.execute("SELECT count(*) FROM pg_index i JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=i.indkey[0] WHERE i.indrelid='public.produto'::regclass AND i.indnkeyatts=1 AND a.attname='status' AND i.indisvalid")
            self.assertEqual(cursor.fetchone()[0], 1)

    def test_invalid_unique_key_is_not_accepted(self):
        conn = self.database('itclube_parity_key')
        with conn.cursor() as cursor:
            # Schema 0008 fictício para isolar a revisão 0009.
            cursor.execute("ALTER TABLE historico DROP COLUMN valor_compra; ALTER TABLE historico ADD COLUMN chave_idempotencia VARCHAR(128); CREATE UNIQUE INDEX include_key ON historico(id_historico) INCLUDE(chave_idempotencia); UPDATE alembic_version SET version_num='0008_consolidar_schema'")
        previous = TestingConfig.SQLALCHEMY_DATABASE_URI
        try:
            TestingConfig.SQLALCHEMY_DATABASE_URI = 'postgresql://dd@127.0.0.1:55439/itclube_parity_key'
            with create_app('testing').app_context():
                upgrade()
                from app.extensions import db
                db.session.remove()
                db.engine.dispose()
        finally:
            TestingConfig.SQLALCHEMY_DATABASE_URI = previous
        with conn.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM pg_index i JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=i.indkey[0] WHERE i.indrelid='public.historico'::regclass AND i.indisunique AND i.indisvalid AND i.indnkeyatts=1 AND i.indpred IS NULL AND a.attname='chave_idempotencia'")
            self.assertEqual(cursor.fetchone()[0], 1)
