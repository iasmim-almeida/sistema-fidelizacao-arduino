from datetime import datetime
from app.extensions import db


class Resgate(db.Model):
    __tablename__ = "resgate"

    id_resgate = db.Column(db.Integer, primary_key=True)
    id_cliente = db.Column(db.Integer, db.ForeignKey("cliente.id_cliente"), nullable=False)
    data = db.Column(db.DateTime, default=datetime.utcnow)
    pontos_utilizados = db.Column(db.Integer, nullable=False)
    descricao_recompensa = db.Column(db.String(200), nullable=False)

    def to_dict(self):
        return {
            "id_resgate": self.id_resgate,
            "id_cliente": self.id_cliente,
            "data": self.data.isoformat() if self.data else None,
            "pontos_utilizados": self.pontos_utilizados,
            "descricao_recompensa": self.descricao_recompensa,
        }
