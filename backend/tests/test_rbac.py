import os
import sys
import unittest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app import create_app
from app.extensions import db
from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.services.rbac import (
    ROLE_PROPRIETARIO,
    ROLE_GERENTE,
    ROLE_VENDEDOR,
    usuario_tem_permissao,
)


class RBACTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app("testing")
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()

            self.proprietario = Usuario(
                nome="Proprietario Teste",
                login="prop_test",
                email="prop@teste.com",
                cargo=ROLE_PROPRIETARIO,
                nivel_acesso="gestor",
                ativo=True,
            )
            self.proprietario.set_senha("PropTeste123!")

            self.gerente = Usuario(
                nome="Gerente Teste",
                login="ger_test",
                email="ger@teste.com",
                cargo=ROLE_GERENTE,
                nivel_acesso="gerente",
                ativo=True,
            )
            self.gerente.set_senha("GerTeste123!")

            self.vendedor = Usuario(
                nome="Vendedor Teste",
                login="vend_test",
                email="vend@teste.com",
                cargo=ROLE_VENDEDOR,
                nivel_acesso="vendedor",
                ativo=True,
            )
            self.vendedor.set_senha("VendTeste123!")

            self.inativo = Usuario(
                nome="Inativo Teste",
                login="inat_test",
                email="inat@teste.com",
                cargo=ROLE_VENDEDOR,
                nivel_acesso="vendedor",
                ativo=False,
            )
            self.inativo.set_senha("InatTeste123!")

            self.cliente = Cliente(
                nome="Cliente Teste",
                telefone="11999990001",
                ativo=True,
            )
            self.cliente.set_senha("CliTeste123!")

            db.session.add_all([self.proprietario, self.gerente, self.vendedor, self.inativo, self.cliente])
            db.session.commit()

            self.ids = {
                "prop": self.proprietario.id_usuario,
                "ger": self.gerente.id_usuario,
                "vend": self.vendedor.id_usuario,
                "inat": self.inativo.id_usuario,
                "cli": self.cliente.id_cliente,
            }

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def autenticar(self, prefixo, user_id):
        with self.client.session_transaction() as sess:
            sess["_user_id"] = f"{prefixo}_{user_id}"
            sess["_fresh"] = True

    def test_matriz_permissoes_unitaria(self):
        with self.app.app_context():
            vendedora = db.session.get(Usuario, self.ids["prop"])
            inat = db.session.get(Usuario, self.ids["inat"])
            cli = db.session.get(Cliente, self.ids["cli"])

            # Vendedora (Admin) possui acesso integral
            self.assertTrue(usuario_tem_permissao(vendedora, "funcionarios.criar"))
            self.assertTrue(usuario_tem_permissao(vendedora, "auditoria.visualizar"))
            self.assertTrue(usuario_tem_permissao(vendedora, "pontos.remover"))
            self.assertTrue(usuario_tem_permissao(vendedora, "recompensas.criar"))
            self.assertTrue(usuario_tem_permissao(vendedora, "clientes.visualizar"))
            self.assertTrue(usuario_tem_permissao(vendedora, "pontos.adicionar"))

            # Usuário inativo não possui permissão alguma
            self.assertFalse(usuario_tem_permissao(inat, "clientes.visualizar"))
            self.assertFalse(usuario_tem_permissao(inat, "pontos.adicionar"))

            # Cliente não possui permissões administrativas
            self.assertFalse(usuario_tem_permissao(cli, "funcionarios.visualizar"))
            self.assertFalse(usuario_tem_permissao(cli, "auditoria.visualizar"))

    def test_cliente_bloqueado_em_funcionarios_e_auditoria(self):
        self.autenticar("c", self.ids["cli"])
        resp_func = self.client.get("/api/funcionarios/")
        self.assertEqual(resp_func.status_code, 403)

        resp_audit = self.client.get("/api/auditoria/")
        self.assertEqual(resp_audit.status_code, 403)

    def test_inativo_bloqueado_em_funcionarios_e_auditoria(self):
        self.autenticar("u", self.ids["inat"])
        resp_func = self.client.get("/api/funcionarios/")
        self.assertIn(resp_func.status_code, [401, 403])

        resp_audit = self.client.get("/api/auditoria/")
        self.assertIn(resp_audit.status_code, [401, 403])

    def test_vendedora_admin_acessa_funcionarios_e_auditoria(self):
        self.autenticar("u", self.ids["prop"])
        resp_func = self.client.get("/api/funcionarios/")
        self.assertEqual(resp_func.status_code, 200)

        resp_audit = self.client.get("/api/auditoria/")
        self.assertEqual(resp_audit.status_code, 200)

    def test_anonimo_recebe_401(self):
        resp_func = self.client.get("/api/funcionarios/")
        self.assertEqual(resp_func.status_code, 401)

        resp_audit = self.client.get("/api/auditoria/")
        self.assertEqual(resp_audit.status_code, 401)


if __name__ == "__main__":
    unittest.main()
