import re
import unittest
from datetime import timedelta
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.models.cliente import Cliente
from app.models.recompensa import Recompensa, data_local_atual
from app.models.resgate import Resgate
from app.models.usuario import Usuario


class RecompensasTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app("testing")
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            self.gestora_a = Usuario(nome="Gestora A", login="gestora-a", senha_hash="hash")
            self.gestora_b = Usuario(nome="Gestora B", login="gestora-b", senha_hash="hash")
            self.cliente_alto = Cliente(nome="Cliente Alto", telefone="11911111111", pontos_acumulados=100)
            self.cliente_baixo = Cliente(nome="Cliente Baixo", telefone="11922222222", pontos_acumulados=10)
            db.session.add_all([
                self.gestora_a,
                self.gestora_b,
                self.cliente_alto,
                self.cliente_baixo,
            ])
            db.session.commit()
            self.ids = {
                "gestora_a": self.gestora_a.id_usuario,
                "gestora_b": self.gestora_b.id_usuario,
                "cliente_alto": self.cliente_alto.id_cliente,
                "cliente_baixo": self.cliente_baixo.id_cliente,
            }

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def autenticar(self, prefixo, identificador):
        with self.client.session_transaction() as sessao:
            sessao["_user_id"] = f"{prefixo}_{identificador}"
            sessao["_fresh"] = True

    def payload_valido(self, **alteracoes):
        dados = {
            "nome": "10% de desconto",
            "custo_pontos": 50,
            "tipo": "desconto_percentual",
            "valor_beneficio": "10.00",
            "validade": (data_local_atual() + timedelta(days=30)).isoformat(),
            "quantidade_total": 2,
            "status": "ativa",
        }
        dados.update(alteracoes)
        return dados

    def criar_recompensa(self, id_usuario=None, **alteracoes):
        with self.app.app_context():
            recompensa = Recompensa(
                id_usuario=id_usuario or self.ids["gestora_a"],
                nome=alteracoes.get("nome", "Recompensa teste"),
                custo_pontos=alteracoes.get("custo_pontos", 50),
                tipo=alteracoes.get("tipo", "produto_fisico"),
                valor_beneficio=alteracoes.get("valor_beneficio"),
                validade=alteracoes.get("validade", data_local_atual() + timedelta(days=30)),
                quantidade_total=alteracoes.get("quantidade_total", 2),
                quantidade_disponivel=alteracoes.get("quantidade_disponivel", 2),
                status=alteracoes.get("status", "ativa"),
            )
            db.session.add(recompensa)
            db.session.commit()
            return recompensa.id_recompensa

    def test_anonimo_e_cliente_nao_acessam_administracao(self):
        self.assertEqual(self.client.get("/gestao-recompensas").status_code, 302)
        self.assertEqual(self.client.post("/api/recompensas/", json=self.payload_valido()).status_code, 401)

        self.autenticar("c", self.ids["cliente_alto"])
        self.assertEqual(self.client.get("/gestao-recompensas").status_code, 302)
        self.assertEqual(self.client.post("/api/recompensas/", json=self.payload_valido()).status_code, 403)

    def test_criacao_valida_deriva_proprietario_da_sessao(self):
        self.autenticar("u", self.ids["gestora_a"])
        resposta = self.client.post("/api/recompensas/", json=self.payload_valido(id_usuario=999))
        self.assertEqual(resposta.status_code, 400)

        resposta = self.client.post("/api/recompensas/", json=self.payload_valido(nome="  Cupom seguro  "))
        self.assertEqual(resposta.status_code, 201)
        dados = resposta.get_json()
        self.assertEqual(dados["nome"], "Cupom seguro")
        self.assertEqual(dados["id_usuario"], self.ids["gestora_a"])
        self.assertEqual(dados["quantidade_disponivel"], 2)

    def test_mutacoes_web_exigem_csrf_e_aceitam_token_da_pagina(self):
        self.app.config["WTF_CSRF_ENABLED"] = True
        self.autenticar("u", self.ids["gestora_a"])
        sem_token = self.client.post("/api/recompensas/", json=self.payload_valido())
        self.assertEqual(sem_token.status_code, 400)

        pagina = self.client.get("/gestao-recompensas")
        token = re.search(
            rb'<meta name="csrf-token" content="([^"]+)">',
            pagina.data,
        ).group(1).decode()
        com_token = self.client.post(
            "/api/recompensas/",
            json=self.payload_valido(),
            headers={"X-CSRFToken": token},
        )
        self.assertEqual(com_token.status_code, 201)

    def test_criacoes_invalidas(self):
        self.autenticar("u", self.ids["gestora_a"])
        casos = [
            ({"nome": "   "}, "nome"),
            ({"custo_pontos": 0}, "custo"),
            ({"custo_pontos": -1}, "custo"),
            ({"custo_pontos": 1.5}, "inteiro"),
            ({"custo_pontos": "10"}, "inteiro"),
            ({"custo_pontos": None}, "inteiro"),
            ({"custo_pontos": 1_000_000_001}, "não exceder"),
            ({"tipo": "livre"}, "tipo"),
            ({"quantidade_total": -1}, "quantidade"),
            ({"quantidade_total": "2"}, "inteiro"),
            ({"status": "excluida"}, "status"),
            ({"tipo": "desconto_percentual", "valor_beneficio": 0}, "maior que zero"),
            ({"tipo": "desconto_percentual", "valor_beneficio": 101}, "percentual"),
            ({"tipo": "desconto_valor_fixo", "valor_beneficio": 0}, "maior que zero"),
            ({"validade": "31/12/2030"}, "AAAA-MM-DD"),
            ({"validade": (data_local_atual() - timedelta(days=1)).isoformat()}, "passado"),
        ]
        for alteracoes, trecho in casos:
            with self.subTest(alteracoes=alteracoes):
                resposta = self.client.post("/api/recompensas/", json=self.payload_valido(**alteracoes))
                self.assertEqual(resposta.status_code, 400)
                self.assertIn(trecho, resposta.get_json()["erro"])

    def test_idor_impede_leitura_edicao_e_alteracao_de_proprietario(self):
        id_recompensa = self.criar_recompensa()
        self.autenticar("u", self.ids["gestora_b"])
        self.assertEqual(self.client.get(f"/api/recompensas/{id_recompensa}").status_code, 404)
        self.assertEqual(
            self.client.patch(f"/api/recompensas/{id_recompensa}", json={"status": "pausada"}).status_code,
            404,
        )
        with self.app.app_context():
            self.assertEqual(db.session.get(Recompensa, id_recompensa).status, "ativa")

    def test_pausar_reativar_e_editar_estoque_preserva_consumo(self):
        id_recompensa = self.criar_recompensa(quantidade_total=5, quantidade_disponivel=3)
        self.autenticar("u", self.ids["gestora_a"])
        pausada = self.client.patch(f"/api/recompensas/{id_recompensa}", json={"status": "pausada"})
        self.assertEqual(pausada.status_code, 200)
        self.assertEqual(pausada.get_json()["estado"], "pausada")
        reativada = self.client.patch(
            f"/api/recompensas/{id_recompensa}",
            json={"status": "ativa", "quantidade_total": 7},
        )
        self.assertEqual(reativada.status_code, 200)
        self.assertEqual(reativada.get_json()["quantidade_disponivel"], 5)
        invalida = self.client.patch(f"/api/recompensas/{id_recompensa}", json={"quantidade_total": 1})
        self.assertEqual(invalida.status_code, 400)

    def test_catalogo_mantem_recompensa_com_pontos_insuficientes(self):
        id_recompensa = self.criar_recompensa(custo_pontos=50)
        self.autenticar("c", self.ids["cliente_baixo"])
        resposta = self.client.get("/api/recompensas/")
        self.assertEqual(resposta.status_code, 200)
        item = next(r for r in resposta.get_json() if r["id_recompensa"] == id_recompensa)
        self.assertFalse(item["pode_resgatar"])
        self.assertEqual(item["motivo_indisponibilidade"], "Pontos insuficientes")
        self.assertEqual(item["pontos_faltantes"], 40)

    def test_resgate_usa_custo_do_banco_e_atualiza_tudo(self):
        id_recompensa = self.criar_recompensa(custo_pontos=50, quantidade_total=2, quantidade_disponivel=2)
        self.autenticar("c", self.ids["cliente_alto"])
        resposta = self.client.post("/api/resgates/", json={"id_recompensa": id_recompensa})
        self.assertEqual(resposta.status_code, 201)
        self.assertEqual(resposta.get_json()["saldo_atualizado"], 50)
        with self.app.app_context():
            cliente = db.session.get(Cliente, self.ids["cliente_alto"])
            recompensa = db.session.get(Recompensa, id_recompensa)
            resgate = Resgate.query.one()
            self.assertEqual(cliente.pontos_acumulados, 50)
            self.assertEqual(recompensa.quantidade_disponivel, 1)
            self.assertEqual(resgate.id_recompensa, id_recompensa)
            self.assertEqual(resgate.pontos_utilizados, 50)
            self.assertEqual(resgate.descricao_recompensa, recompensa.nome)

    def test_payload_nao_pode_manipular_custo_descricao_ou_cliente(self):
        id_recompensa = self.criar_recompensa(custo_pontos=50)
        self.autenticar("c", self.ids["cliente_alto"])
        resposta = self.client.post(
            "/api/resgates/",
            json={
                "id_recompensa": id_recompensa,
                "pontos_utilizados": 1,
                "descricao_recompensa": "Injetada",
            },
        )
        self.assertEqual(resposta.status_code, 400)
        resposta = self.client.post(
            "/api/resgates/",
            json={"id_recompensa": id_recompensa, "id_cliente": self.ids["cliente_baixo"]},
        )
        self.assertEqual(resposta.status_code, 403)
        with self.app.app_context():
            self.assertEqual(db.session.get(Cliente, self.ids["cliente_alto"]).pontos_acumulados, 100)
            self.assertEqual(Resgate.query.count(), 0)

    def test_rejeita_recompensas_pausada_expirada_esgotada_e_saldo_baixo(self):
        casos = [
            ({"status": "pausada"}, 409),
            ({"validade": data_local_atual() - timedelta(days=1)}, 409),
            ({"quantidade_total": 1, "quantidade_disponivel": 0}, 409),
            ({"custo_pontos": 200}, 400),
        ]
        self.autenticar("c", self.ids["cliente_alto"])
        for alteracoes, status in casos:
            with self.subTest(alteracoes=alteracoes):
                id_recompensa = self.criar_recompensa(**alteracoes)
                resposta = self.client.post("/api/resgates/", json={"id_recompensa": id_recompensa})
                self.assertEqual(resposta.status_code, status)
        with self.app.app_context():
            self.assertEqual(db.session.get(Cliente, self.ids["cliente_alto"]).pontos_acumulados, 100)
            self.assertEqual(Resgate.query.count(), 0)

    def test_ultima_unidade_so_pode_ser_resgatada_uma_vez(self):
        id_recompensa = self.criar_recompensa(quantidade_total=1, quantidade_disponivel=1, custo_pontos=10)
        self.autenticar("c", self.ids["cliente_alto"])
        self.assertEqual(self.client.post("/api/resgates/", json={"id_recompensa": id_recompensa}).status_code, 201)
        self.autenticar("c", self.ids["cliente_baixo"])
        self.assertEqual(self.client.post("/api/resgates/", json={"id_recompensa": id_recompensa}).status_code, 409)
        with self.app.app_context():
            self.assertEqual(db.session.get(Recompensa, id_recompensa).quantidade_disponivel, 0)
            self.assertEqual(Resgate.query.count(), 1)

    def test_falha_no_commit_faz_rollback_completo(self):
        id_recompensa = self.criar_recompensa(custo_pontos=50, quantidade_total=2, quantidade_disponivel=2)
        self.autenticar("c", self.ids["cliente_alto"])
        with patch.object(db.session, "commit", side_effect=RuntimeError("falha simulada")):
            resposta = self.client.post("/api/resgates/", json={"id_recompensa": id_recompensa})
        self.assertEqual(resposta.status_code, 500)
        with self.app.app_context():
            self.assertEqual(db.session.get(Cliente, self.ids["cliente_alto"]).pontos_acumulados, 100)
            self.assertEqual(db.session.get(Recompensa, id_recompensa).quantidade_disponivel, 2)
            self.assertEqual(Resgate.query.count(), 0)

    def test_gestora_so_resgata_recompensa_propria(self):
        id_recompensa = self.criar_recompensa(id_usuario=self.ids["gestora_b"])
        self.autenticar("u", self.ids["gestora_a"])
        resposta = self.client.post(
            "/api/resgates/",
            json={"id_cliente": self.ids["cliente_alto"], "id_recompensa": id_recompensa},
        )
        self.assertEqual(resposta.status_code, 404)

    def test_historico_legado_sem_recompensa_continua_serializavel(self):
        with self.app.app_context():
            legado = Resgate(
                id_cliente=self.ids["cliente_alto"],
                id_recompensa=None,
                pontos_utilizados=10,
                descricao_recompensa="Prêmio legado",
            )
            db.session.add(legado)
            db.session.commit()
        self.autenticar("c", self.ids["cliente_alto"])
        resposta = self.client.get("/api/resgates/")
        self.assertEqual(resposta.status_code, 200)
        self.assertIsNone(resposta.get_json()[0]["id_recompensa"])


if __name__ == "__main__":
    unittest.main()
