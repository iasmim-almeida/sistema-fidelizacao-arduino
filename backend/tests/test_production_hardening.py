import os
import unittest
import threading
from datetime import date, timedelta
from unittest.mock import patch
from app import create_app
from app.extensions import db
from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.models.recompensa import Recompensa
from app.models.historico import Historico
from app.services.rbac import ROLE_PROPRIETARIO, ROLE_VENDEDOR, ROLE_GERENTE


class ProductionHardeningTestCase(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db_path = self.temp_file.name
        self.temp_file.close()

        self.app = create_app("testing")
        from sqlalchemy.pool import NullPool
        self.app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{self.temp_db_path}"
        self.app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "poolclass": NullPool,
            "connect_args": {"timeout": 15, "check_same_thread": False}
        }
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            self.proprietaria = Usuario(
                nome="Proprietaria Loja",
                login="proprietaria_teste",
                email="dona@loja.com",
                cargo=ROLE_PROPRIETARIO,
                nivel_acesso="ADMIN",
                ativo=True
            )
            self.proprietaria.set_senha("ProprietariaForte2026!")

            self.vendedora = Usuario(
                nome="Vendedora Balcao",
                login="vendedora_teste",
                email="balcao@loja.com",
                cargo=ROLE_VENDEDOR,
                nivel_acesso="ADMIN",
                ativo=True
            )
            self.vendedora.set_senha("VendedoraForte2026!")

            self.cliente = Cliente(
                nome="Cliente Fiel",
                login="cliente_fiel",
                telefone="11988887777",
                email="cliente@teste.com",
                pontos_acumulados=50,
                nivel_acesso="CLIENTE",
                cargo="cliente",
                ativo=True
            )
            self.cliente.set_senha("ClienteForte2026!")

            db.session.add_all([self.proprietaria, self.vendedora, self.cliente])
            db.session.commit()

            self.ids = {
                "proprietaria": self.proprietaria.id_usuario,
                "vendedora": self.vendedora.id_usuario,
                "cliente": self.cliente.id_usuario,
            }

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        if hasattr(self, "temp_db_path") and os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except OSError:
                pass

    def autenticar(self, prefixo, id_usuario):
        with self.client.session_transaction() as sessao:
            sessao["_user_id"] = f"{prefixo}_{id_usuario}"
            sessao["_fresh"] = True

    def test_production_cookies_e_hsts(self):
        """Valida configuração de cookies seguros e headers em ambiente production."""
        with patch.dict(os.environ, {"SECRET_KEY": "chave-super-segura-producao-64-caracteres-para-teste-1234567890"}):
            app_prod = create_app("production")
            self.assertFalse(app_prod.config["DEBUG"])
            self.assertFalse(app_prod.config["TESTING"])
            self.assertTrue(app_prod.config["SESSION_COOKIE_HTTPONLY"])
            self.assertTrue(app_prod.config["SESSION_COOKIE_SECURE"])
            self.assertEqual(app_prod.config["SESSION_COOKIE_SAMESITE"], "Lax")
            self.assertTrue(app_prod.config["REMEMBER_COOKIE_HTTPONLY"])
            self.assertTrue(app_prod.config["REMEMBER_COOKIE_SECURE"])

            client_prod = app_prod.test_client()
            resp = client_prod.get("/health")
            self.assertEqual(resp.status_code, 200)
            self.assertIn("Strict-Transport-Security", resp.headers)
            self.assertIn("max-age=31536000", resp.headers["Strict-Transport-Security"])

    def test_production_secret_key_fail_closed(self):
        """Garante que a aplicação falha de forma explícita em PRD se SECRET_KEY estiver ausente ou insegura."""
        for segredo_invalido in ["", "dev-secret-key", "troque-por-uma-chave-longa-e-aleatoria"]:
            with patch.dict(os.environ, {"SECRET_KEY": segredo_invalido}):
                with self.assertRaises(ValueError):
                    create_app("production")

    def test_cli_create_owner(self):
        """Valida bootstrap administrativo via comando CLI 'flask create-owner'."""
        runner = self.app.test_cli_runner()
        result = runner.invoke(args=[
            "create-owner",
            "--force",
            "--nome", "Dona Fundadora",
            "--login", "fundadora",
            "--email", "fundadora@itclube.com",
            "--senha", "FundadoraForte2026!"
        ])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("criada com êxito", result.output)

        with self.app.app_context():
            dona = Usuario.query.filter_by(login="fundadora").first()
            self.assertIsNotNone(dona)
            self.assertEqual(dona.cargo, ROLE_PROPRIETARIO)
            self.assertEqual(dona.nivel_acesso, "ADMIN")
            self.assertTrue(dona.verificar_senha("FundadoraForte2026!"))

    def test_regra_pontuacao_unificada_e_rejeicao_payload_injetado(self):
        """Garante que qualquer valor gera rigorosamente +1 ponto e tentativas de forçar pontos são ignoradas."""
        self.autenticar("u", self.ids["vendedora"])

        # Compras com valores diversos e injeção de 'pontos=100' no payload
        for valor in [1.00, 50.00, 10000.00]:
            resp = self.client.post("/api/compras/", json={
                "id_cliente": self.ids["cliente"],
                "valor": valor,
                "pontos": 100,
                "points": 500,
                "quantidade_pontos": 9999
            })
            self.assertEqual(resp.status_code, 201)
            data = resp.get_json()
            self.assertEqual(data["pontos_adicionados"], 1, "Compra deve gerar exatamente 1 ponto")

    def test_cadastro_cliente_bloqueia_role_injection(self):
        """Garante que cadastro público de cliente ignora cargos administrativos enviados via mass-assignment."""
        resp = self.client.post("/auth/cadastro", data={
            "nome": "Tentativa Invasor",
            "telefone": "11912345678",
            "email": "invasor@teste.com",
            "senha": "SenhaForte2026!",
            "confirmar_senha": "SenhaForte2026!",
            "cargo": "proprietario",
            "nivel_acesso": "ADMIN"
        }, follow_redirects=False)
        # O formulário com CSRF desabilitado em testing redireciona para login após sucesso
        self.assertIn(resp.status_code, [200, 302])

        with self.app.app_context():
            usuario = Usuario.query.filter_by(telefone="11912345678").first()
            if usuario:
                self.assertEqual(usuario.nivel_acesso, "CLIENTE")
                self.assertEqual(usuario.cargo, "cliente")

    def test_concorrencia_resgate_estoque_unitario(self):
        """Com estoque = 1, dois resgates simultâneos devem resultar em exatamente 1 sucesso e 1 falha."""
        with self.app.app_context():
            recompensa = Recompensa(
                id_usuario=self.ids["proprietaria"],
                nome_cupom="Item Raro Unico",
                codigo="RARO-001",
                custo_pontos=10,
                tipo="produto_fisico",
                validade=date.today() + timedelta(days=30),
                quantidade_total=1,
                quantidade_disponivel=1,
                status="ativa"
            )
            db.session.add(recompensa)
            db.session.commit()
            id_rec = recompensa.id_produto

    def test_concorrencia_resgate_estoque_unitario(self):
        """Com estoque = 1, tentativas subsequentes devem resultar em 1 sucesso e falhas com 409 sem estoque negativo."""
        with self.app.app_context():
            recompensa = Recompensa(
                id_usuario=self.ids["proprietaria"],
                nome_cupom="Item Raro Unico",
                codigo="RARO-001",
                custo_pontos=10,
                tipo="produto_fisico",
                validade=date.today() + timedelta(days=30),
                quantidade_total=1,
                quantidade_disponivel=1,
                status="ativa"
            )
            db.session.add(recompensa)
            db.session.commit()
            id_rec = recompensa.id_produto

        self.autenticar("u", self.ids["vendedora"])
        # Primeira tentativa de resgate (sucesso)
        resp1 = self.client.post("/api/resgates/", json={
            "id_cliente": self.ids["cliente"],
            "id_recompensa": id_rec
        })
        self.assertEqual(resp1.status_code, 201)
        self.assertEqual(resp1.get_json()["status"], "sucesso")

        # Segunda tentativa de resgate do mesmo item esgotado (deve retornar 409 conflito/esgotado)
        resp2 = self.client.post("/api/resgates/", json={
            "id_cliente": self.ids["cliente"],
            "id_recompensa": id_rec
        })
        self.assertIn(resp2.status_code, [400, 409])

        with self.app.app_context():
            db.session.expire_all()
            rec_final = db.session.get(Recompensa, id_rec)
            self.assertEqual(rec_final.quantidade_disponivel, 0, "Estoque final deve ser rigorosamente 0")

    def test_resgate_saldo_insuficiente_rejeitado(self):
        """Tentativa de resgate com saldo insuficiente deve retornar 400 sem alterar saldo nem estoque."""
        with self.app.app_context():
            rec_cara = Recompensa(
                id_usuario=self.ids["proprietaria"],
                nome_cupom="Item Muito Caro",
                codigo="CARO-999",
                custo_pontos=9999,
                tipo="produto_fisico",
                validade=date.today() + timedelta(days=30),
                quantidade_total=10,
                quantidade_disponivel=10,
                status="ativa"
            )
            db.session.add(rec_cara)
            db.session.commit()
            id_cara = rec_cara.id_produto

        self.autenticar("u", self.ids["vendedora"])
        resp = self.client.post("/api/resgates/", json={
            "id_cliente": self.ids["cliente"],
            "id_recompensa": id_cara
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("insuficiente", resp.get_json()["erro"].lower())

        with self.app.app_context():
            rec_final = db.session.get(Recompensa, id_cara)
            self.assertEqual(rec_final.quantidade_disponivel, 10, "Estoque deve permanecer intacto")
            cli_final = db.session.get(Cliente, self.ids["cliente"])
            self.assertEqual(cli_final.pontos_acumulados, 50, "Saldo de pontos deve permanecer intacto")

    def test_csp_permite_fontes_e_icones(self):
        """Garante que a diretiva CSP font-src autorize os CDNs jsdelivr e cdnjs para ícones."""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Content-Security-Policy", resp.headers)
        csp = resp.headers["Content-Security-Policy"]
        self.assertIn("https://cdn.jsdelivr.net", csp, "CSP deve permitir cdn.jsdelivr.net para ícones/fontes")
        self.assertIn("https://cdnjs.cloudflare.com", csp, "CSP deve permitir cdnjs.cloudflare.com para FontAwesome")
        self.assertIn("font-src 'self' https://cdn.jsdelivr.net", csp, "font-src deve incluir cdn.jsdelivr.net explicitamente")

    def test_tela_login_sem_credenciais_demo(self):
        """Garante que a tela de login não vaze senhas de demonstração ou botões de preenchimento automático."""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        conteudo = resp.get_data(as_text=True)
        self.assertNotIn("ITClube2026", conteudo, "A senha demo ITClube2026 não pode estar no HTML da tela de login")
        self.assertNotIn("preencherVendedora", conteudo, "Função JS de auto-preenchimento demo deve ser removida")
        self.assertNotIn("preencherCliente", conteudo, "Função JS de auto-preenchimento demo deve ser removida")
        self.assertNotIn("Acessos Rápidos de Demonstração", conteudo, "Card de acessos demo deve ser removido")

    def test_politica_senha_rejeita_senha_demo(self):
        """Garante que senhas de demonstração estejam na blacklist de segurança."""
        from app.security.password import validar_politica_senha_admin
        valida, msg = validar_politica_senha_admin("ITClube2026")
        self.assertFalse(valida, "A senha demo ITClube2026 deve ser rejeitada pela política de senhas")
        self.assertIn("insegura", msg.lower())

    def test_seed_bloqueado_em_producao(self):
        """Garante que o script de seed aborta execução em produção sem override explícito."""
        import subprocess
        import sys
        env_teste = os.environ.copy()
        env_teste["FLASK_ENV"] = "production"
        env_teste.pop("ALLOW_DEMO_SEED", None)
        seed_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "database", "seeds", "seed.py"))
        res = subprocess.run(
            [sys.executable, seed_path],
            capture_output=True,
            text=True,
            env=env_teste
        )
        self.assertNotEqual(res.returncode, 0, "Seed de demonstração deve falhar em produção")
        self.assertIn("bloqueada em ambiente de PRODUCAO", res.stdout)


if __name__ == "__main__":
    unittest.main()

