from datetime import datetime, timezone
from app.extensions import db


def agora_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class MovimentacaoPontos(db.Model):
    __tablename__ = "movimentacao_pontos"

    id_movimentacao = db.Column(db.Integer, primary_key=True)
    id_cliente = db.Column(
        db.Integer,
        db.ForeignKey("cliente.id_cliente", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tipo = db.Column(db.String(30), nullable=False, index=True)
    # quantidade: positivo para crédito, negativo para débito
    quantidade = db.Column(db.Integer, nullable=False)
    saldo_anterior = db.Column(db.Integer, nullable=False)
    saldo_posterior = db.Column(db.Integer, nullable=False)
    origem = db.Column(db.String(50), nullable=False, default="sistema")
    motivo = db.Column(db.String(255), nullable=True)

    # Rastreabilidade / chaves estrangeiras
    id_usuario = db.Column(
        db.Integer,
        db.ForeignKey("usuario.id_usuario", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    id_compra = db.Column(
        db.Integer,
        db.ForeignKey("compra.id_compra", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    id_resgate = db.Column(
        db.Integer,
        db.ForeignKey("resgate.id_resgate", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    id_recompensa = db.Column(
        db.Integer,
        db.ForeignKey("recompensa.id_recompensa", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    data_hora = db.Column(db.DateTime, nullable=False, default=agora_utc, index=True)

    # Relacionamentos
    usuario = db.relationship("Usuario", backref="movimentacoes_pontos")
    compra = db.relationship("Compra", backref="movimentacoes_pontos")
    resgate = db.relationship("Resgate", backref="movimentacoes_pontos")
    recompensa = db.relationship("Recompensa", backref="movimentacoes_pontos")

    def to_dict(self):
        return {
            "id_movimentacao": self.id_movimentacao,
            "id_cliente": self.id_cliente,
            "tipo": self.tipo,
            "quantidade": self.quantidade,
            "saldo_anterior": self.saldo_anterior,
            "saldo_posterior": self.saldo_posterior,
            "origem": self.origem,
            "motivo": self.motivo,
            "id_usuario": self.id_usuario,
            "usuario_nome": self.usuario.nome if self.usuario else None,
            "id_compra": self.id_compra,
            "id_resgate": self.id_resgate,
            "id_recompensa": self.id_recompensa,
            "recompensa_nome": self.recompensa.nome if self.recompensa else None,
            "data_hora": self.data_hora.isoformat() if self.data_hora else None,
        }
