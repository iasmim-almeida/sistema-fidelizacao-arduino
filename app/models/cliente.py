from datetime import datetime
from app.extensions import db


class Cliente(db.Model):
    __tablename__ = "cliente"

    id_cliente = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    telefone = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    endereco = db.Column(db.String(200), nullable=True)
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)
    pontos_acumulados = db.Column(db.Integer, default=0, nullable=False)

    compras = db.relationship("Compra", backref="cliente", lazy=True, cascade="all, delete-orphan")
    resgates = db.relationship("Resgate", backref="cliente", lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id_cliente": self.id_cliente,
            "nome": self.nome,
            "telefone": self.telefone,
            "email": self.email,
            "endereco": self.endereco,
            "data_cadastro": self.data_cadastro.isoformat() if self.data_cadastro else None,
            "pontos_acumulados": self.pontos_acumulados,
        }
