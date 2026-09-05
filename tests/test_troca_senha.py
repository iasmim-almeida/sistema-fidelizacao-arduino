"""
Testes automatizados para a funcionalidade de alteração de senha de administradores.
Cobre validação da senha atual, política de complexidade, confirmação,
prevenção contra reutilização, controle de acesso (RBAC), CSRF e fluxo de login pós-troca.
"""
import re
import unittest
from app import create_app
from app.extensions import db as _db, limiter
from app.models.usuario import Usuario
from app.models.cliente import Cliente


class TrocaSenhaAdminTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app("testing")
        limiter.enabled = False
        self.client = self.app.test_client()
        with self.app.app_context():
            _db.create_all()
            self.admin = Usuario(
                nome="Admin Teste",
                login="admin_test",
                email="admin@teste.com",
                nivel_acesso="gestor"
            )
            self.admin.set_senha("SenhaAtual@123")

            self.cliente = Cliente(
                nome="Cliente Teste",
                telefone="11999998888",
                pontos_acumulados=50
            )
            self.cliente.set_senha("ClienteSenha@123")

            _db.session.add_all([self.admin, self.cliente])
            _db.session.commit()
            self.admin_id = self.admin.id_usuario
            self.cliente_id = self.cliente.id_cliente

    def tearDown(self):
        with self.app.app_context():
            _db.session.remove()
            _db.drop_all()

    def autenticar_admin(self):
        with self.client.session_transaction() as sess:
            sess["_user_id"] = f"u_{self.admin_id}"
            sess["_fresh"] = True

    def autenticar_cliente(self):
        with self.client.session_transaction() as sess:
            sess["_user_id"] = f"c_{self.cliente_id}"
            sess["_fresh"] = True

    # ───────────────────── Casos Positivos ─────────────────────

    def test_alterar_senha_sucesso(self):
        """Administrador autenticado altera sua senha com sucesso."""
        self.autenticar_admin()
        resp = self.client.post("/auth/alterar-senha", json={
            "senha_atual": "SenhaAtual@123",
            "nova_senha": "NovaSenhaForte@2026",
            "confirmar_nova_senha": "NovaSenhaForte@2026"
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "sucesso")

        with self.app.app_context():
            admin_db = _db.session.get(Usuario, self.admin_id)
            self.assertFalse(admin_db.verificar_senha("SenhaAtual@123"))
            self.assertTrue(admin_db.verificar_senha("NovaSenhaForte@2026"))

    def test_login_com_nova_senha_apos_troca(self):
        """Após troca com sucesso, o login funciona com a nova senha e falha com a antiga."""
        self.autenticar_admin()
        self.client.post("/auth/alterar-senha", json={
            "senha_atual": "SenhaAtual@123",
            "nova_senha": "NovaSenhaForte@2026",
            "confirmar_nova_senha": "NovaSenhaForte@2026"
        })

        # Teste de login com senha antiga deve falhar
        resp_antiga = self.client.post("/auth/login", json={
            "login": "admin_test",
            "senha": "SenhaAtual@123"
        })
        self.assertEqual(resp_antiga.status_code, 401)

        # Teste de login com nova senha deve passar
        resp_nova = self.client.post("/auth/login", json={
            "login": "admin_test",
            "senha": "NovaSenhaForte@2026"
        })
        self.assertEqual(resp_nova.status_code, 200)
        self.assertEqual(resp_nova.get_json()["tipo"], "vendedora")

    # ───────────────────── Validação da Senha Atual ─────────────────────

    def test_senha_atual_incorreta(self):
        """Rejeita alteração se a senha atual estiver incorreta."""
        self.autenticar_admin()
        resp = self.client.post("/auth/alterar-senha", json={
            "senha_atual": "SenhaErrada@999",
            "nova_senha": "NovaSenhaForte@2026",
            "confirmar_nova_senha": "NovaSenhaForte@2026"
        })
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("incorreta", data["erro"].lower())

    def test_reutilizacao_mesma_senha(self):
        """Rejeita tentativa de definir nova senha idêntica à senha atual."""
        self.autenticar_admin()
        resp = self.client.post("/auth/alterar-senha", json={
            "senha_atual": "SenhaAtual@123",
            "nova_senha": "SenhaAtual@123",
            "confirmar_nova_senha": "SenhaAtual@123"
        })
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("diferente", data["erro"].lower())

    # ───────────────────── Validação de Confirmação ─────────────────────

    def test_confirmacao_diferente(self):
        """Rejeita alteração se nova senha e confirmação não forem idênticas."""
        self.autenticar_admin()
        resp = self.client.post("/auth/alterar-senha", json={
            "senha_atual": "SenhaAtual@123",
            "nova_senha": "NovaSenhaForte@2026",
            "confirmar_nova_senha": "OutraSenhaForte@2026"
        })
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("confere", data["erro"].lower())

    # ───────────────────── Política de Complexidade ─────────────────────

    def test_nova_senha_curta(self):
        """Rejeita nova senha com menos de 8 caracteres."""
        self.autenticar_admin()
        resp = self.client.post("/auth/alterar-senha", json={
            "senha_atual": "SenhaAtual@123",
            "nova_senha": "Ab1!",
            "confirmar_nova_senha": "Ab1!"
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("8 caracteres", resp.get_json()["erro"].lower())

    def test_nova_senha_sem_maiuscula(self):
        """Rejeita nova senha sem letra maiúscula."""
        self.autenticar_admin()
        resp = self.client.post("/auth/alterar-senha", json={
            "senha_atual": "SenhaAtual@123",
            "nova_senha": "senhanovaforte@123",
            "confirmar_nova_senha": "senhanovaforte@123"
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("maiuscula", resp.get_json()["erro"].lower())

    def test_nova_senha_sem_minuscula(self):
        """Rejeita nova senha sem letra minúscula."""
        self.autenticar_admin()
        resp = self.client.post("/auth/alterar-senha", json={
            "senha_atual": "SenhaAtual@123",
            "nova_senha": "SENHANOVA@12345",
            "confirmar_nova_senha": "SENHANOVA@12345"
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("minuscula", resp.get_json()["erro"].lower())

    def test_nova_senha_sem_numero(self):
        """Rejeita nova senha sem dígito numérico."""
        self.autenticar_admin()
        resp = self.client.post("/auth/alterar-senha", json={
            "senha_atual": "SenhaAtual@123",
            "nova_senha": "SenhaSemNumero!@",
            "confirmar_nova_senha": "SenhaSemNumero!@"
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("numero", resp.get_json()["erro"].lower())

    def test_nova_senha_sem_caractere_especial(self):
        """Rejeita nova senha sem caractere especial."""
        self.autenticar_admin()
        resp = self.client.post("/auth/alterar-senha", json={
            "senha_atual": "SenhaAtual@123",
            "nova_senha": "SenhaSemEspecial123",
            "confirmar_nova_senha": "SenhaSemEspecial123"
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("especial", resp.get_json()["erro"].lower())

    def test_nova_senha_comum_bloqueada(self):
        """Rejeita nova senha se constar em blacklist de senhas comuns."""
        self.autenticar_admin()
        resp = self.client.post("/auth/alterar-senha", json={
            "senha_atual": "SenhaAtual@123",
            "nova_senha": "fideliza2026",
            "confirmar_nova_senha": "fideliza2026"
        })
        self.assertEqual(resp.status_code, 400)
        self.assertTrue("comum" in resp.get_json()["erro"].lower() or "insegura" in resp.get_json()["erro"].lower())

    def test_campos_obrigatorios_ausentes(self):
        """Rejeita requisição com campos vazios."""
        self.autenticar_admin()
        resp = self.client.post("/auth/alterar-senha", json={
            "senha_atual": "",
            "nova_senha": "",
            "confirmar_nova_senha": ""
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("obrigatorios", resp.get_json()["erro"].lower())

    # ───────────────────── Controle de Acesso e RBAC ─────────────────────

    def test_alterar_senha_anonimo_rejeitado(self):
        """Requisição não autenticada recebe 401."""
        resp = self.client.post("/auth/alterar-senha", json={
            "senha_atual": "Qualquer123",
            "nova_senha": "NovaForte@2026",
            "confirmar_nova_senha": "NovaForte@2026"
        })
        self.assertEqual(resp.status_code, 401)

    def test_alterar_senha_cliente_rejeitado(self):
        """Cliente comum recebe 403 ao tentar usar o endpoint administrativo."""
        self.autenticar_cliente()
        resp = self.client.post("/auth/alterar-senha", json={
            "senha_atual": "ClienteSenha@123",
            "nova_senha": "NovaForte@2026",
            "confirmar_nova_senha": "NovaForte@2026"
        })
        self.assertEqual(resp.status_code, 403)

    # ───────────────────── Renderização da Página Web ─────────────────────

    def test_pagina_alterar_senha_admin_renderiza_200(self):
        """Administrador autenticado acessa a página web /alterar-senha."""
        self.autenticar_admin()
        resp = self.client.get("/alterar-senha")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8")
        self.assertIn("Alterar Senha", body)
        self.assertIn("formAlterarSenha", body)

    def test_pagina_alterar_senha_cliente_redireciona(self):
        """Cliente autenticado é redirecionado ao tentar acessar /alterar-senha."""
        self.autenticar_cliente()
        resp = self.client.get("/alterar-senha")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/bemvindo", resp.headers.get("Location", ""))

    def test_pagina_alterar_senha_anonimo_redireciona(self):
        """Usuário anônimo é redirecionado ao tentar acessar /alterar-senha."""
        resp = self.client.get("/alterar-senha")
        self.assertEqual(resp.status_code, 302)

    def test_alterar_senha_exige_csrf_ativo(self):
        """Com CSRF ativo, mutações na rota exigem o header X-CSRFToken."""
        app_csrf = create_app("testing")
        app_csrf.config["WTF_CSRF_ENABLED"] = True
        with app_csrf.app_context():
            _db.create_all()
            admin_dev = Usuario(
                nome="Admin Dev CSRF",
                login="admin_dev_csrf",
                email="admin_dev_csrf@teste.com",
                nivel_acesso="gestor"
            )
            admin_dev.set_senha("SenhaDev@123")
            _db.session.add(admin_dev)
            _db.session.commit()
            dev_admin_id = admin_dev.id_usuario

            c = app_csrf.test_client()
            with c.session_transaction() as sess:
                sess["_user_id"] = f"u_{dev_admin_id}"
                sess["_fresh"] = True

            # 1. Tentativa sem token CSRF -> bloqueado com 400
            resp_sem_csrf = c.post("/auth/alterar-senha", json={
                "senha_atual": "SenhaDev@123",
                "nova_senha": "NovaSenhaSegura@2026",
                "confirmar_nova_senha": "NovaSenhaSegura@2026"
            })
            self.assertEqual(resp_sem_csrf.status_code, 400)

            # 2. Obter token CSRF válido da página
            resp_page = c.get("/alterar-senha")
            self.assertEqual(resp_page.status_code, 200)
            match = re.search(r'name="csrf-token"\s+content="([^"]+)"', resp_page.data.decode("utf-8"))
            self.assertIsNotNone(match, "Meta tag csrf-token não encontrada na página")
            token = match.group(1)

            # 3. Enviar com token CSRF válido -> 200 OK
            resp_com_csrf = c.post(
                "/auth/alterar-senha",
                json={
                    "senha_atual": "SenhaDev@123",
                    "nova_senha": "NovaSenhaSegura@2026",
                    "confirmar_nova_senha": "NovaSenhaSegura@2026"
                },
                headers={"X-CSRFToken": token}
            )
            self.assertEqual(resp_com_csrf.status_code, 200)
            self.assertEqual(resp_com_csrf.get_json()["status"], "sucesso")


if __name__ == "__main__":
    unittest.main()
