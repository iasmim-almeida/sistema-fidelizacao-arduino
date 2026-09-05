import unittest
from app import create_app
from app.extensions import db, limiter
from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.models.auditoria import Auditoria
from app.services.rbac import ROLE_PROPRIETARIO, ROLE_VENDEDOR
from app.services.auditoria import registrar_auditoria


class AuditoriaTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app("testing")
        limiter.enabled = False
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()

            self.admin = Usuario(
                nome="Admin Auditor",
                login="admin_aud",
                cargo=ROLE_PROPRIETARIO,
                nivel_acesso="gestor",
                ativo=True,
            )
            self.admin.set_senha("AdminAuditor@2026")

            self.vendedor = Usuario(
                nome="Vendedor Auditor",
                login="vend_aud",
                cargo=ROLE_VENDEDOR,
                nivel_acesso="vendedor",
                ativo=True,
            )
            self.vendedor.set_senha("VendAuditor@2026")

            self.cliente = Cliente(
                nome="Cliente Aud",
                telefone="11988880001",
                pontos_acumulados=50,
                ativo=True,
            )
            self.cliente.set_senha("CliAudSenha@123")

            db.session.add_all([self.admin, self.vendedor, self.cliente])
            db.session.commit()

            self.admin_id = self.admin.id_usuario
            self.vend_id = self.vendedor.id_usuario
            self.cliente_id = self.cliente.id_cliente

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def autenticar(self, prefixo, user_id):
        with self.client.session_transaction() as sess:
            sess["_user_id"] = f"{prefixo}_{user_id}"
            sess["_fresh"] = True

    def test_sanitizacao_dados_sensiveis(self):
        with self.app.app_context():
            reg = registrar_auditoria(
                acao="TESTE_SENSIVEL",
                entidade="seguranca",
                detalhes={
                    "usuario": "teste",
                    "senha": "MinhaSenhaSuperSecreta123!",
                    "senha_hash": "argon2$fakehash",
                    "token": "secret_token_abc",
                },
                usuario_id=self.admin_id,
            )
            db.session.commit()

            self.assertIsNotNone(reg)
            self.assertNotIn("MinhaSenhaSuperSecreta123!", reg.detalhes)
            self.assertNotIn("argon2$fakehash", reg.detalhes)
            self.assertIn("[REMOVIDO_POR_SEGURANCA]", reg.detalhes)

    def test_auditoria_em_acoes_administrativas(self):
        self.autenticar("u", self.admin_id)

        # 1. Ajuste de pontos
        self.client.post(
            f"/api/clientes/{self.cliente_id}/pontos/ajuste",
            json={"operacao": "adicionar", "quantidade": 20, "motivo": "Premio de fidelidade"}
        )

        with self.app.app_context():
            reg = Auditoria.query.filter_by(entidade="cliente", entidade_id=str(self.cliente_id)).first()
            self.assertIsNotNone(reg)
            self.assertIn("AJUSTE_PONTOS", reg.acao)

    def test_auditoria_consulta_paginada(self):
        with self.app.app_context():
            for i in range(5):
                registrar_auditoria(
                    acao=f"ACAO_TESTE_{i}",
                    entidade="teste",
                    entidade_id=str(i),
                    usuario_id=self.admin_id,
                )
            db.session.commit()

        self.autenticar("u", self.admin_id)
        resp = self.client.get("/api/auditoria/?per_page=3&page=1")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertGreaterEqual(data["total"], 5)
        self.assertEqual(len(data["items"]), 3)

    def test_auditoria_acesso_restrito(self):
        # Vendedor não pode visualizar auditoria
        self.autenticar("u", self.vend_id)
        resp = self.client.get("/api/auditoria/")
        self.assertEqual(resp.status_code, 403)


if __name__ == "__main__":
    unittest.main()
