"""
Testes de QA e Segurança (OWASP Top 10, Validações de Entrada/Saída, Segregação de Autenticação e RBAC).
"""
import os
import sys
import unittest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app import create_app
from app.extensions import db, limiter
from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.services.rbac import ROLE_VENDEDORA, ROLE_VENDEDOR


class QASecurityHardeningTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app("testing")
        limiter.enabled = False
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()

            # Vendedora Administradora
            self.vendedora = Usuario(
                nome="Vendedora Teste",
                login="vendedora_seg",
                email="vendedora.seg@loja.com",
                cargo=ROLE_VENDEDORA,
                nivel_acesso="ADMIN",
                ativo=True,
            )
            self.vendedora.set_senha("VendedoraSeg123!")

            # Cliente
            self.cliente = Cliente(
                nome="Cliente Regular",
                telefone="11911112222",
                login="11911112222",
                email="cliente.reg@email.com",
                nivel_acesso="CLIENTE",
                cargo="cliente",
                ativo=True,
                pontos_acumulados=100,
            )
            self.cliente.set_senha("ClienteSeg123!")

            db.session.add_all([self.vendedora, self.cliente])
            db.session.commit()

            self.vendedora_id = self.vendedora.id_usuario
            self.cliente_id = self.cliente.id_cliente

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def autenticar_vendedora(self):
        with self.client.session_transaction() as sess:
            sess["_user_id"] = f"u_{self.vendedora_id}"
            sess["_fresh"] = True

    def autenticar_cliente(self):
        with self.client.session_transaction() as sess:
            sess["_user_id"] = f"c_{self.cliente_id}"
            sess["_fresh"] = True

    # ─────────────────────────────────────────────────────────────
    # 1. Segregação de Autenticação (OWASP A07 & A01)
    # ─────────────────────────────────────────────────────────────

    def test_cliente_bloqueado_no_login_vendedora(self):
        """Cliente não pode efetuar login através do endpoint administrativo de vendedora."""
        resp = self.client.post("/auth/login", json={
            "email": "cliente.reg@email.com",
            "senha": "ClienteSeg123!"
        })
        self.assertEqual(resp.status_code, 401)
        data = resp.get_json()
        self.assertIn("erro", data)
        self.assertIn("Credenciais de vendedora invalidas", data["erro"])

    def test_vendedora_bloqueada_no_login_cliente(self):
        """Vendedora/Admin não pode efetuar login através do endpoint exclusivo de clientes."""
        resp = self.client.post("/auth/cliente/login", json={
            "login": "vendedora_seg",
            "senha": "VendedoraSeg123!"
        })
        self.assertEqual(resp.status_code, 401)
        data = resp.get_json()
        self.assertIn("erro", data)
        self.assertEqual(data["erro"], "Telefone ou senha invalidos.")

    def test_logout_exige_post(self):
        """Logout altera estado somente via POST; GET não é permitido."""
        self.autenticar_cliente()
        resp_post = self.client.post("/auth/logout")
        self.assertIn(resp_post.status_code, [200, 302])

        self.autenticar_cliente()
        resp_get = self.client.get("/auth/logout")
        self.assertEqual(resp_get.status_code, 405)

    # ─────────────────────────────────────────────────────────────
    # 2. Cabeçalhos de Segurança HTTP (OWASP A05)
    # ─────────────────────────────────────────────────────────────

    def test_security_headers_presentes(self):
        """Garante a presença de cabeçalhos de segurança obrigatórios."""
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(resp.headers.get("X-Frame-Options"), "SAMEORIGIN")
        self.assertEqual(resp.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")
        self.assertIn("geolocation=()", resp.headers.get("Permissions-Policy", ""))
        self.assertEqual(resp.headers.get("Cross-Origin-Opener-Policy"), "same-origin")
        self.assertIn("default-src 'self'", resp.headers.get("Content-Security-Policy", ""))

    # ─────────────────────────────────────────────────────────────
    # 3. Validação de Input — Cadastro de Clientes (OWASP A03 / A04)
    # ─────────────────────────────────────────────────────────────

    def test_cadastrar_cliente_nome_curto_rejeitado(self):
        """Nome com menos de 3 caracteres deve ser rejeitado no cadastro pela vendedora."""
        self.autenticar_vendedora()
        resp = self.client.post("/api/clientes/", json={
            "nome": "Ab",
            "telefone": "11988880001",
            "senha": "SenhaValida123"
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("nome deve conter entre 3 e 120 caracteres", resp.get_json()["erro"].lower())

    def test_cadastrar_cliente_nome_muito_longo_rejeitado(self):
        """Nome com mais de 120 caracteres deve ser rejeitado."""
        self.autenticar_vendedora()
        resp = self.client.post("/api/clientes/", json={
            "nome": "A" * 121,
            "telefone": "11988880002",
            "senha": "SenhaValida123"
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("nome deve conter entre 3 e 120 caracteres", resp.get_json()["erro"].lower())

    def test_cadastrar_cliente_formato_email_invalido_rejeitado(self):
        """E-mail sem formato válido deve ser rejeitado no cadastro."""
        self.autenticar_vendedora()
        resp = self.client.post("/api/clientes/", json={
            "nome": "Cliente Teste",
            "telefone": "11988880003",
            "email": "email_invalido_sem_arroba",
            "senha": "SenhaValida123"
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("formato de e-mail invalido", resp.get_json()["erro"].lower())

    # ─────────────────────────────────────────────────────────────
    # 4. Validação de Input e Integridade — Compras (OWASP A01 / A04)
    # ─────────────────────────────────────────────────────────────

    def test_compras_rejeita_id_cliente_tipo_invalido(self):
        """id_cliente com tipo não inteiro (string não conversível, booleano, etc.) deve retornar 400."""
        self.autenticar_vendedora()
        resp = self.client.post("/api/compras/", json={
            "id_cliente": "nao_e_numero",
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("id_cliente deve ser um número inteiro", resp.get_json()["erro"])

    def test_compra_credita_um_ponto_sem_campo_financeiro(self):
        """Uma compra válida sem campo financeiro gera exatamente um ponto."""
        self.autenticar_vendedora()
        resp = self.client.post("/api/compras/", json={
            "id_cliente": self.cliente_id
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertEqual(data["pontos_adicionados"], 1)

    def test_compras_listar_segrega_por_perfil_e_bloqueia_cliente_em_outro_id(self):
        """Cliente autenticado só pode visualizar suas próprias compras."""
        self.autenticar_cliente()
        resp = self.client.get("/api/compras/")
        self.assertEqual(resp.status_code, 200)
        for item in resp.get_json():
            self.assertEqual(item["id_cliente"], self.cliente_id)

    # ─────────────────────────────────────────────────────────────
    # 5. Proteção contra Mass Assignment em Resgates (OWASP A04)
    # ─────────────────────────────────────────────────────────────

    def test_resgate_rejeita_campos_adicionais_custo_e_pontos(self):
        """Parâmetros manipulados pelo cliente (como custo arbitrário) devem ser rejeitados."""
        self.autenticar_vendedora()
        resp = self.client.post("/api/resgates/", json={
            "id_cliente": self.cliente_id,
            "id_recompensa": 1,
            "custo_pontos": 0,  # Campo não permitido
            "saldo_posterior": 999999  # Mass assignment não permitido
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("resgate aceita apenas", resp.get_json()["erro"].lower())


if __name__ == "__main__":
    unittest.main()
