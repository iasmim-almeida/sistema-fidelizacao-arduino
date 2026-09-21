"""
Testes automatizados para a funcionalidade:
- Cadastro de clientes pela vendedora com senha inicial.
- Identificação de cadastro pela vendedora no login do cliente.
- Solicitação e obrigatoriedade da troca de senha no primeiro acesso.
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
from app.services.rbac import ROLE_VENDEDOR, ROLE_PROPRIETARIO


class ClientePrimeiroAcessoTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app("testing")
        limiter.enabled = False
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()

            # Vendedora
            self.vendedora = Usuario(
                nome="Vendedora Loja",
                login="vendedora_1",
                email="vendedora@loja.com",
                cargo=ROLE_VENDEDOR,
                nivel_acesso="vendedor",
                ativo=True,
            )
            self.vendedora.set_senha("Vendedora123!")
            db.session.add(self.vendedora)
            db.session.commit()
            self.vendedora_id = self.vendedora.id_usuario

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def autenticar_vendedora(self):
        with self.client.session_transaction() as sess:
            sess["_user_id"] = f"u_{self.vendedora_id}"
            sess["_fresh"] = True

    def autenticar_cliente(self, cliente_id):
        with self.client.session_transaction() as sess:
            sess["_user_id"] = f"c_{cliente_id}"
            sess["_fresh"] = True

    def test_vendedora_cadastra_cliente_com_senha(self):
        """Vendedora cadastra cliente com senha inicial e flag precisa_trocar_senha é True."""
        self.autenticar_vendedora()
        resp = self.client.post("/api/clientes/", json={
            "nome": "Carlos Cliente",
            "telefone": "11988887777",
            "email": "carlos@teste.com",
            "endereco": "Rua das Flores, 50",
            "senha": "SenhaInicial123"
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertTrue(data.get("precisa_trocar_senha"))

        with self.app.app_context():
            cli = Cliente.query.filter_by(telefone="11988887777").first()
            self.assertIsNotNone(cli)
            self.assertTrue(cli.precisa_trocar_senha)
            self.assertTrue(cli.verificar_senha("SenhaInicial123"))

    def test_cadastro_cliente_com_senha_invalida_falha(self):
        """Senha inicial que não atende aos requisitos mínimos deve ser rejeitada."""
        self.autenticar_vendedora()
        resp = self.client.post("/api/clientes/", json={
            "nome": "Carlos Cliente",
            "telefone": "11988887777",
            "senha": "123"
        })
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("erro", data)

    def test_login_cliente_identifica_cadastro_vendedora_e_solicita_troca(self):
        """Ao fazer login, o sistema identifica que a vendedora cadastrou e redireciona para troca de senha."""
        # 1. Cadastra cliente
        self.autenticar_vendedora()
        self.client.post("/api/clientes/", json={
            "nome": "Marina Silva",
            "telefone": "11977776666",
            "senha": "SenhaInicial123"
        })

        # Desloga vendedora
        self.client.get("/auth/logout")

        # 2. Cliente faz login com a senha informada pela vendedora
        resp_login = self.client.post("/auth/cliente/login", json={
            "telefone": "11977776666",
            "senha": "SenhaInicial123"
        })
        self.assertEqual(resp_login.status_code, 200)
        data = resp_login.get_json()
        self.assertTrue(data.get("precisa_trocar_senha"))
        self.assertTrue(data.get("cadastrado_por_vendedora"))
        self.assertEqual(data.get("redirect"), "/cliente/trocar-senha")

    def test_bloqueio_navegacao_enquanto_precisa_trocar_senha(self):
        """Cliente com precisa_trocar_senha é bloqueado ao tentar navegar para /bemvindo."""
        # Cadastra cliente
        self.autenticar_vendedora()
        res = self.client.post("/api/clientes/", json={
            "nome": "Roberta Lima",
            "telefone": "11966665555",
            "senha": "SenhaInicial123"
        })
        cliente_id = res.get_json()["id_cliente"]

        # Autentica como cliente
        self.autenticar_cliente(cliente_id)

        # Tentativa de acessar /bemvindo deve redirecionar para /cliente/trocar-senha
        resp = self.client.get("/bemvindo")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/cliente/trocar-senha", resp.headers.get("Location", ""))

        # Rota de troca de senha deve responder 200 OK
        resp_troca = self.client.get("/cliente/trocar-senha")
        self.assertEqual(resp_troca.status_code, 200)
        self.assertIn("Cadastrar Nova Senha", resp_troca.data.decode("utf-8"))

    def test_fluxo_completo_troca_senha_desbloqueia_cliente(self):
        """Após realizar a troca da senha, o cliente tem livre acesso ao sistema."""
        # 1. Cadastra cliente pela vendedora
        self.autenticar_vendedora()
        res = self.client.post("/api/clientes/", json={
            "nome": "Fernando Dias",
            "telefone": "11955554444",
            "senha": "SenhaInicial123"
        })
        cliente_id = res.get_json()["id_cliente"]

        # 2. Autentica cliente
        self.autenticar_cliente(cliente_id)

        # 3. Executa alteração da senha
        resp_alt = self.client.post("/api/clientes/me/alterar-senha", json={
            "senha_atual": "SenhaInicial123",
            "nova_senha": "MinhaNovaSenha1",
            "confirmar_nova_senha": "MinhaNovaSenha1"
        })
        self.assertEqual(resp_alt.status_code, 200)

        # 4. Verifica no banco que precisa_trocar_senha agora é False
        with self.app.app_context():
            cli = db.session.get(Cliente, cliente_id)
            self.assertFalse(cli.precisa_trocar_senha)
            self.assertTrue(cli.verificar_senha("MinhaNovaSenha1"))
            self.assertFalse(cli.verificar_senha("SenhaInicial123"))

        # 5. Cliente agora consegue acessar /bemvindo sem redirecionamento
        resp_bemvindo = self.client.get("/bemvindo")
        self.assertEqual(resp_bemvindo.status_code, 200)

        # 6. Novo login com a nova senha não exige mais troca
        resp_login = self.client.post("/auth/cliente/login", json={
            "telefone": "11955554444",
            "senha": "MinhaNovaSenha1"
        })
        self.assertEqual(resp_login.status_code, 200)
        data_login = resp_login.get_json()
        self.assertFalse(data_login.get("precisa_trocar_senha"))
        self.assertEqual(data_login.get("redirect"), "/bemvindo")


if __name__ == "__main__":
    unittest.main()
