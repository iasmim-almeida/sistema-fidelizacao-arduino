from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db


class Cliente(UserMixin, db.Model):
    __tablename__ = "cliente"

    id_cliente = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    telefone = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    endereco = db.Column(db.String(200), nullable=True)
    senha_hash = db.Column(db.String(255), nullable=True)
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)
    pontos_acumulados = db.Column(db.Integer, default=0, nullable=False)

    # Identificadores de Perfil / Role
    tipo = "cliente"
    is_vendedora = False
    is_cliente = True

    compras = db.relationship("Compra", backref="cliente", lazy=True, cascade="all, delete-orphan")
    resgates = db.relationship("Resgate", backref="cliente", lazy=True, cascade="all, delete-orphan")

    def get_id(self):
        return f"c_{self.id_cliente}"

    def set_senha(self, senha: str) -> None:
        if not senha:
            raise ValueError("A senha nao pode ser vazia.")
        self.senha_hash = generate_password_hash(senha)

    def verificar_senha(self, senha: str) -> bool:
        # Mitigação VULN-02: Remove backdoor de senha padrão '1234'
        if not self.senha_hash or not senha:
            return False
        return check_password_hash(self.senha_hash, senha)

    def to_dict(self):
        return {
            "id_cliente": self.id_cliente,
            "nome": self.nome,
            "telefone": self.telefone,
            "email": self.email,
            "endereco": self.endereco,
            "data_cadastro": self.data_cadastro.isoformat() if self.data_cadastro else None,
            "pontos_acumulados": self.pontos_acumulados,
            "tipo": self.tipo,
        }
