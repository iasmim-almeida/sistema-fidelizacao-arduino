from datetime import datetime
from app.extensions import db


class Compra(db.Model):
    __tablename__ = "compra"

    id_compra = db.Column(db.Integer, primary_key=True)
    id_cliente = db.Column(db.Integer, db.ForeignKey("cliente.id_cliente"), nullable=False)
    data = db.Column(db.DateTime, default=datetime.utcnow)
    valor = db.Column(db.Numeric(10, 2), nullable=False)
    pontos_gerados = db.Column(db.Integer, default=0, nullable=False)

    def to_dict(self):
        return {
            "id_compra": self.id_compra,
            "id_cliente": self.id_cliente,
            "data": self.data.isoformat() if self.data else None,
            "valor": float(self.valor),
            "pontos_gerados": self.pontos_gerados,
        }
