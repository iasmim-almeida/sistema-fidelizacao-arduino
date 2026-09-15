import os
import sys
import unittest
from datetime import datetime, timezone

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app import create_app
from app.extensions import db, limiter
from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.models.compra import Compra
from app.models.recompensa import Recompensa
from app.models.resgate import Resgate
from app.models.auditoria import Auditoria
from app.services.rbac import ROLE_PROPRIETARIO, ROLE_VENDEDOR


class ITClubeRegrasTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app("testing")
        limiter.enabled = False
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

            self.vendedora = Usuario(
                nome="Vendedora Loja",
                login="vend_it",
                cargo=ROLE_VENDEDOR,
                nivel_acesso="vendedor",
                ativo=True,
            )
            self.vendedora.set_senha("Vend12345!")

            self.gestora = Usuario(
                nome="Gestora Loja",
                login="gestora_it",
                cargo=ROLE_PROPRIETARIO,
                nivel_acesso="gestor",
                ativo=True,
            )
            self.gestora.set_senha("Gestora12345!")

            self.cliente = Cliente(
                nome="Cliente IT Clube",
                telefone="11988887777",
                email="cliente.it@teste.com",
                pontos_acumulados=0,
                ativo=True,
            )
            self.cliente.set_senha("Cliente12345!")

            self.cliente_dois = Cliente(
                nome="Cliente Dois",
                telefone="11977776666",
                email="cliente.dois@teste.com",
                pontos_acumulados=50,
                ativo=True,
            )
            self.cliente_dois.set_senha("Cliente12345!")

            db.session.add_all([
                self.vendedora,
                self.gestora,
                self.cliente,
                self.cliente_dois,
            ])
            db.session.flush()

            self.recompensa = Recompensa(
                id_usuario=self.gestora.id_usuario,
                nome="Brinde IT Clube",
                custo_pontos=5,
                quantidade_total=10,
                quantidade_disponivel=10,
                tipo="produto_fisico",
                validade=datetime.now(timezone.utc).date(),
                status="ativa",
            )
            db.session.add(self.recompensa)
            db.session.commit()

            self.vendedora_id = self.vendedora.id_usuario
            self.gestora_id = self.gestora.id_usuario
            self.cliente_id = self.cliente.id_cliente
            self.cliente_dois_id = self.cliente_dois.id_cliente
            self.recompensa_id = self.recompensa.id_recompensa

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def autenticar(self, prefixo, user_id):
        with self.client.session_transaction() as sess:
            sess["_user_id"] = f"{prefixo}_{user_id}"
            sess["_fresh"] = True

    def test_uma_compra_gera_um_ponto(self):
        """Regra do IT Clube: 1 compra = 1 ponto."""
        self.autenticar("u", self.vendedora_id)
        resp = self.client.post("/api/compras/", json={
            "telefone": "11988887777",
            "valor": 150.00
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertEqual(data["pontos_adicionados"], 1)
        self.assertEqual(data["saldo_atualizado"], 1)

        with self.app.app_context():
            cli = db.session.get(Cliente, self.cliente_id)
            self.assertEqual(cli.pontos_acumulados, 1)

    def test_dez_compras_geram_dez_pontos(self):
        """10 compras consecutivas devem acumular exatamente 10 pontos."""
        self.autenticar("u", self.vendedora_id)
        for i in range(10):
            resp = self.client.post("/api/compras/", json={
                "telefone": "11988887777",
                "valor": 10.00 * (i + 1)
            })
            self.assertEqual(resp.status_code, 201)
            self.assertEqual(resp.get_json()["saldo_atualizado"], i + 1)

        with self.app.app_context():
            cli = db.session.get(Cliente, self.cliente_id)
            self.assertEqual(cli.pontos_acumulados, 10)

    def test_valores_monetarios_diferentes_geram_sempre_um_ponto(self):
        """Compras de R$ 10, R$ 100 e R$ 1000 geram cada uma exatamente 1 ponto."""
        self.autenticar("u", self.vendedora_id)
        valores = [10.00, 100.00, 1000.00]
        saldo_esperado = 0
        for val in valores:
            resp = self.client.post("/api/compras/", json={
                "telefone": "11988887777",
                "valor": val
            })
            self.assertEqual(resp.status_code, 201)
            saldo_esperado += 1
            self.assertEqual(resp.get_json()["pontos_adicionados"], 1)
            self.assertEqual(resp.get_json()["saldo_atualizado"], saldo_esperado)

        with self.app.app_context():
            cli = db.session.get(Cliente, self.cliente_id)
            self.assertEqual(cli.pontos_acumulados, 3)

    def test_cliente_nao_altera_proprios_pontos(self):
        """Cliente não pode alterar seus pontos via self-service nem endpoints administrativos."""
        self.autenticar("c", self.cliente_id)

        # Tentativa 1: Injeção de pontos no endpoint /api/clientes/me
        resp = self.client.put("/api/clientes/me", json={
            "nome": "Cliente Injetor",
            "pontos_acumulados": 99999,
            "pontos": 99999,
            "saldo": 99999
        })
        self.assertEqual(resp.status_code, 200)

        with self.app.app_context():
            cli = db.session.get(Cliente, self.cliente_id)
            self.assertEqual(cli.pontos_acumulados, 0)
            self.assertEqual(cli.nome, "Cliente Injetor")

        # Tentativa 2: Acesso ao endpoint restrito de ajuste de pontos
        resp2 = self.client.post(f"/api/clientes/{self.cliente_id}/pontos/ajuste", json={
            "operacao": "adicionar",
            "quantidade": 100,
            "motivo": "Fraude"
        })
        self.assertEqual(resp2.status_code, 403)

    def test_cliente_auto_resgate_bloqueado(self):
        """O cliente não pode se auto-resgatar (POST /api/resgates/ deve retornar 403 para clientes)."""
        with self.app.app_context():
            cli = db.session.get(Cliente, self.cliente_id)
            cli.pontos_acumulados = 20
            db.session.commit()

        self.autenticar("c", self.cliente_id)
        resp = self.client.post("/api/resgates/", json={
            "id_recompensa": self.recompensa_id
        })
        self.assertEqual(resp.status_code, 403)

        # Confirmar que a gestora/vendedora pode validar o resgate no PDV
        self.autenticar("u", self.gestora_id)
        resp_gestora = self.client.post("/api/resgates/", json={
            "id_cliente": self.cliente_id,
            "id_recompensa": self.recompensa_id
        })
        self.assertEqual(resp_gestora.status_code, 201)

        with self.app.app_context():
            cli = db.session.get(Cliente, self.cliente_id)
            self.assertEqual(cli.pontos_acumulados, 15)

    def test_cliente_atualizacao_perfil_proprio(self):
        """Cliente pode atualizar seu próprio nome, telefone e email."""
        self.autenticar("c", self.cliente_id)
        resp = self.client.put("/api/clientes/me", json={
            "nome": "Cliente Nome Atualizado",
            "telefone": "11911112222",
            "email": "novo.email@teste.com"
        })
        self.assertEqual(resp.status_code, 200)

        with self.app.app_context():
            cli = db.session.get(Cliente, self.cliente_id)
            self.assertEqual(cli.nome, "Cliente Nome Atualizado")
            self.assertEqual(cli.telefone, "11911112222")
            self.assertEqual(cli.email, "novo.email@teste.com")

    def test_cliente_atualizacao_perfil_rejeita_duplicatas(self):
        """Atualização de perfil rejeita telefone ou email já em uso por outro cliente."""
        self.autenticar("c", self.cliente_id)

        # Telefone já em uso pelo cliente_dois
        resp_tel = self.client.put("/api/clientes/me", json={
            "telefone": "11977776666"
        })
        self.assertIn(resp_tel.status_code, [400, 409])

        # Email já em uso pelo cliente_dois
        resp_email = self.client.put("/api/clientes/me", json={
            "email": "cliente.dois@teste.com"
        })
        self.assertIn(resp_email.status_code, [400, 409])

    def test_cliente_alteracao_senha_segura(self):
        """Cliente altera senha fornecendo a senha atual e uma nova senha válida."""
        self.autenticar("c", self.cliente_id)

        # Erro: Senha atual errada
        resp_err = self.client.post("/api/clientes/me/alterar-senha", json={
            "senha_atual": "SenhaErrada123!",
            "nova_senha": "NovaSenhaSegura2026!",
            "confirmar_senha": "NovaSenhaSegura2026!"
        })
        self.assertEqual(resp_err.status_code, 400)

        # Sucesso: Senha atual correta
        resp_ok = self.client.post("/api/clientes/me/alterar-senha", json={
            "senha_atual": "Cliente12345!",
            "nova_senha": "NovaSenhaSegura2026!",
            "confirmar_senha": "NovaSenhaSegura2026!"
        })
        self.assertEqual(resp_ok.status_code, 200)

        with self.app.app_context():
            cli = db.session.get(Cliente, self.cliente_id)
            self.assertTrue(cli.check_senha("NovaSenhaSegura2026!"))
            self.assertFalse(cli.check_senha("Cliente12345!"))

    def test_auditoria_sem_vazamento_de_senha(self):
        """Garante que a auditoria registra eventos sem expor senhas em texto plano."""
        self.autenticar("c", self.cliente_id)
        self.client.post("/api/clientes/me/alterar-senha", json={
            "senha_atual": "Cliente12345!",
            "nova_senha": "NovaSenhaSegura2026!",
            "confirmar_senha": "NovaSenhaSegura2026!"
        })

        with self.app.app_context():
            logs = Auditoria.query.filter_by(acao="ALTERAR_SENHA_CLIENTE").all()
            self.assertGreaterEqual(len(logs), 1)
            for log in logs:
                detalhes_str = str(log.detalhes) if log.detalhes else ""
                self.assertNotIn("NovaSenhaSegura2026!", detalhes_str)
                self.assertNotIn("Cliente12345!", detalhes_str)


if __name__ == "__main__":
    unittest.main()
