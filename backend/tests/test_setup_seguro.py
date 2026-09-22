import os
import sys
import unittest
import threading
from unittest.mock import patch

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

    # 1. Banco vazio -> setup permitido
    def test_banco_vazio_setup_permitido(self):
        resp_auth = self.client.get("/auth/setup")
        self.assertEqual(resp_auth.status_code, 200)
        self.assertIn(b"Cadastro Inicial Seguro", resp_auth.data)

        # Rota de atalho /setup redireciona para /auth/setup
        resp_setup = self.client.get("/setup")
        self.assertEqual(resp_setup.status_code, 302)
        self.assertIn("/auth/setup", resp_setup.headers.get("Location", ""))

    # 2. Criar primeiro admin -> sucesso
    def test_criar_primeiro_admin_sucesso(self):
        payload = {
            "nome": "Camila Silva",
            "login": "camila_admin",
            "email": "camila@loja.com.br",
            "senha": "SenhaForte@2026",
            "confirmar_senha": "SenhaForte@2026",
        }
        resp = self.client.post("/auth/setup", json=payload)
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertIn("sucesso", data["mensagem"].lower())
        self.assertEqual(data["redirect"], "/dashboard")

        with self.app.app_context():
            u = Usuario.query.filter_by(login="camila_admin").first()
            self.assertIsNotNone(u)
            self.assertTrue(u.is_vendedora)
            self.assertEqual(u.nivel_acesso, "ADMIN")
            self.assertTrue(u.verificar_senha("SenhaForte@2026"))
            self.assertFalse(u.precisa_trocar_senha)

            # Auditoria registrada com detalhes sanitizados (sem senha)
            audit = Auditoria.query.filter_by(acao="CADASTRO_INICIAL_VENDEDORA_ADMIN").first()
            self.assertIsNotNone(audit)
            self.assertNotIn("SenhaForte@2026", str(audit.detalhes))

    # 3. Depois da criação -> setup bloqueado (GET e POST)
    def test_depois_da_criacao_setup_bloqueado(self):
        # Cria admin inicial
        payload = {
            "nome": "Primeira Vendedora",
            "login": "primeira_vendedora",
            "email": "v1@loja.com",
            "senha": "SenhaForte@2026",
            "confirmar_senha": "SenhaForte@2026",
        }
        r = self.client.post("/auth/setup", json=payload)
        self.assertEqual(r.status_code, 201)

        # GET /auth/setup deve redirecionar para login
        resp_get = self.client.get("/auth/setup")
        self.assertEqual(resp_get.status_code, 302)

        # POST /auth/setup subsequente deve retornar 403 Forbidden
        payload_subsequente = {
            "nome": "Segunda Vendedora",
            "login": "segunda_vendedora",
            "email": "v2@loja.com",
            "senha": "SenhaForte@2026",
            "confirmar_senha": "SenhaForte@2026",
        }
        resp_post = self.client.post("/auth/setup", json=payload_subsequente)
        self.assertEqual(resp_post.status_code, 403)
        self.assertIn("concluído", resp_post.get_json()["erro"].lower())

    # 4. Tentativa de segundo admin pelo setup -> bloqueada
    def test_tentativa_segundo_admin_bloqueada(self):
        with self.app.app_context():
            u = Usuario(
                nome="Admin Existente",
                login="admin_loja",
                email="admin@loja.com",
                cargo=ROLE_VENDEDORA,
                nivel_acesso="ADMIN",
                ativo=True,
            )
            u.set_senha("AdminSenhaForte@2026")
            db.session.add(u)
            db.session.commit()

        resp = self.client.post("/auth/setup", json={
            "nome": "Invasor Admin",
            "login": "invasor",
            "email": "invasor@loja.com",
            "senha": "InvasorSenha@2026",
            "confirmar_senha": "InvasorSenha@2026",
        })
        self.assertEqual(resp.status_code, 403)
        with self.app.app_context():
            self.assertEqual(Usuario.query.count(), 1)

    # 5. Senha inválida -> rejeitada
    def test_senha_invalida_rejeitada(self):
        senhas_invalidas = [
            "1234",                     # Curta e comum
            "senhafraca",               # Sem maiúscula, número ou especial
            "SenhaSemNumeroNemEspecial",
            "Senha123456",              # Sem caractere especial
            "fideliza2026",             # Blacklist
        ]
        for s in senhas_invalidas:
            resp = self.client.post("/auth/setup", json={
                "nome": "Vendedora Valida",
                "login": "vendedora_valida",
                "email": "valida@loja.com",
                "senha": s,
                "confirmar_senha": s,
            })
            self.assertEqual(resp.status_code, 400, f"A senha '{s}' deveria ter sido rejeitada com 400.")
            with self.app.app_context():
                self.assertEqual(Usuario.query.count(), 0)

    # 6. Senhas diferentes -> rejeitadas
    def test_senhas_diferentes_rejeitadas(self):
        resp = self.client.post("/auth/setup", json={
            "nome": "Vendedora Chefe",
            "login": "vendedora_chefe",
            "email": "chefe@loja.com",
            "senha": "SenhaForte@2026",
            "confirmar_senha": "OutraSenhaDiferente@2026",
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("não confere", resp.get_json()["erro"].lower())

    # 7. E-mail inválido -> rejeitado
    def test_email_invalido_rejeitado(self):
        emails_invalidos = ["emailsemarroba", "usuario@", "@dominio.com", "nome@dominio sem espaco"]
        for e in emails_invalidos:
            resp = self.client.post("/auth/setup", json={
                "nome": "Vendedora Chefe",
                "login": "chefe_teste",
                "email": e,
                "senha": "SenhaForte@2026",
                "confirmar_senha": "SenhaForte@2026",
            })
            self.assertEqual(resp.status_code, 400, f"O e-mail '{e}' deveria ser rejeitado.")

    # 8. Nome inválido -> rejeitado (< 3 ou > 100 caracteres)
    def test_nome_invalido_rejeitado(self):
        # Muito curto
        resp_curto = self.client.post("/auth/setup", json={
            "nome": "A",
            "login": "vendedora_curta",
            "email": "curta@loja.com",
            "senha": "SenhaForte@2026",
            "confirmar_senha": "SenhaForte@2026",
        })
        self.assertEqual(resp_curto.status_code, 400)

        # Muito longo
        resp_longo = self.client.post("/auth/setup", json={
            "nome": "A" * 105,
            "login": "vendedora_longa",
            "email": "longa@loja.com",
            "senha": "SenhaForte@2026",
            "confirmar_senha": "SenhaForte@2026",
        })
        self.assertEqual(resp_longo.status_code, 400)

    # 9. Login ou E-mail duplicado -> rejeitado
    def test_login_ou_email_duplicado_rejeitado(self):
        with self.app.app_context():
            u = Usuario(
                nome="Admin Previo",
                login="login_existente",
                email="existente@loja.com",
                cargo="cliente",
                nivel_acesso="CLIENTE",
            )
            u.set_senha("ClienteForte@2026")
            db.session.add(u)
            db.session.commit()

        # Login duplicado
        resp_login_dup = self.client.post("/auth/setup", json={
            "nome": "Nova Vendedora",
            "login": "login_existente",
            "email": "outro@loja.com",
            "senha": "SenhaForte@2026",
            "confirmar_senha": "SenhaForte@2026",
        })
        self.assertEqual(resp_login_dup.status_code, 409)

        # Email duplicado
        resp_email_dup = self.client.post("/auth/setup", json={
            "nome": "Nova Vendedora",
            "login": "login_novo",
            "email": "existente@loja.com",
            "senha": "SenhaForte@2026",
            "confirmar_senha": "SenhaForte@2026",
        })
        self.assertEqual(resp_email_dup.status_code, 409)

    # 10. CSRF inválido -> rejeitado
    def test_csrf_invalido_rejeitado(self):
        app_csrf = create_app("testing")
        app_csrf.config["WTF_CSRF_ENABLED"] = True
        client_csrf = app_csrf.test_client()

        with app_csrf.app_context():
            db.create_all()

        # Requisição POST sem CSRF token deve retornar 400
        resp = client_csrf.post("/auth/setup", data={
            "nome": "Tentativa Sem CSRF",
            "login": "admin_sem_csrf",
            "email": "sem_csrf@loja.com",
            "senha": "SenhaForte@2026",
            "confirmar_senha": "SenhaForte@2026",
        })
        self.assertEqual(resp.status_code, 400)

    # 11. Persistência: restart lógico da aplicação mantém setup bloqueado
    def test_restart_logico_persistencia(self):
        # Cria admin inicial
        payload = {
            "nome": "Vendedora Persistente",
            "login": "vendedora_persist",
            "email": "persist@loja.com",
            "senha": "SenhaForte@2026",
            "confirmar_senha": "SenhaForte@2026",
        }
        self.client.post("/auth/setup", json=payload)

        # Cria novo test_client simulando reinicialização / novo worker
        novo_client = self.app.test_client()
        resp_get = novo_client.get("/auth/setup")
        self.assertEqual(resp_get.status_code, 302)

        resp_post = novo_client.post("/auth/setup", json=payload)
        self.assertEqual(resp_post.status_code, 403)

    # 12. INITIAL_SETUP_TOKEN quando configurado
    def test_setup_com_initial_setup_token(self):
        token_secreto = "token-render-bootstrap-secreto-987"
        with patch.dict(os.environ, {"INITIAL_SETUP_TOKEN": token_secreto}):
            # Tentativa sem token -> 403
            resp_sem_token = self.client.post("/auth/setup", json={
                "nome": "Vendedora Com Token",
                "login": "vendedora_tok",
                "email": "tok@loja.com",
                "senha": "SenhaForte@2026",
                "confirmar_senha": "SenhaForte@2026",
            })
            self.assertEqual(resp_sem_token.status_code, 403)
            self.assertIn("token", resp_sem_token.get_json()["erro"].lower())

            # Tentativa com token incorreto -> 403
            resp_token_errado = self.client.post("/auth/setup", json={
                "nome": "Vendedora Com Token",
                "login": "vendedora_tok",
                "email": "tok@loja.com",
                "senha": "SenhaForte@2026",
                "confirmar_senha": "SenhaForte@2026",
                "setup_token": "token-falso",
            })
            self.assertEqual(resp_token_errado.status_code, 403)

            # Tentativa com token correto -> 201 Sucesso
            resp_token_correto = self.client.post("/auth/setup", json={
                "nome": "Vendedora Com Token",
                "login": "vendedora_tok",
                "email": "tok@loja.com",
                "senha": "SenhaForte@2026",
                "confirmar_senha": "SenhaForte@2026",
                "setup_token": token_secreto,
            })
            self.assertEqual(resp_token_correto.status_code, 201)

            # Depois de criado, mesmo enviando o token correto, é bloqueado!
            resp_bloqueado = self.client.post("/auth/setup", json={
                "nome": "Outra Vendedora",
                "login": "outra_tok",
                "email": "outra@loja.com",
                "senha": "SenhaForte@2026",
                "confirmar_senha": "SenhaForte@2026",
                "setup_token": token_secreto,
            })
            self.assertEqual(resp_bloqueado.status_code, 403)

    # 13. Race condition: múltiplos requests simultâneos criam apenas 1 admin
    def test_race_condition_concorrencia_primeiro_admin(self):
        import tempfile
        from sqlalchemy.pool import NullPool

        temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        temp_db_path = temp_file.name
        temp_file.close()

        app_conc = create_app("testing")
        app_conc.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{temp_db_path}"
        app_conc.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "poolclass": NullPool,
            "connect_args": {"timeout": 20, "check_same_thread": False},
        }

        with app_conc.app_context():
            db.create_all()

        resultados = []

        def submeter_setup(indice):
            client = app_conc.test_client()
            resp = client.post("/auth/setup", json={
                "nome": f"Vendedora Concorrente {indice}",
                "login": f"vendedora_conc_{indice}",
                "email": f"conc_{indice}@loja.com",
                "senha": f"SenhaForte@{indice}2026",
                "confirmar_senha": f"SenhaForte@{indice}2026",
            })
            resultados.append(resp.status_code)

        t1 = threading.Thread(target=submeter_setup, args=(1,))
        t2 = threading.Thread(target=submeter_setup, args=(2,))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        with app_conc.app_context():
            admins = Usuario.query.filter(Usuario.nivel_acesso == "ADMIN").all()
            self.assertEqual(len(admins), 1, "Deve existir rigorosamente 1 administrador inicial.")
            db.session.remove()
            db.drop_all()

        if os.path.exists(temp_db_path):
            try:
                os.remove(temp_db_path)
            except OSError:
                pass

        self.assertIn(201, resultados, "Pelo menos uma requisição deve ter sucesso.")

    # 14. Fail-closed de SECRET_KEY em Produção
    def test_secret_key_fail_closed_em_producao(self):
        for chave in ["", "dev-secret-key", "troque-por-uma-chave-longa-e-aleatoria"]:
            with patch.dict(os.environ, {"SECRET_KEY": chave}):
                with self.assertRaises(ValueError):
                    create_app("production")

    # 15. Exclusão/desativação do último admin NÃO deve reabrir /auth/setup silenciosamente
    def test_desativacao_ultimo_admin_bloqueada(self):
        """O sistema deve impedir a desativação da última vendedora ativa,
        evitando que sistema_precisa_setup() retorne True em sistema já inicializado."""
        # Cria admin inicial via setup
        payload = {
            "nome": "Admin Unica",
            "login": "admin_unica",
            "email": "unica@loja.com",
            "senha": "SenhaForte@2026",
            "confirmar_senha": "SenhaForte@2026",
        }
        r = self.client.post("/auth/setup", json=payload)
        self.assertEqual(r.status_code, 201)

        with self.app.app_context():
            admin = Usuario.query.filter_by(login="admin_unica").first()
            admin_id = admin.id_usuario

        # Tenta desativar a única admin via API de funcionários
        resp = self.client.post(
            f"/api/funcionarios/{admin_id}/status",
            json={"ativo": False},
        )
        # Deve ser bloqueado (400) ou proibido (403) — não pode desativar a última
        self.assertIn(resp.status_code, [400, 403])

        # Verifica que /auth/setup continua BLOQUEADO (não reabriu)
        resp_setup = self.client.get("/auth/setup")
        self.assertEqual(resp_setup.status_code, 302)

        resp_post = self.client.post("/auth/setup", json=payload)
        self.assertEqual(resp_post.status_code, 403)

    # 16. Rebaixamento de cargo do último admin deve ser bloqueado
    def test_rebaixamento_ultimo_admin_bloqueado(self):
        """O sistema deve impedir rebaixar o cargo do último administrador
        para 'cliente', o que tornaria sistema_precisa_setup() True."""
        payload = {
            "nome": "Admin Para Rebaixar",
            "login": "admin_rebaixar",
            "email": "rebaixar@loja.com",
            "senha": "SenhaForte@2026",
            "confirmar_senha": "SenhaForte@2026",
        }
        r = self.client.post("/auth/setup", json=payload)
        self.assertEqual(r.status_code, 201)

        with self.app.app_context():
            admin = Usuario.query.filter_by(login="admin_rebaixar").first()
            admin_id = admin.id_usuario

        # Tenta rebaixar via API de edição de funcionários
        resp = self.client.put(
            f"/api/funcionarios/{admin_id}",
            json={"cargo": "cliente"},
        )
        # Deve ser bloqueado — resposta 400 (último admin) ou 403 (permissão)
        self.assertIn(resp.status_code, [400, 403])

        # Setup deve continuar fechado
        resp_setup = self.client.get("/auth/setup")
        self.assertEqual(resp_setup.status_code, 302)

    # 17. Token ausente/incorreto via POST body deve bloquear; token correto via POST body deve permitir
    def test_token_somente_via_post_body(self):
        """O token de setup deve ser aceito SOMENTE via POST body, nunca via query string."""
        token_secreto = "meu-token-seguro-via-body-789"
        with patch.dict(os.environ, {"INITIAL_SETUP_TOKEN": token_secreto}):
            # Token via query string NÃO deve funcionar
            resp_query = self.client.post(
                f"/auth/setup?token={token_secreto}",
                json={
                    "nome": "Vendedora Token QS",
                    "login": "vendedora_qs",
                    "email": "qs@loja.com",
                    "senha": "SenhaForte@2026",
                    "confirmar_senha": "SenhaForte@2026",
                },
            )
            self.assertEqual(resp_query.status_code, 403, "Token via query string não deve ser aceito")

            # Token via POST body deve funcionar
            resp_body = self.client.post(
                "/auth/setup",
                json={
                    "nome": "Vendedora Token Body",
                    "login": "vendedora_body",
                    "email": "body@loja.com",
                    "senha": "SenhaForte@2026",
                    "confirmar_senha": "SenhaForte@2026",
                    "setup_token": token_secreto,
                },
            )
            self.assertEqual(resp_body.status_code, 201, "Token via POST body deve ser aceito")


if __name__ == "__main__":
    unittest.main()
