"""
Testes automatizados para a funcionalidade de cadastro de clientes.
Cobre rendering da página, validações do formulário, persistência no banco,
e fluxo completo de registro → login.
"""
import unittest
from app import create_app
from app.extensions import db as _db, limiter
from app.models.cliente import Cliente


class BaseCadastroTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app("testing")
        limiter.enabled = False
        self.client = self.app.test_client()
        with self.app.app_context():
            _db.create_all()

    def tearDown(self):
        with self.app.app_context():
            _db.session.remove()
            _db.drop_all()



# ───────────────────── Renderização da Página ─────────────────────

class TestCadastroPageRendering(BaseCadastroTestCase):
    def test_get_cadastro_returns_200(self):
        """GET /auth/cadastro deve renderizar a página de cadastro."""
        resp = self.client.get("/auth/cadastro")
        assert resp.status_code == 200

    def test_get_cadastro_contains_form(self):
        """A página deve conter o formulário com campos obrigatórios."""
        resp = self.client.get("/auth/cadastro")
        body = resp.data.decode("utf-8")
        assert "nome" in body.lower()
        assert "telefone" in body.lower()
        assert "senha" in body.lower()

    def test_get_cadastro_csrf_in_non_testing(self):
        """Em modo não-testing, o formulário deve ter proteção CSRF ativa."""
        # CSRF token é desabilitado em TestingConfig (WTF_CSRF_ENABLED=False)
        # Validamos que o campo existe quando CSRF está ativo
        from app import create_app as _create_app
        app = _create_app("development")
        with app.app_context():
            with app.test_client() as c:
                resp = c.get("/auth/cadastro")
                body = resp.data.decode("utf-8")
                assert "csrf_token" in body, "CSRF token ausente em modo development"


# ───────────────────── Cadastro com Sucesso ─────────────────────

class TestCadastroSuccess(BaseCadastroTestCase):
    def test_valid_registration_redirects(self):
        """Cadastro válido redireciona para a página inicial."""
        resp = self.client.post("/auth/cadastro", data={
            "nome": "Maria Santos",
            "telefone": "11999887766",
            "senha": "SenhaForte1",
            "confirmar_senha": "SenhaForte1",
        }, follow_redirects=False)
        assert resp.status_code == 302
        assert "/" in resp.headers.get("Location", "")

    def test_valid_registration_creates_client(self):
        """Cadastro válido persiste o cliente no banco."""
        self.client.post("/auth/cadastro", data={
            "nome": "Joana Lima",
            "telefone": "21988776655",
            "senha": "TesteSeg1",
            "confirmar_senha": "TesteSeg1",
        })
        with self.app.app_context():
            cl = Cliente.query.filter_by(telefone="21988776655").first()
            assert cl is not None, "Cliente não foi criado no banco"
            assert cl.nome == "Joana Lima"
            assert cl.pontos_acumulados == 0
            assert cl.senha_hash is not None

    def test_valid_registration_stores_hashed_password(self):
        """A senha deve ser armazenada como hash, nunca em texto puro."""
        self.client.post("/auth/cadastro", data={
            "nome": "Ana Costa",
            "telefone": "31977665544",
            "senha": "MinhaSenh4",
            "confirmar_senha": "MinhaSenh4",
        })
        with self.app.app_context():
            cl = Cliente.query.filter_by(telefone="31977665544").first()
            assert cl.senha_hash != "MinhaSenh4", "Senha armazenada em texto puro!"
            assert cl.verificar_senha("MinhaSenh4"), "Hash não corresponde à senha"

    def test_phone_stored_digits_only(self):
        """O telefone deve ser armazenado apenas com dígitos."""
        self.client.post("/auth/cadastro", data={
            "nome": "Paula Reis",
            "telefone": "(41) 98765-4321",
            "senha": "Segura123",
            "confirmar_senha": "Segura123",
        })
        with self.app.app_context():
            cl = Cliente.query.filter_by(telefone="41987654321").first()
            assert cl is not None, "Telefone não foi normalizado para dígitos"

    def test_success_flash_message(self):
        """Mensagem flash de sucesso deve ser exibida após cadastro."""
        resp = self.client.post("/auth/cadastro", data={
            "nome": "Flash Test",
            "telefone": "51966554433",
            "senha": "Teste1234",
            "confirmar_senha": "Teste1234",
        }, follow_redirects=True)
        body = resp.data.decode("utf-8")
        assert "sucesso" in body.lower() or "Cadastro realizado" in body


# ───────────────────── Validações do Formulário ─────────────────────

