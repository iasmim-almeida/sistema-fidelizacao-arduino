import unittest

from app import create_app
from app.extensions import db
from app.models.usuario import Usuario
from app.services.rbac import PERMISSOES, ROLE_VENDEDORA, usuario_tem_permissao


class RBACTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app("testing")
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            self.admin = Usuario(
                nome="Vendedora Teste",
                login="vendedora_teste",
                email="vendedora@teste.com",
                cargo=ROLE_VENDEDORA,
                nivel_acesso="ADMIN",
                ativo=True,
            )
            self.admin.set_senha("VendedoraTeste123!")
            self.inativa = Usuario(
                nome="Vendedora Inativa",
                login="vendedora_inativa",
                email="inativa@teste.com",
                cargo=ROLE_VENDEDORA,
                nivel_acesso="ADMIN",
                ativo=False,
            )
            self.inativa.set_senha("InativaTeste123!")
            self.cliente = Usuario(
                nome="Cliente Teste",
                login="11999990001",
                telefone="11999990001",
                cargo="cliente",
                nivel_acesso="CLIENTE",
                ativo=True,
            )
            self.cliente.set_senha("ClienteTeste123!")
            db.session.add_all([self.admin, self.inativa, self.cliente])
            db.session.commit()
            self.ids = {
                "admin": self.admin.id_usuario,
                "inativa": self.inativa.id_usuario,
                "cliente": self.cliente.id_usuario,
            }

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_admin_ativo_possui_permissoes_operacionais(self):
        with self.app.app_context():
            admin = db.session.get(Usuario, self.ids["admin"])
            self.assertNotIn("auditoria.visualizar", PERMISSOES)
            for permissao in PERMISSOES:
                self.assertTrue(usuario_tem_permissao(admin, permissao), permissao)

    def test_cliente_e_admin_inativo_nao_possuem_permissoes(self):
        with self.app.app_context():
            cliente = db.session.get(Usuario, self.ids["cliente"])
            inativa = db.session.get(Usuario, self.ids["inativa"])
            for permissao in PERMISSOES:
                self.assertFalse(usuario_tem_permissao(cliente, permissao), permissao)
                self.assertFalse(usuario_tem_permissao(inativa, permissao), permissao)

    def test_modulos_removidos_nao_possuem_rotas(self):
        for rota in ("/funcionarios", "/api/funcionarios/", "/api/auditoria/"):
            with self.subTest(rota=rota):
                self.assertEqual(self.client.get(rota).status_code, 404)


if __name__ == "__main__":
    unittest.main()
