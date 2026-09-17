from datetime import datetime, timezone

from sqlalchemy.orm import synonym

from app.extensions import db


def agora_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Historico(db.Model):
    __tablename__ = "historico"

    id_historico = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey("usuario.id_usuario", ondelete="CASCADE"), nullable=False, index=True)
    id_produto = db.Column(db.Integer, db.ForeignKey("produto.id_produto", ondelete="SET NULL"), nullable=True, index=True)
    tipo_movimentacao = db.Column(db.String(20), nullable=False, default="AJUSTE_POSITIVO", index=True)
    data_movimentacao = db.Column(db.DateTime, nullable=False, default=agora_utc, index=True)
    pontos = db.Column(db.Integer, nullable=False)
    descricao = db.Column(db.String(255), nullable=True)
    valor_compra = db.Column(db.Numeric(10, 2), nullable=True)
    saldo_anterior = db.Column(db.Integer, nullable=True)
    saldo_posterior = db.Column(db.Integer, nullable=True)
    origem = db.Column(db.String(50), nullable=True)

    id_cliente = synonym("id_usuario")
    id_recompensa = synonym("id_produto")
    id_compra = synonym("id_historico")
    id_resgate = synonym("id_historico")
    tipo = synonym("tipo_movimentacao")
    data = synonym("data_movimentacao")
    data_hora = synonym("data_movimentacao")
    quantidade = synonym("pontos")
    pontos_gerados = synonym("pontos")
    pontos_utilizados = synonym("pontos")
    valor = synonym("valor_compra")
    descricao_recompensa = synonym("descricao")
    motivo = synonym("descricao")

    def to_dict(self):
        return {
            "id_historico": self.id_historico,
            "id_compra": self.id_historico if self.tipo_movimentacao == "COMPRA" else None,
            "id_resgate": self.id_historico if self.tipo_movimentacao == "RESGATE" else None,
            "id_cliente": self.id_usuario,
            "id_usuario": self.id_usuario,
            "id_produto": self.id_produto,
            "id_recompensa": self.id_produto,
            "tipo_movimentacao": self.tipo_movimentacao,
            "tipo": self.tipo_movimentacao,
            "data": self.data_movimentacao.isoformat() if self.data_movimentacao else None,
            "data_hora": self.data_movimentacao.isoformat() if self.data_movimentacao else None,
            "pontos": self.pontos,
            "quantidade": self.pontos,
            "pontos_gerados": self.pontos if self.tipo_movimentacao == "COMPRA" else None,
            "pontos_utilizados": abs(self.pontos) if self.tipo_movimentacao == "RESGATE" else None,
            "valor": float(self.valor_compra) if self.valor_compra is not None else None,
            "descricao": self.descricao,
            "descricao_recompensa": self.descricao if self.tipo_movimentacao == "RESGATE" else None,
            "saldo_anterior": self.saldo_anterior,
            "saldo_posterior": self.saldo_posterior,
            "origem": self.origem,
            "motivo": self.descricao,
        }
