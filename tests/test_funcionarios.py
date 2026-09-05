import unittest
from app import create_app
from app.extensions import db, limiter
from app.models.usuario import Usuario
from app.services.rbac import ROLE_PROPRIETARIO, ROLE_GERENTE, ROLE_VENDEDOR


class FuncionariosTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app("testing")
        limiter.enabled = False
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()

            self.admin = Usuario(
                nome="Admin Chefe",
                login="admin_chefe",
                email="chefe@loja.com",
                cargo=ROLE_PROPRIETARIO,
                nivel_acesso="gestor",
                ativo=True,
            )
            self.admin.set_senha("ChefeFideliZa@2026")

            self.gerente = Usuario(
                nome="Gerente Ana",
                login="gerente_ana",
                email="ana@loja.com",
                cargo=ROLE_GERENTE,
                nivel_acesso="gerente",
                ativo=True,
            )
            self.gerente.set_senha("GerenteFideliZa@2026")

            self.vendedor = Usuario(
                nome="Vendedor Carlos",
                login="vendedor_carlos",
                email="carlos@loja.com",
                cargo=ROLE_VENDEDOR,
                nivel_acesso="vendedor",
                ativo=True,
            )
            self.vendedor.set_senha("VendedorFideliZa@2026")

            db.session.add_all([self.admin, self.gerente, self.vendedor])
            db.session.commit()

            self.admin_id = self.admin.id_usuario
            self.gerente_id = self.gerente.id_usuario
            self.vendedor_id = self.vendedor.id_usuario

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def autenticar(self, user_id):
        with self.client.session_transaction() as sess:
            sess["_user_id"] = f"u_{user_id}"
            sess["_fresh"] = True

    def test_listar_funcionarios(self):
        self.autenticar(self.admin_id)
        resp = self.client.get("/api/funcionarios/")
        self.assertEqual(resp.status_code, 200)
        dados = resp.get_json()
        self.assertEqual(len(dados), 3)

    def test_criar_funcionario_sucesso(self):
        self.autenticar(self.admin_id)
        payload = {
            "nome": "Novo Vendedor",
            "login": "novo_vend",
            "email": "novo@loja.com",
            "cargo": "vendedor",
            "senha": "SenhaForte@2026",
        }
        resp = self.client.post("/api/funcionarios/", json=payload)
        self.assertEqual(resp.status_code, 201)
        with self.app.app_context():
            u = Usuario.query.filter_by(login="novo_vend").first()
            self.assertIsNotNone(u)
            self.assertTrue(u.verificar_senha("SenhaForte@2026"))
            self.assertEqual(u.cargo, "vendedor")

    def test_criar_funcionario_senha_fraca_rejeitada(self):
        self.autenticar(self.admin_id)
        payload = {
            "nome": "Fraco Vendedor",
            "login": "fraco_vend",
            "cargo": "vendedor",
            "senha": "1234",
        }
        resp = self.client.post("/api/funcionarios/", json=payload)
        self.assertEqual(resp.status_code, 400)

    def test_criar_funcionario_duplicado_rejeitado(self):
        self.autenticar(self.admin_id)
        payload = {
            "nome": "Duplicado",
            "login": "admin_chefe",
            "cargo": "vendedor",
            "senha": "SenhaForte@2026",
        }
        resp = self.client.post("/api/funcionarios/", json=payload)
        self.assertEqual(resp.status_code, 409)

    def test_prevencao_privilege_escalation(self):
        # Vendedor tenta criar usuário
        self.autenticar(self.vendedor_id)
        payload = {
            "nome": "Invasor",
            "login": "invasor",
            "cargo": "proprietario",
            "senha": "SenhaForte@2026",
        }
        resp = self.client.post("/api/funcionarios/", json=payload)
        self.assertEqual(resp.status_code, 403)

    def test_editar_funcionario(self):
        self.autenticar(self.admin_id)
        resp = self.client.put(
            f"/api/funcionarios/{self.vendedor_id}",
            json={"nome": "Carlos Atualizado", "email": "carlos.novo@loja.com"}
        )
        self.assertEqual(resp.status_code, 200)
        with self.app.app_context():
            u = db.session.get(Usuario, self.vendedor_id)
            self.assertEqual(u.nome, "Carlos Atualizado")
            self.assertEqual(u.email, "carlos.novo@loja.com")

    def test_desativar_e_reativar_funcionario(self):
        self.autenticar(self.admin_id)
        # Desativa
        resp = self.client.post(
            f"/api/funcionarios/{self.vendedor_id}/status",
            json={"ativo": False}
        )
        self.assertEqual(resp.status_code, 200)
        with self.app.app_context():
            self.assertFalse(db.session.get(Usuario, self.vendedor_id).ativo)

        # Login de usuário inativo deve falhar
        resp_login = self.client.post(
            "/auth/login",
            json={"login": "vendedor_carlos", "senha": "VendedorFideliZa@2026"}
        )
        self.assertEqual(resp_login.status_code, 401)
        self.assertIn("inativa", resp_login.get_json()["erro"].lower())

        # Reativa
        resp_reativa = self.client.post(
            f"/api/funcionarios/{self.vendedor_id}/status",
            json={"ativo": True}
        )
        self.assertEqual(resp_reativa.status_code, 200)
        with self.app.app_context():
            self.assertTrue(db.session.get(Usuario, self.vendedor_id).ativo)

    def test_impedir_autodesativacao(self):
        self.autenticar(self.admin_id)
        resp = self.client.post(
            f"/api/funcionarios/{self.admin_id}/status",
            json={"ativo": False}
        )
        self.assertEqual(resp.status_code, 400)

    def test_impedir_desativar_unico_proprietario(self):
        self.autenticar(self.admin_id)
        # Tenta desativar o único proprietário passando ID
        resp = self.client.post(
            f"/api/funcionarios/{self.admin_id}/status",
            json={"ativo": False}
        )
        self.assertEqual(resp.status_code, 400)

    def test_redefinir_senha_funcionario(self):
        self.autenticar(self.admin_id)
        resp = self.client.post(
            f"/api/funcionarios/{self.vendedor_id}/reset-senha",
            json={"nova_senha": "NovaSenhaSegura@2026"}
        )
        self.assertEqual(resp.status_code, 200)
        with self.app.app_context():
            u = db.session.get(Usuario, self.vendedor_id)
            self.assertTrue(u.verificar_senha("NovaSenhaSegura@2026"))
            self.assertTrue(u.precisa_trocar_senha)


if __name__ == "__main__":
    unittest.main()
