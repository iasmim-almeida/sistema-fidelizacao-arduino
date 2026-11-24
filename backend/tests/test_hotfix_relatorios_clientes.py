import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app import create_app
from app.extensions import db, limiter
from app.models.historico import Historico
from app.models.usuario import Usuario


class HotfixRelatoriosClientesTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app("testing")
        limiter.enabled = False
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            self.admin = Usuario(
                nome="Vendedora Fixture",
                login="vendedora_hotfix",
                nivel_acesso="ADMIN",
                cargo="vendedora",
                ativo=True,
            )
            self.cliente = Usuario(
                nome="Cliente Histórico",
                login="11910000001",
                telefone="11910000001",
                email="historico@example.test",
                nivel_acesso="CLIENTE",
                cargo="cliente",
                ativo=True,
                pontos_acumulados=2,
            )
            self.cliente_sem_compra = Usuario(
                nome="Cliente Sem Compra",
                login="11910000002",
                telefone="11910000002",
                nivel_acesso="CLIENTE",
                cargo="cliente",
                ativo=True,
            )
            self.cliente_inativo = Usuario(
                nome="Cliente Inativo",
                login="11910000003",
                telefone="11910000003",
                nivel_acesso="CLIENTE",
                cargo="cliente",
                ativo=False,
            )
            for usuario in (
                self.admin,
                self.cliente,
                self.cliente_sem_compra,
                self.cliente_inativo,
            ):
                usuario.set_senha("FixtureSegura123!")
            db.session.add_all([
                self.admin,
                self.cliente,
                self.cliente_sem_compra,
                self.cliente_inativo,
            ])
            db.session.flush()

            agora = datetime.now(timezone.utc).replace(tzinfo=None)
            db.session.add_all([
                Historico(
                    id_usuario=self.cliente.id_usuario,
                    tipo_movimentacao="COMPRA",
                    pontos=1,
                    data_movimentacao=agora - timedelta(days=2),
                    saldo_anterior=0,
                    saldo_posterior=1,
                    origem="fixture",
                ),
                Historico(
                    id_usuario=self.cliente.id_usuario,
                    tipo_movimentacao="COMPRA",
                    pontos=1,
                    data_movimentacao=agora - timedelta(days=45),
                    saldo_anterior=None,
                    saldo_posterior=None,
                    origem="migracao",
                ),
                Historico(
                    id_usuario=self.cliente.id_usuario,
                    tipo_movimentacao="RESGATE",
                    pontos=-1,
                    data_movimentacao=agora - timedelta(days=1),
                    saldo_anterior=2,
                    saldo_posterior=1,
                    origem="fixture",
                ),
                Historico(
                    id_usuario=self.cliente.id_usuario,
                    tipo_movimentacao="AJUSTE_POSITIVO",
                    pontos=2,
                    data_movimentacao=agora - timedelta(hours=12),
                    saldo_anterior=1,
                    saldo_posterior=3,
                    origem="fixture",
                ),
                Historico(
                    id_usuario=self.cliente.id_usuario,
                    tipo_movimentacao="AJUSTE_NEGATIVO",
                    pontos=-1,
                    data_movimentacao=agora - timedelta(hours=6),
                    saldo_anterior=3,
                    saldo_posterior=2,
                    origem="fixture",
                ),
            ])
            db.session.commit()
            self.admin_id = self.admin.id_usuario
            self.cliente_id = self.cliente.id_usuario

        with self.client.session_transaction() as sessao:
            sessao["_user_id"] = f"u_{self.admin_id}"
            sessao["_fresh"] = True

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_detalhes_cliente_retorna_estatisticas_e_ultima_movimentacao(self):
        resposta = self.client.get(f"/api/clientes/{self.cliente_id}")
        self.assertEqual(resposta.status_code, 200)
        dados = resposta.get_json()
        self.assertEqual(dados["total_compras"], 2)
        self.assertEqual(dados["total_resgates"], 1)
        self.assertEqual(dados["ultima_compra"]["tipo_movimentacao"], "COMPRA")
        self.assertEqual(dados["ultimo_resgate"]["tipo_movimentacao"], "RESGATE")

    def test_serializacao_cliente_e_historico_nao_reintroduz_campos_financeiros(self):
        detalhe = self.client.get(f"/api/clientes/{self.cliente_id}").get_json()
        extrato = self.client.get(f"/api/clientes/{self.cliente_id}/extrato").get_json()
        compras = self.client.get("/api/compras/").get_json()
        serializado = repr({"detalhe": detalhe, "extrato": extrato, "compras": compras})
        self.assertNotIn("valor_compra", serializado)
        self.assertNotIn("faturamento", serializado)
        self.assertNotIn("auditoria", serializado)

    def test_extrato_preserva_compras_resgate_e_ajustes(self):
        resposta = self.client.get(f"/api/clientes/{self.cliente_id}/extrato")
        self.assertEqual(resposta.status_code, 200)
        tipos = {item["tipo"] for item in resposta.get_json()["extrato"]}
        self.assertEqual(
            tipos,
            {"COMPRA", "RESGATE", "AJUSTE_POSITIVO", "AJUSTE_NEGATIVO"},
        )

    def test_compras_historicas_nao_sao_limitadas_a_trinta_dias(self):
        resposta = self.client.get("/api/compras/")
        self.assertEqual(resposta.status_code, 200)
        compras = resposta.get_json()
        self.assertEqual(len(compras), 2)
        self.assertTrue(all(item["tipo_movimentacao"] == "COMPRA" for item in compras))

    def test_discriminadores_legados_com_caixa_e_espacos_sao_recuperados(self):
        with self.app.app_context():
            if db.engine.dialect.name != "sqlite":
                self.skipTest("Fixture de drift legado é específica do SQLite isolado.")
            db.session.execute(text("PRAGMA ignore_check_constraints = ON"))
            db.session.execute(
                text(
                    "INSERT INTO historico "
                    "(id_usuario, tipo_movimentacao, data_movimentacao, pontos, descricao) "
                    "VALUES (:cliente, ' compra ', :data, 1, 'Compra legada')"
                ),
                {
                    "cliente": self.cliente_id,
                    "data": datetime.now(timezone.utc).replace(tzinfo=None),
                },
            )
            db.session.execute(
                text(
                    "INSERT INTO historico "
                    "(id_usuario, tipo_movimentacao, data_movimentacao, pontos, descricao) "
                    "VALUES (:cliente, 'resgate ', :data, -1, 'Resgate legado')"
                ),
                {
                    "cliente": self.cliente_id,
                    "data": datetime.now(timezone.utc).replace(tzinfo=None),
                },
            )
            db.session.commit()

        compras = self.client.get("/api/compras/").get_json()
        resgates = self.client.get("/api/resgates/").get_json()
        detalhe = self.client.get(f"/api/clientes/{self.cliente_id}").get_json()
        indicadores = self.client.get("/api/relatorios/indicadores?dias=30").get_json()
        self.assertEqual(len(compras), 3)
        self.assertEqual(len(resgates), 2)
        self.assertEqual(compras[0]["tipo_movimentacao"], "COMPRA")
        self.assertEqual(resgates[0]["tipo_movimentacao"], "RESGATE")
        self.assertEqual(detalhe["total_compras"], 3)
        self.assertEqual(detalhe["total_resgates"], 2)
        self.assertEqual(indicadores["quantidade_compras"], 2)
        self.assertEqual(indicadores["quantidade_resgates"], 2)

    def test_indicadores_recentes_respeitam_formula_e_excluem_ajustes(self):
        resposta = self.client.get("/api/relatorios/indicadores?dias=30")
        self.assertEqual(resposta.status_code, 200)
        dados = resposta.get_json()
        self.assertEqual(dados["clientes_ativos"], 2)
        self.assertEqual(dados["quantidade_compras"], 1)
        self.assertEqual(dados["quantidade_resgates"], 1)
        self.assertEqual(dados["pontos_emitidos"], 1)
        self.assertEqual(dados["pontos_resgatados"], 1)
        self.assertEqual(dados["frequencia_recompra"], 0.5)
        self.assertEqual(dados["indice_resgate"], 100.0)
        self.assertEqual(dados["taxa_rotatividade"], 66.67)

    def test_indicadores_distinguem_historico_fora_do_periodo(self):
        with self.app.app_context():
            Historico.query.filter(Historico.data_movimentacao >= datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30)).delete()
            db.session.commit()
        dados = self.client.get("/api/relatorios/indicadores?dias=30").get_json()
        self.assertEqual(dados["quantidade_compras"], 0)
        self.assertFalse(dados["tem_movimentacao_periodo"])
        self.assertTrue(dados["tem_movimentacao_historica"])
        self.assertEqual(dados["quantidade_compras_total"], 1)

    def test_indicadores_sem_movimentacoes_retornam_zeros_explicitos(self):
        with self.app.app_context():
            Historico.query.delete()
            db.session.commit()
        dados = self.client.get("/api/relatorios/indicadores?dias=30").get_json()
        self.assertEqual(dados["frequencia_recompra"], 0.0)
        self.assertEqual(dados["indice_resgate"], 0.0)
        self.assertFalse(dados["tem_movimentacao_periodo"])
        self.assertFalse(dados["tem_movimentacao_historica"])

    def test_dashboard_converte_resgate_negativo_em_magnitude_positiva(self):
        dados = self.client.get("/api/dashboard/estatisticas").get_json()
        self.assertEqual(dados["pontos_utilizados"], 1)

    def test_contrato_json_contem_campos_consumidos_pelo_frontend(self):
        indicadores = self.client.get("/api/relatorios/indicadores?dias=30").get_json()
        esperados = {
            "frequencia_recompra",
            "taxa_rotatividade",
            "rotatividade_aplicavel",
            "indice_resgate",
            "clientes_com_compra_ultimos_30_dias",
            "clientes_sem_compra_ultimos_30_dias",
            "pontos_emitidos",
            "pontos_resgatados",
            "tem_movimentacao_periodo",
            "tem_movimentacao_historica",
        }
        self.assertTrue(esperados.issubset(indicadores))

    def test_templates_exibem_erros_e_estados_sem_dados(self):
        clientes = self.client.get("/clientes")
        relatorios = self.client.get("/relatorios")
        self.assertEqual(clientes.status_code, 200)
        self.assertEqual(relatorios.status_code, 200)
        html_clientes = clientes.get_data(as_text=True)
        html_relatorios = relatorios.get_data(as_text=True)
        self.assertIn('data-action="detalhes-cliente"', html_clientes)
        self.assertIn('id="alertaModalDetalhes"', html_clientes)
        self.assertIn("modal-fullscreen-sm-down", html_clientes)
        self.assertIn('id="alertaRelatorios"', html_relatorios)
        self.assertIn('id="mensagemGraficoBarras"', html_relatorios)
        self.assertNotIn("return r.ok?r.json():[]", html_relatorios)


if __name__ == "__main__":
    unittest.main()