class TestCadastroValidation(BaseCadastroTestCase):
    def test_empty_fields_rejected(self):
        """Campos vazios devem ser rejeitados com mensagem de erro."""
        resp = self.client.post("/auth/cadastro", data={
            "nome": "",
            "telefone": "",
            "senha": "",
            "confirmar_senha": "",
        })
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        assert "obrigatori" in body.lower()

    def test_short_name_rejected(self):
        """Nome com menos de 3 caracteres deve ser rejeitado."""
        resp = self.client.post("/auth/cadastro", data={
            "nome": "AB",
            "telefone": "11999000111",
            "senha": "Teste1234",
            "confirmar_senha": "Teste1234",
        })
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        assert "3" in body  # deve mencionar mínimo de 3 caracteres

    def test_invalid_phone_format_rejected(self):
        """Telefone com formato inválido deve ser rejeitado."""
        resp = self.client.post("/auth/cadastro", data={
            "nome": "Teste Phone",
            "telefone": "123",
            "senha": "Teste1234",
            "confirmar_senha": "Teste1234",
        })
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        assert "formato" in body.lower() or "invalido" in body.lower()

    def test_short_password_rejected(self):
        """Senha com menos de 8 caracteres deve ser rejeitada."""
        resp = self.client.post("/auth/cadastro", data={
            "nome": "Teste Curto",
            "telefone": "11888111222",
            "senha": "Ab1",
            "confirmar_senha": "Ab1",
        })
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        assert "8" in body

    def test_password_without_letter_rejected(self):
        """Senha sem letras (apenas números) deve ser rejeitada."""
        resp = self.client.post("/auth/cadastro", data={
            "nome": "Teste Digits",
            "telefone": "11777111222",
            "senha": "99887766",
            "confirmar_senha": "99887766",
        })
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        assert "letra" in body.lower() or "numero" in body.lower()

    def test_common_password_rejected(self):
        """Senhas comuns (12345678, password, etc.) devem ser rejeitadas."""
        resp = self.client.post("/auth/cadastro", data={
            "nome": "Teste Comum",
            "telefone": "11666111222",
            "senha": "12345678",
            "confirmar_senha": "12345678",
        })
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        assert "insegura" in body.lower() or "comum" in body.lower()

    def test_password_mismatch_rejected(self):
        """Senhas que não conferem devem ser rejeitadas."""
        resp = self.client.post("/auth/cadastro", data={
            "nome": "Teste Mismatch",
            "telefone": "11555111222",
            "senha": "SenhaA123",
            "confirmar_senha": "SenhaB456",
        })
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        assert "nao conferem" in body.lower()

    def test_duplicate_phone_rejected(self):
        """Telefone já cadastrado deve ser rejeitado."""
        # Primeiro cadastro
        self.client.post("/auth/cadastro", data={
            "nome": "Primeiro User",
            "telefone": "11944411222",
            "senha": "Primeira1",
            "confirmar_senha": "Primeira1",
        })
        # Segundo cadastro com mesmo telefone
        resp = self.client.post("/auth/cadastro", data={
            "nome": "Segundo User",
            "telefone": "11944411222",
            "senha": "Segunda22",
            "confirmar_senha": "Segunda22",
        })
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        assert "ja esta cadastrado" in body.lower()


# ───────────────────── Redirecionamento de Usuário Autenticado ─────────────────────

class TestCadastroAuthenticatedRedirect(BaseCadastroTestCase):
    def test_authenticated_client_redirected(self):
        """Usuário autenticado como cliente é redirecionado ao acessar cadastro."""
        # Cadastrar e logar
        self.client.post("/auth/cadastro", data={
            "nome": "Auth Test",
            "telefone": "11933311222",
            "senha": "AuthTest1",
            "confirmar_senha": "AuthTest1",
        })
        self.client.post("/auth/cliente/login",
            json={"telefone": "11933311222", "senha": "AuthTest1"},
            content_type="application/json")

        resp = self.client.get("/auth/cadastro")
        assert resp.status_code == 302, "Deveria redirecionar usuário autenticado"


# ───────────────────── Fluxo Completo: Cadastro → Login ─────────────────────

class TestCadastroLoginFlow(BaseCadastroTestCase):
    def test_register_then_login_succeeds(self):
        """Após cadastro, o cliente deve conseguir fazer login."""
        self.client.post("/auth/cadastro", data={
            "nome": "Flow Test",
            "telefone": "11922211333",
            "senha": "FlowTest9",
            "confirmar_senha": "FlowTest9",
        })
        resp = self.client.post("/auth/cliente/login",
            json={"telefone": "11922211333", "senha": "FlowTest9"},
            content_type="application/json")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["tipo"] == "cliente"
        assert data["cliente"]["telefone"] == "11922211333"


if __name__ == "__main__":
    unittest.main()
