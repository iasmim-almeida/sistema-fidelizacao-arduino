import unittest
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
            prop = db.session.get(Usuario, self.ids["prop"])
            ger = db.session.get(Usuario, self.ids["ger"])
            vend = db.session.get(Usuario, self.ids["vend"])
            inat = db.session.get(Usuario, self.ids["inat"])

            # Proprietário tem tudo
            self.assertTrue(usuario_tem_permissao(prop, "funcionarios.criar"))
            self.assertTrue(usuario_tem_permissao(prop, "auditoria.visualizar"))
            self.assertTrue(usuario_tem_permissao(prop, "pontos.remover"))

            # Gerente não tem funcionários nem auditoria, mas tem pontos e recompensas
            self.assertFalse(usuario_tem_permissao(ger, "funcionarios.criar"))
            self.assertFalse(usuario_tem_permissao(ger, "auditoria.visualizar"))
            self.assertTrue(usuario_tem_permissao(ger, "pontos.remover"))
            self.assertTrue(usuario_tem_permissao(ger, "recompensas.criar"))

            # Vendedor não tem auditoria, nem funcionários, nem remover pontos, nem desativar cliente
            self.assertFalse(usuario_tem_permissao(vend, "funcionarios.visualizar"))
            self.assertFalse(usuario_tem_permissao(vend, "auditoria.visualizar"))
            self.assertFalse(usuario_tem_permissao(vend, "pontos.remover"))
            self.assertFalse(usuario_tem_permissao(vend, "clientes.desativar"))
            self.assertTrue(usuario_tem_permissao(vend, "clientes.visualizar"))
            self.assertTrue(usuario_tem_permissao(vend, "pontos.adicionar"))

            # Usuário inativo não possui permissão alguma
            self.assertFalse(usuario_tem_permissao(inat, "clientes.visualizar"))

    def test_vendedor_bloqueado_em_funcionarios_e_auditoria(self):
        self.autenticar("u", self.ids["vend"])
        resp_func = self.client.get("/api/funcionarios/")
        self.assertEqual(resp_func.status_code, 403)

        resp_audit = self.client.get("/api/auditoria/")
        self.assertEqual(resp_audit.status_code, 403)

    def test_gerente_bloqueado_em_auditoria_e_funcionarios(self):
        self.autenticar("u", self.ids["ger"])
        resp_func = self.client.get("/api/funcionarios/")
        self.assertEqual(resp_func.status_code, 403)

        resp_audit = self.client.get("/api/auditoria/")
        self.assertEqual(resp_audit.status_code, 403)

    def test_proprietario_acessa_funcionarios_e_auditoria(self):
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
