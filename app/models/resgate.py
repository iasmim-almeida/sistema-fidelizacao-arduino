from datetime import datetime, timezone
from app.extensions import db


class Resgate(db.Model):
    __tablename__ = "resgate"

    id_resgate = db.Column(db.Integer, primary_key=True)
    id_cliente = db.Column(db.Integer, db.ForeignKey("cliente.id_cliente"), nullable=False)
    id_recompensa = db.Column(
        db.Integer,
        db.ForeignKey("recompensa.id_recompensa", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    data = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    pontos_utilizados = db.Column(db.Integer, nullable=False)
    descricao_recompensa = db.Column(db.String(200), nullable=False)

    recompensa = db.relationship("Recompensa", back_populates="resgates")

    def to_dict(self):
        return {
            "id_resgate": self.id_resgate,
            "id_cliente": self.id_cliente,
            "id_recompensa": self.id_recompensa,
            "data": self.data.isoformat() if self.data else None,
            "pontos_utilizados": self.pontos_utilizados,
            "descricao_recompensa": self.descricao_recompensa,
        }
