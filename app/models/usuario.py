from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db


class Usuario(UserMixin, db.Model):
    __tablename__ = "usuario"

    id_usuario = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    login = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    senha_hash = db.Column(db.String(255), nullable=False)
    nivel_acesso = db.Column(db.String(20), default="gestor", nullable=False)

    # Identificadores de Perfil / Role
    tipo = "vendedora"
    is_vendedora = True
    is_cliente = False

    def get_id(self):
        return f"u_{self.id_usuario}"

    def set_senha(self, senha: str) -> None:
        self.senha_hash = generate_password_hash(senha)

    def verificar_senha(self, senha: str) -> bool:
        if not self.senha_hash:
            return False
        return check_password_hash(self.senha_hash, senha)

    def to_dict(self):
        return {
            "id_usuario": self.id_usuario,
            "nome": self.nome,
            "login": self.login,
            "email": self.email,
            "nivel_acesso": self.nivel_acesso,
            "tipo": self.tipo,
        }
