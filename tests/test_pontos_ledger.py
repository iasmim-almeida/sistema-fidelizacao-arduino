import unittest
from decimal import Decimal
from app import create_app
from app.extensions import db, limiter
from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.models.movimentacao_pontos import MovimentacaoPontos
from app.services.rbac import ROLE_PROPRIETARIO, ROLE_GERENTE, ROLE_VENDEDOR


class PontosLedgerTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app("testing")
        limiter.enabled = False
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()

            self.admin = Usuario(
                nome="Admin Teste",
                login="admin_pts",
                cargo=ROLE_PROPRIETARIO,
                nivel_acesso="gestor",
                ativo=True,
            )
            self.admin.set_senha("AdminTeste123!")

            self.gerente = Usuario(
                nome="Gerente Teste",
                login="ger_pts",
                cargo=ROLE_GERENTE,
                nivel_acesso="gerente",
                ativo=True,
            )
            self.gerente.set_senha("GerTeste123!")

            self.vendedor = Usuario(
                nome="Vendedor Teste",
                login="vend_pts",
                cargo=ROLE_VENDEDOR,
                nivel_acesso="vendedor",
                ativo=True,
            )
            self.vendedor.set_senha("VendTeste123!")

            self.cliente = Cliente(
                nome="Cliente Pontos",
                telefone="11999990001",
                pontos_acumulados=100,
                ativo=True,
            )
            self.cliente.set_senha("CliTeste123!")

            self.cliente_outro = Cliente(
                nome="Cliente Outro",
                telefone="11999990002",
                pontos_acumulados=50,
                ativo=True,
            )
            self.cliente_outro.set_senha("CliTeste123!")

            db.session.add_all([self.admin, self.gerente, self.vendedor, self.cliente, self.cliente_outro])
            db.session.commit()

            self.admin_id = self.admin.id_usuario
            self.gerente_id = self.gerente.id_usuario
            self.vendedor_id = self.vendedor.id_usuario
            self.cliente_id = self.cliente.id_cliente
            self.outro_id = self.cliente_outro.id_cliente

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def autenticar(self, prefixo, user_id):
        with self.client.session_transaction() as sess:
            sess["_user_id"] = f"{prefixo}_{user_id}"
            sess["_fresh"] = True

    def test_ajuste_adicionar_pontos_sucesso(self):
        self.autenticar("u", self.admin_id)
        payload = {
            "operacao": "adicionar",
            "quantidade": 50,
            "motivo": "Bonificação de aniversário da loja",
        }
        resp = self.client.post(f"/api/clientes/{self.cliente_id}/pontos/ajuste", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["saldo_atual"], 150)

        with self.app.app_context():
            cli = db.session.get(Cliente, self.cliente_id)
            self.assertEqual(cli.pontos_acumulados, 150)

            mov = MovimentacaoPontos.query.filter_by(id_cliente=self.cliente_id).one()
            self.assertEqual(mov.tipo, "AJUSTE_POSITIVO")
            self.assertEqual(mov.quantidade, 50)
            self.assertEqual(mov.saldo_anterior, 100)
            self.assertEqual(mov.saldo_posterior, 150)
            self.assertEqual(mov.motivo, "Bonificação de aniversário da loja")
            self.assertEqual(mov.id_usuario, self.admin_id)

    def test_ajuste_remover_pontos_sucesso(self):
        self.autenticar("u", self.gerente_id)
        payload = {
            "operacao": "remover",
            "quantidade": 30,
            "motivo": "Correção de pontuação indevida",
        }
        resp = self.client.post(f"/api/clientes/{self.cliente_id}/pontos/ajuste", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["saldo_atual"], 70)

        with self.app.app_context():
            cli = db.session.get(Cliente, self.cliente_id)
            self.assertEqual(cli.pontos_acumulados, 70)

            mov = MovimentacaoPontos.query.filter_by(id_cliente=self.cliente_id).one()
            self.assertEqual(mov.tipo, "AJUSTE_NEGATIVO")
            self.assertEqual(mov.quantidade, -30)
            self.assertEqual(mov.saldo_anterior, 100)
            self.assertEqual(mov.saldo_posterior, 70)

    def test_ajuste_motivo_obrigatorio(self):
        self.autenticar("u", self.admin_id)
        payload = {"operacao": "adicionar", "quantidade": 20, "motivo": "   "}
        resp = self.client.post(f"/api/clientes/{self.cliente_id}/pontos/ajuste", json=payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("motivo", resp.get_json()["erro"].lower())

    def test_ajuste_quantidade_zero_ou_negativa_rejeitada(self):
        self.autenticar("u", self.admin_id)
        resp_zero = self.client.post(
            f"/api/clientes/{self.cliente_id}/pontos/ajuste",
            json={"operacao": "adicionar", "quantidade": 0, "motivo": "Teste"}
        )
        self.assertEqual(resp_zero.status_code, 400)

        resp_neg = self.client.post(
            f"/api/clientes/{self.cliente_id}/pontos/ajuste",
            json={"operacao": "adicionar", "quantidade": -10, "motivo": "Teste"}
        )
        self.assertEqual(resp_neg.status_code, 400)

    def test_ajuste_remover_acima_do_saldo_rejeitado(self):
        self.autenticar("u", self.admin_id)
        # Saldo é 100; tenta remover 150
        payload = {"operacao": "remover", "quantidade": 150, "motivo": "Estorno"}
        resp = self.client.post(f"/api/clientes/{self.cliente_id}/pontos/ajuste", json=payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("insuficiente", resp.get_json()["erro"].lower())

        with self.app.app_context():
            cli = db.session.get(Cliente, self.cliente_id)
            self.assertEqual(cli.pontos_acumulados, 100)

    def test_vendedor_bloqueado_ao_remover_pontos(self):
        self.autenticar("u", self.vendedor_id)
        payload = {"operacao": "remover", "quantidade": 10, "motivo": "Tentativa vendedor"}
        resp = self.client.post(f"/api/clientes/{self.cliente_id}/pontos/ajuste", json=payload)
        self.assertEqual(resp.status_code, 403)

    def test_extrato_cliente_segregado(self):
        # Gera movimentação via compra
        self.autenticar("u", self.admin_id)
        self.client.post("/api/compras/", json={"id_cliente": self.cliente_id, "valor": 50})

        # Cliente acessa o próprio extrato -> 200
        self.autenticar("c", self.cliente_id)
        resp_proprio = self.client.get(f"/api/clientes/{self.cliente_id}/extrato")
        self.assertEqual(resp_proprio.status_code, 200)
        self.assertEqual(len(resp_proprio.get_json()["extrato"]), 1)

        # Cliente tenta acessar extrato de outro -> 403 (IDOR bloqueado)
        resp_outro = self.client.get(f"/api/clientes/{self.outro_id}/extrato")
        self.assertEqual(resp_outro.status_code, 403)

    def test_transacao_compra_atualiza_ledger_automaticamente(self):
        self.autenticar("u", self.admin_id)
        resp = self.client.post("/api/compras/", json={"id_cliente": self.cliente_id, "valor": 80.00})
        self.assertEqual(resp.status_code, 201)

        with self.app.app_context():
            mov = MovimentacaoPontos.query.filter_by(id_cliente=self.cliente_id, tipo="COMPRA").first()
            self.assertIsNotNone(mov)
            self.assertEqual(mov.quantidade, 80)
            self.assertEqual(mov.saldo_anterior, 100)
            self.assertEqual(mov.saldo_posterior, 180)


if __name__ == "__main__":
    unittest.main()
