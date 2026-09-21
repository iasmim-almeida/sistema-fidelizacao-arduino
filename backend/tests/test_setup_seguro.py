import os
import sys
import unittest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app import create_app
from app.extensions import db, limiter
from app.models.usuario import Usuario
from app.models.auditoria import Auditoria
from app.services.rbac import ROLE_VENDEDORA


class SetupSeguroTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app("testing")
        limiter.enabled = False
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_get_setup_permitido_quando_sem_admin(self):
        resp = self.client.get("/setup")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Cadastro Inicial Seguro", resp.data)

    def test_post_setup_senha_fraca_rejeitada(self):
        payload = {
            "nome": "Vendedora Chefe",
            "login": "vendedora_chefe",
            "email": "chefe@loja.com",
            "senha": "1234",
            "confirmar_senha": "1234",
        }
        resp = self.client.post("/setup", json=payload)
        self.assertEqual(resp.status_code, 400)
        with self.app.app_context():
            self.assertEqual(Usuario.query.count(), 0)

    def test_post_setup_confirmacao_invalida_rejeitada(self):
        payload = {
            "nome": "Vendedora Chefe",
            "login": "vendedora_chefe",
            "email": "chefe@loja.com",
            "senha": "SenhaForte@2026",
            "confirmar_senha": "OutraSenha@2026",
        }
        resp = self.client.post("/setup", json=payload)
        self.assertEqual(resp.status_code, 400)

    def test_setup_sucesso_cria_vendedora_admin(self):
        payload = {
            "nome": "Vendedora Administradora",
            "login": "vendedora_admin",
            "email": "admin@loja.com",
            "senha": "SenhaSegura@2026",
            "confirmar_senha": "SenhaSegura@2026",
        }
        resp = self.client.post("/setup", json=payload)
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertIn("sucesso", data["mensagem"].lower())

        with self.app.app_context():
            u = Usuario.query.filter_by(login="vendedora_admin").first()
            self.assertIsNotNone(u)
            self.assertTrue(u.is_vendedora)
            self.assertEqual(u.cargo, ROLE_VENDEDORA)
            self.assertEqual(u.nivel_acesso, "ADMIN")
            self.assertTrue(u.verificar_senha("SenhaSegura@2026"))

            # Auditoria registrada
            audit = Auditoria.query.filter_by(acao="CADASTRO_INICIAL_VENDEDORA_ADMIN").first()
            self.assertIsNotNone(audit)
            self.assertEqual(audit.id_usuario, u.id_usuario)

    def test_setup_bloqueado_apos_primeiro_admin(self):
        # 1. Cria primeiro admin
        with self.app.app_context():
            u = Usuario(
                nome="Primeira Vendedora",
                login="vendedora1",
                email="v1@loja.com",
                cargo=ROLE_VENDEDORA,
                nivel_acesso="ADMIN",
                ativo=True,
            )
            u.set_senha("SenhaForte@2026")
            db.session.add(u)
            db.session.commit()

        # 2. Tentativa subsequente via GET é redirecionada
        resp_get = self.client.get("/setup")
        self.assertEqual(resp_get.status_code, 302)

        # 3. Tentativa subsequente via POST JSON é rejeitada com 403
        payload = {
            "nome": "Segunda Vendedora",
            "login": "vendedora2",
            "email": "v2@loja.com",
            "senha": "SenhaForte@2026",
            "confirmar_senha": "SenhaForte@2026",
        }
        resp_post = self.client.post("/setup", json=payload)
        self.assertEqual(resp_post.status_code, 403)
        self.assertIn("concluído", resp_post.get_json()["erro"].lower())


if __name__ == "__main__":
    unittest.main()
