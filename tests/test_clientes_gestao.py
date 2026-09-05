import unittest
from app import create_app
from app.extensions import db, limiter
from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.services.rbac import ROLE_PROPRIETARIO, ROLE_VENDEDOR


class ClientesGestaoTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app("testing")
        limiter.enabled = False
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()

            self.admin = Usuario(
                nome="Admin Teste",
                login="admin_cli",
                cargo=ROLE_PROPRIETARIO,
                nivel_acesso="gestor",
                ativo=True,
            )
            self.admin.set_senha("AdminTeste123!")

            self.vendedor = Usuario(
                nome="Vendedor Teste",
                login="vend_cli",
                cargo=ROLE_VENDEDOR,
                nivel_acesso="vendedor",
                ativo=True,
            )
            self.vendedor.set_senha("VendTeste123!")

            self.c1 = Cliente(nome="Beatriz Souza", telefone="11999990001", email="beatriz@teste.com", pontos_acumulados=100, ativo=True)
            self.c1.set_senha("CliSenha123!")

            self.c2 = Cliente(nome="Bruno Lima", telefone="11999990002", email="bruno@teste.com", pontos_acumulados=50, ativo=True)
            self.c2.set_senha("CliSenha123!")

            self.c3 = Cliente(nome="Carla Dias", telefone="11999990003", email="carla@teste.com", pontos_acumulados=200, ativo=False)
            self.c3.set_senha("CliSenha123!")

            db.session.add_all([self.admin, self.vendedor, self.c1, self.c2, self.c3])
            db.session.commit()

            self.admin_id = self.admin.id_usuario
            self.vend_id = self.vendedor.id_usuario
            self.c1_id = self.c1.id_cliente
            self.c2_id = self.c2.id_cliente
            self.c3_id = self.c3.id_cliente

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def autenticar(self, prefixo, user_id):
        with self.client.session_transaction() as sess:
            sess["_user_id"] = f"{prefixo}_{user_id}"
            sess["_fresh"] = True

    def test_listar_clientes_com_busca(self):
        self.autenticar("u", self.admin_id)
        resp = self.client.get("/api/clientes/?q=beatriz")
        self.assertEqual(resp.status_code, 200)
        items = resp.get_json()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["nome"], "Beatriz Souza")

    def test_listar_clientes_filtro_status(self):
        self.autenticar("u", self.admin_id)
        resp_ativos = self.client.get("/api/clientes/?status=ativo")
        self.assertEqual(resp_ativos.status_code, 200)
        self.assertEqual(len(resp_ativos.get_json()), 2)

        resp_inativos = self.client.get("/api/clientes/?status=inativo")
        self.assertEqual(resp_inativos.status_code, 200)
        self.assertEqual(len(resp_inativos.get_json()), 1)
        self.assertEqual(resp_inativos.get_json()[0]["nome"], "Carla Dias")

    def test_listar_clientes_paginacao(self):
        self.autenticar("u", self.admin_id)
        resp = self.client.get("/api/clientes/?page=1&per_page=2")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["total"], 3)
        self.assertEqual(len(data["items"]), 2)

    def test_obter_detalhes_cliente(self):
        self.autenticar("u", self.admin_id)
        resp = self.client.get(f"/api/clientes/{self.c1_id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["nome"], "Beatriz Souza")
        self.assertIn("total_compras", data)
        self.assertIn("total_resgates", data)

    def test_editar_cliente_sucesso(self):
        self.autenticar("u", self.admin_id)
        resp = self.client.put(
            f"/api/clientes/{self.c1_id}",
            json={"nome": "Beatriz Souza Santos", "endereco": "Av Paulista, 1000"}
        )
        self.assertEqual(resp.status_code, 200)
        with self.app.app_context():
            cli = db.session.get(Cliente, self.c1_id)
            self.assertEqual(cli.nome, "Beatriz Souza Santos")
            self.assertEqual(cli.endereco, "Av Paulista, 1000")

    def test_desativar_e_reativar_cliente(self):
        self.autenticar("u", self.admin_id)
        # Desativa
        resp = self.client.post(
            f"/api/clientes/{self.c1_id}/status",
            json={"ativo": False, "motivo": "Solicitação do cliente"}
        )
        self.assertEqual(resp.status_code, 200)
        with self.app.app_context():
            self.assertFalse(db.session.get(Cliente, self.c1_id).ativo)

        # Login de cliente desativado falha
        resp_login = self.client.post(
            "/auth/cliente/login",
            json={"telefone": "11999990001", "senha": "CliSenha123!"}
        )
        self.assertEqual(resp_login.status_code, 401)

        # Compra para cliente desativado falha
        resp_compra = self.client.post(
            "/api/compras/",
            json={"id_cliente": self.c1_id, "valor": 50}
        )
        self.assertEqual(resp_compra.status_code, 400)

        # Reativa
        resp_reativa = self.client.post(
            f"/api/clientes/{self.c1_id}/status",
            json={"ativo": True}
        )
        self.assertEqual(resp_reativa.status_code, 200)
        with self.app.app_context():
            self.assertTrue(db.session.get(Cliente, self.c1_id).ativo)


if __name__ == "__main__":
    unittest.main()
