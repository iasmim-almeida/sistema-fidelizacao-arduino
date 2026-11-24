import unittest
from datetime import datetime, timezone

from app import create_app
from app.extensions import db, limiter
from app.models.historico import Historico
from app.models.usuario import Usuario


class IntegridadeConsultasTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app("testing")
        limiter.enabled = False
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            self.admin = Usuario(
                nome="Vendedora",
                login="vendedora",
                email="vendedora@teste.com",
                nivel_acesso="ADMIN",
                cargo="vendedora",
                ativo=True,
            )
            self.cliente_um = Usuario(
                nome="Cliente Um",
                login="11911111111",
                telefone="11911111111",
                nivel_acesso="CLIENTE",
                cargo="cliente",
                ativo=True,
                pontos_acumulados=10,
            )
            self.cliente_dois = Usuario(
                nome="Cliente Dois",
                login="11922222222",
                telefone="11922222222",
                nivel_acesso="CLIENTE",
                cargo="cliente",
                ativo=True,
            )
            self.cliente_inativo = Usuario(
                nome="Cliente Inativo",
                login="11933333333",
                telefone="11933333333",
                nivel_acesso="CLIENTE",
                cargo="cliente",
                ativo=False,
            )
            for usuario in (self.admin, self.cliente_um, self.cliente_dois, self.cliente_inativo):
                usuario.set_senha("SenhaTeste123!")
            db.session.add_all([
                self.admin,
                self.cliente_um,
                self.cliente_dois,
                self.cliente_inativo,
            ])
            db.session.flush()

            agora = datetime.now(timezone.utc).replace(tzinfo=None)
            db.session.add_all([
                Historico(id_usuario=self.cliente_um.id_usuario, tipo_movimentacao="COMPRA", pontos=1, data_movimentacao=agora),
                Historico(id_usuario=self.cliente_um.id_usuario, tipo_movimentacao="COMPRA", pontos=1, data_movimentacao=agora),
                Historico(id_usuario=self.cliente_um.id_usuario, tipo_movimentacao="RESGATE", pontos=1, data_movimentacao=agora),
                Historico(id_usuario=self.cliente_um.id_usuario, tipo_movimentacao="AJUSTE_POSITIVO", pontos=5, data_movimentacao=agora),
            ])
            db.session.commit()
            self.ids = {
                "admin": self.admin.id_usuario,
                "cliente": self.cliente_um.id_usuario,
            }

        with self.client.session_transaction() as sessao:
            sessao["_user_id"] = f"u_{self.ids['admin']}"
            sessao["_fresh"] = True

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_listagens_e_detalhe_filtram_tipo_de_movimentacao(self):
        compras = self.client.get("/api/compras/").get_json()
        resgates = self.client.get("/api/resgates/").get_json()
        detalhe = self.client.get(f"/api/clientes/{self.ids['cliente']}").get_json()

        self.assertEqual([item["tipo_movimentacao"] for item in compras], ["COMPRA", "COMPRA"])
        self.assertEqual([item["tipo_movimentacao"] for item in resgates], ["RESGATE"])
        self.assertEqual(detalhe["total_compras"], 2)
        self.assertEqual(detalhe["total_resgates"], 1)

    def test_dashboard_exclui_administradores_das_metricas_de_cliente(self):
        dados = self.client.get("/api/dashboard/estatisticas").get_json()
        self.assertEqual(dados["total_clientes"], 3)
        self.assertEqual(dados["clientes_ativos"], 2)
        self.assertEqual(dados["total_compras"], 2)
        self.assertEqual(dados["total_resgates"], 1)
        self.assertNotIn("faturamento_total", dados)
        self.assertNotIn("faturamento_mes", dados)

    def test_indicadores_academicos_usam_periodo_e_clientes_ativos(self):
        dados = self.client.get("/api/relatorios/indicadores?dias=30").get_json()
        self.assertEqual(dados["clientes_ativos"], 2)
        self.assertEqual(dados["quantidade_compras"], 2)
        self.assertEqual(dados["frequencia_recompra"], 1.0)
        self.assertTrue(dados["rotatividade_aplicavel"])
        self.assertEqual(dados["taxa_rotatividade"], 66.67)
        self.assertEqual(dados["indice_resgate"], 50.0)

    def test_compra_por_sessao_exige_csrf(self):
        self.app.config["WTF_CSRF_ENABLED"] = True
        try:
            resposta = self.client.post(
                "/api/compras/",
                json={"telefone": "11911111111"},
            )
            self.assertEqual(resposta.status_code, 400)
            self.assertIn("CSRF", resposta.get_json()["erro"])
        finally:
            self.app.config["WTF_CSRF_ENABLED"] = False


class IdempotenciaIoTTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app("testing")
        self.app.config["WTF_CSRF_ENABLED"] = True
        limiter.enabled = False
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            cliente = Usuario(
                nome="Cliente IoT",
                login="11944444444",
                telefone="11944444444",
                nivel_acesso="CLIENTE",
                cargo="cliente",
                ativo=True,
                pontos_acumulados=0,
            )
            cliente.set_senha("ClienteIoT123!")
            db.session.add(cliente)
            db.session.commit()
            self.cliente_id = cliente.id_usuario

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_repeticao_da_mesma_chave_nao_gera_novo_ponto(self):
        headers = {
            "X-Device-Key": self.app.config["IOT_DEVICE_KEY"],
            "X-Idempotency-Key": "iot-test-operation-0001",
        }
        payload = {"telefone": "11944444444"}
        primeira = self.client.post("/api/compras/", json=payload, headers=headers)
        repetida = self.client.post("/api/compras/", json=payload, headers=headers)

        self.assertEqual(primeira.status_code, 201)
        self.assertEqual(repetida.status_code, 200)
        self.assertTrue(repetida.get_json()["duplicada"])
        with self.app.app_context():
            cliente = db.session.get(Usuario, self.cliente_id)
            self.assertEqual(cliente.pontos_acumulados, 1)
            self.assertEqual(
                Historico.query.filter_by(tipo_movimentacao="COMPRA").count(),
                1,
            )


if __name__ == "__main__":
    unittest.main()
