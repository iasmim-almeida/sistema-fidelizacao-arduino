"""Integração somente no cluster descartável explicitamente indicado."""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from app import create_app
from app.extensions import db
from app.models.usuario import Usuario
from app.models.historico import Historico
from app.models.recompensa import Produto


@unittest.skipUnless(os.getenv("ITCLUBE_TEST_POSTGRES"), "PostgreSQL descartável não configurado")
class ReleasePostgresqlTest(unittest.TestCase):
    def setUp(self):
        uri = os.environ["ITCLUBE_TEST_POSTGRES"]
        if "127.0.0.1:55439/" not in uri:
            raise RuntimeError("Use exclusivamente o cluster descartável na porta 55439")
        from app.config import TestingConfig
        previous = TestingConfig.SQLALCHEMY_DATABASE_URI
        TestingConfig.SQLALCHEMY_DATABASE_URI = uri
        self.app = create_app("testing")
        TestingConfig.SQLALCHEMY_DATABASE_URI = previous
        with self.app.app_context():
            db.drop_all()
            db.create_all()
            admin = Usuario(nome="Admin", login="admin", nivel_acesso="ADMIN", cargo="proprietario")
            one = Usuario(nome="Um", login="um", telefone="11911111111", nivel_acesso="CLIENTE")
            two = Usuario(nome="Dois", login="dois", telefone="11922222222", nivel_acesso="CLIENTE")
            db.session.add_all([admin, one, two])
            db.session.commit()
            self.ids = (admin.id_usuario, one.id_usuario, two.id_usuario)

    def client(self, user=None):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = f"u_{user or self.ids[0]}"
            session["_fresh"] = True
        return client

    def test_concurrent_idempotency(self):
        def buy(customer):
            return self.client().post("/api/compras/", json={"id_cliente": customer}, headers={"X-Idempotency-Key": "same-key-123"}).status_code
        with ThreadPoolExecutor(2) as executor:
            self.assertEqual(sorted(executor.map(buy, [self.ids[1]] * 2)), [200, 201])
        with self.app.app_context():
            self.assertEqual(Historico.query.count(), 1)
            self.assertEqual(db.session.get(Usuario, self.ids[1]).pontos_acumulados, 1)

    def test_concurrent_different_clients(self):
        def buy(customer):
            return self.client().post("/api/compras/", json={"id_cliente": customer}, headers={"X-Idempotency-Key": "different-clients"}).status_code
        with ThreadPoolExecutor(2) as executor:
            self.assertEqual(sorted(executor.map(buy, self.ids[1:])), [201, 409])
        with self.app.app_context():
            self.assertEqual(Historico.query.count(), 1)
            self.assertEqual(sum(db.session.get(Usuario, i).pontos_acumulados for i in self.ids[1:]), 1)

    def test_resgate_estoque_e_saldo(self):
        with self.app.app_context():
            db.session.get(Usuario, self.ids[1]).pontos_acumulados = 5
            reward = Produto(id_usuario=self.ids[0], nome="Prêmio", custo_pontos=2, validade=date.today()+timedelta(days=1), quantidade_total=3, quantidade_disponivel=3)
            db.session.add(reward)
            db.session.commit()
            reward_id = reward.id_produto
        response = self.client().post("/api/resgates/", json={"id_cliente": self.ids[1], "id_recompensa": reward_id})
        self.assertEqual(response.status_code, 201)
        with self.app.app_context():
            self.assertEqual(db.session.get(Usuario, self.ids[1]).pontos_acumulados, 3)
            self.assertEqual(db.session.get(Produto, reward_id).quantidade_disponivel, 2)

    def test_logout_csrf_remember(self):
        for user in self.ids[:2]:
            client = self.client(user)
            self.app.config["WTF_CSRF_ENABLED"] = True
            from flask_wtf.csrf import generate_csrf
            with self.app.test_request_context():
                token = generate_csrf()
                from flask import session
                raw = session["csrf_token"]
            with client.session_transaction() as session:
                session["csrf_token"] = raw
            client.set_cookie("remember_token", "invalid-old-cookie")
            response = client.post("/auth/logout", headers={"X-CSRFToken": token})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(any("remember_token=;" in cookie for cookie in response.headers.getlist("Set-Cookie")))
            self.assertEqual(client.get("/auth/me").status_code, 401)
            self.assertEqual(client.get("/api/compras/").status_code, 401)
            self.assertEqual(client.get("/dashboard").status_code, 302)

    def test_delta(self):
        for points in (-2, 2):
            self.assertEqual(Historico(tipo_movimentacao="RESGATE", pontos=points).delta_pontos, -2)

    def test_ajustes_detalhes_extrato_e_relatorios(self):
        client = self.client()
        for operation, quantity in (("adicionar", 4), ("remover", 1)):
            response = client.post(f"/api/clientes/{self.ids[1]}/pontos/ajuste", json={"operacao": operation, "quantidade": quantity, "motivo": "Fixture"})
            self.assertEqual(response.status_code, 200)
        for url in (f"/api/clientes/{self.ids[1]}", f"/api/clientes/{self.ids[1]}/extrato", "/api/dashboard/estatisticas", "/api/relatorios/indicadores?dias=30"):
            self.assertEqual(client.get(url).status_code, 200)
        self.assertEqual(client.get(f"/api/clientes/{self.ids[1]}/extrato").json["saldo_atual"], 3)
        self.assertEqual(self.client(self.ids[1]).get(f"/api/clientes/{self.ids[2]}/extrato").status_code, 403)
        self.assertEqual(client.post(f"/api/clientes/{self.ids[1]}/status", json={"ativo": False}).status_code, 200)

    def test_reward_name_and_constraint(self):
        from sqlalchemy.exc import IntegrityError
        client = self.client()
        payload = {"nome": "x" * 101, "tipo": "produto_fisico", "custo_pontos": 1, "quantidade_total": 1, "validade": (date.today()+timedelta(days=1)).isoformat(), "status": "ativa"}
        self.assertEqual(client.post("/api/recompensas/", json=payload).status_code, 400)
        payload["nome"] = "x" * 100
        self.assertEqual(client.post("/api/recompensas/", json=payload).status_code, 201)
        with self.app.app_context():
            db.session.add(Produto(nome="inválido", tipo="desconto_percentual", custo_pontos=1, valor_beneficio=None, validade=date.today()))
            with self.assertRaises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_unrelated_integrity_error_rollback(self):
        from unittest.mock import patch
        from app.services.pontos import registrar_movimentacao
        def invalid(**kwargs):
            return registrar_movimentacao(**kwargs, recompensa_id=999999)
        with patch("app.routes.compras.registrar_movimentacao", side_effect=invalid):
            response = self.client().post("/api/compras/", json={"id_cliente": self.ids[1]}, headers={"X-Idempotency-Key": "invalid-foreign-key"})
        self.assertEqual(response.status_code, 500)
        with self.app.app_context():
            self.assertEqual(Historico.query.count(), 0)
            self.assertEqual(db.session.get(Usuario, self.ids[1]).pontos_acumulados, 0)
