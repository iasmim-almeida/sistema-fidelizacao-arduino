import unittest
from datetime import datetime, timedelta, timezone

from app import create_app
from app.extensions import db, limiter
from app.models.historico import Historico
from app.models.usuario import Usuario


class IndicadoresAcademicosTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app("testing")
        limiter.enabled = False
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            admin = Usuario(
                nome="Vendedora Acadêmica",
                login="admin.academico",
                email="admin.academico@teste.local",
                nivel_acesso="ADMIN",
                cargo="vendedora",
                ativo=True,
            )
            admin.set_senha("SenhaAcademica123!")
            clientes = []
            for indice in range(9):
                cliente = Usuario(
                    nome=f"Cliente Acadêmico {indice + 1}",
                    login=f"1199000000{indice}",
                    telefone=f"1199000000{indice}",
                    nivel_acesso="CLIENTE",
                    cargo="cliente",
                    ativo=True,
                    pontos_acumulados=10,
                )
                cliente.set_senha("SenhaCliente123!")
                clientes.append(cliente)

            db.session.add_all([admin, *clientes])
            db.session.flush()
            agora = datetime.now(timezone.utc).replace(tzinfo=None)

            movimentos = [
                Historico(
                    id_usuario=clientes[indice % 8].id_usuario,
                    tipo_movimentacao="COMPRA",
                    pontos=1,
                    data_movimentacao=agora - timedelta(days=indice % 10),
                )
                for indice in range(11)
            ]
            movimentos.extend([
                Historico(
                    id_usuario=clientes[0].id_usuario,
                    tipo_movimentacao="RESGATE",
                    pontos=-2,
                    data_movimentacao=agora - timedelta(days=2),
                ),
                Historico(
                    id_usuario=clientes[1].id_usuario,
                    tipo_movimentacao="RESGATE",
                    pontos=3,
                    data_movimentacao=agora - timedelta(days=3),
                ),
                Historico(
                    id_usuario=clientes[8].id_usuario,
                    tipo_movimentacao="AJUSTE_POSITIVO",
                    pontos=50,
                    data_movimentacao=agora,
                ),
                Historico(
                    id_usuario=admin.id_usuario,
                    tipo_movimentacao="COMPRA",
                    pontos=1,
                    data_movimentacao=agora,
                ),
            ])
            db.session.add_all(movimentos)
            db.session.commit()
            self.admin_id = admin.id_usuario

        with self.client.session_transaction() as sessao:
            sessao["_user_id"] = f"u_{self.admin_id}"
            sessao["_fresh"] = True

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_resultados_academicos_do_periodo_de_19_dias(self):
        resposta = self.client.get("/api/relatorios/indicadores?dias=19")
        self.assertEqual(resposta.status_code, 200)
        dados = resposta.get_json()

        self.assertEqual(dados["clientes_ativos"], 9)
        self.assertEqual(dados["quantidade_compras"], 11)
        self.assertEqual(dados["pontos_emitidos"], 11)
        self.assertEqual(dados["quantidade_resgates"], 2)
        self.assertEqual(dados["pontos_resgatados"], 5)
        self.assertEqual(dados["frequencia_recompra"], 1.22)
        self.assertEqual(dados["indice_resgate"], 45.45)
        self.assertFalse(dados["rotatividade_aplicavel"])
        self.assertIsNone(dados["taxa_rotatividade"])

    def test_rotatividade_ignora_ajuste_como_retorno_a_loja(self):
        dados = self.client.get("/api/relatorios/indicadores?dias=30").get_json()

        self.assertTrue(dados["rotatividade_aplicavel"])
        self.assertEqual(dados["total_clientes_cadastrados"], 9)
        self.assertEqual(dados["clientes_com_compra_ultimos_30_dias"], 8)
        self.assertEqual(dados["taxa_rotatividade"], 11.11)


if __name__ == "__main__":
    unittest.main()
