"""Cenários de migração no cluster local descartável da release."""
import os
from pathlib import Path
import unittest
import psycopg2
from flask_migrate import upgrade, check
from sqlalchemy import text
from app import create_app
from app.config import TestingConfig
from app.extensions import db

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(os.getenv("ITCLUBE_TEST_POSTGRES"), "PostgreSQL descartável não configurado")
class MigrationPostgresqlTest(unittest.TestCase):
    def setUp(self):
        if "127.0.0.1:55439/" not in os.environ["ITCLUBE_TEST_POSTGRES"]:
            raise RuntimeError("Cluster descartável obrigatório")
        control = psycopg2.connect("host=127.0.0.1 port=55439 user=dd dbname=release_api")
        control.autocommit = True
        with control.cursor() as cursor:
            cursor.execute("DROP DATABASE IF EXISTS itclube_migration_fixture")
            cursor.execute("CREATE DATABASE itclube_migration_fixture TEMPLATE template0 ENCODING 'UTF8'")
        control.close()
        self.connection = psycopg2.connect("host=127.0.0.1 port=55439 user=dd dbname=itclube_migration_fixture")
        self.connection.autocommit = True
        self.cursor = self.connection.cursor()
        self.schema = "public"
        self.cursor.execute(f"SET search_path TO {self.schema}")

    def tearDown(self):
        self.cursor.close()
        self.connection.close()

    def fixture(self):
        sql = (ROOT / "database/schema/schema_postgresql.sql").read_text()
        sql = sql.replace("SERIAL PRIMARY KEY", "INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY")
        sql = sql.replace("    chave_idempotencia  VARCHAR(128),", "    valor_compra NUMERIC(10,2),")
        sql = sql[:sql.index("CREATE UNIQUE INDEX IF NOT EXISTS ix_historico_chave_idempotencia")]
        self.cursor.execute(sql)
        self.cursor.execute("CREATE TABLE alembic_version(version_num VARCHAR(32) PRIMARY KEY); INSERT INTO alembic_version VALUES ('0006_adaptar_neon'); CREATE TABLE auditoria(id_auditoria INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,id_usuario INTEGER REFERENCES usuario(id_usuario),acao VARCHAR(50) NOT NULL,entidade VARCHAR(50) NOT NULL,entidade_id VARCHAR(50),detalhes TEXT,ip VARCHAR(45),user_agent VARCHAR(255),data_hora TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        self.cursor.execute("INSERT INTO usuario(nome,login,senha_hash,nivel_acesso,pontos_acumulados) VALUES ('Cliente','cliente','hash-ficticio','CLIENTE',1)")
        self.cursor.execute("INSERT INTO historico(id_usuario,tipo_movimentacao,pontos,valor_compra) VALUES (1,'COMPRA',1,19.90)")
        self.cursor.execute("SELECT to_jsonb(u) FROM usuario u")
        self.user = self.cursor.fetchone()[0]

    def app(self):
        previous = TestingConfig.SQLALCHEMY_DATABASE_URI
        TestingConfig.SQLALCHEMY_DATABASE_URI = "postgresql://dd@127.0.0.1:55439/itclube_migration_fixture"
        app = create_app("testing")
        with app.app_context():
            engine = db.engine
        self.addCleanup(engine.dispose)
        TestingConfig.SQLALCHEMY_DATABASE_URI = previous
        return app

    def verify(self):
        self.cursor.execute("SELECT version_num FROM alembic_version")
        self.assertEqual(self.cursor.fetchone()[0], "0009_alinhar_neon")
        self.cursor.execute("SELECT to_jsonb(u) FROM usuario u")
        self.assertEqual(self.cursor.fetchone()[0], self.user)
        self.cursor.execute("SELECT is_identity FROM information_schema.columns WHERE table_schema=%s AND table_name='usuario' AND column_name='id_usuario'", (self.schema,))
        self.assertEqual(self.cursor.fetchone()[0], "YES")
        self.cursor.execute("SELECT pontos FROM historico")
        self.assertEqual(self.cursor.fetchone()[0], 1)
        with self.assertRaises(psycopg2.IntegrityError):
            self.cursor.execute("DELETE FROM usuario WHERE id_usuario=1")
        self.cursor.execute("INSERT INTO usuario(nome,login,senha_hash,nivel_acesso) VALUES ('Novo','novo','hash-ficticio','CLIENTE') RETURNING id_usuario")
        self.assertEqual(self.cursor.fetchone()[0], 2)

    def test_0006_to_0009(self):
        self.fixture()
        with self.app().app_context():
            upgrade()
        self.verify()

    def test_empty_database_to_head(self):
        with self.app().app_context():
            upgrade()
            check()
        self.cursor.execute("SELECT version_num FROM alembic_version")
        self.assertEqual(self.cursor.fetchone()[0], "0009_alinhar_neon")

    def test_enum_legacy(self):
        self.fixture()
        self.cursor.execute("ALTER TABLE historico DROP CONSTRAINT chk_historico_tipo; CREATE TYPE movimento_legado AS ENUM ('COMPRA','RESGATE'); ALTER TABLE historico ALTER COLUMN tipo_movimentacao TYPE movimento_legado USING tipo_movimentacao::movimento_legado")
        with self.app().app_context():
            upgrade()
        self.verify()

    def test_sql_dry_run(self):
        self.fixture()
        sql = (ROOT / "database/release_0006_0009.sql").read_text()
        sql = sql.replace("\n-- SET LOCAL itclube.backup_confirmado", "\nSET LOCAL itclube.backup_confirmado")
        self.cursor.execute(sql)
        self.cursor.execute("SELECT version_num FROM alembic_version")
        self.assertEqual(self.cursor.fetchone()[0], "0006_adaptar_neon")

    def test_0008_to_0009(self):
        self.fixture()
        with self.app().app_context():
            upgrade(revision="0008_consolidar_schema")
            upgrade()
        self.verify()

    def test_sql_equivalent(self):
        self.fixture()
        sql = (ROOT / "database/release_0006_0009.sql").read_text()
        sql = sql.replace("\n-- SET LOCAL itclube.backup_confirmado", "\nSET LOCAL itclube.backup_confirmado")
        # Apenas neste banco fictício, confirma para verificar o resultado final.
        self.cursor.execute(sql.replace("ROLLBACK;", "COMMIT;"))
        self.verify()
