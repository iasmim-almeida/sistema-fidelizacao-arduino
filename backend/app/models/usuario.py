from datetime import datetime, timezone
import uuid
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import synonym

from app.extensions import db


def agora_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def login_padrao(context):
    valores = context.get_current_parameters()
    login = valores.get("login")
    if login:
        return login
    telefone = valores.get("telefone")
    return telefone or f"usuario_{uuid.uuid4().hex}"


class Usuario(UserMixin, db.Model):
    __tablename__ = "usuario"

    id_usuario = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    telefone = db.Column(db.String(20), unique=True, nullable=True)
    email = db.Column(db.String(100), unique=True, nullable=True)
    endereco = db.Column(db.String(255), nullable=True)
    data_cadastro = db.Column(db.DateTime, nullable=False, default=agora_utc)
    pontos_acumulados = db.Column(db.Integer, nullable=False, default=0)
    login = db.Column(db.String(50), unique=True, nullable=False, default=login_padrao)
    senha_hash = db.Column(db.String(255), nullable=False, default="!senha_nao_configurada!")
    nivel_acesso = db.Column(db.String(20), default="CLIENTE", nullable=False)

    # Campos do modelo de funcionários
    cargo = db.Column(db.String(30), default="proprietario", nullable=False)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    ultimo_login = db.Column(db.DateTime, nullable=True)
    precisa_trocar_senha = db.Column(db.Boolean, default=False, nullable=False)

    id_cliente = synonym("id_usuario")

    def __init__(self, **kwargs):
        if "nivel_acesso" not in kwargs:
            kwargs["nivel_acesso"] = "CLIENTE" if kwargs.get("telefone") else "ADMIN"
        super().__init__(**kwargs)

    @property
    def is_active(self):
        """Flask-Login: contas inativas não conseguem autenticar nem manter sessão."""
        return bool(self.ativo)

    @property
    def is_proprietario(self) -> bool:
        from app.services.rbac import ROLE_PROPRIETARIO, normalizar_cargo
        return normalizar_cargo(self.cargo or self.nivel_acesso) == ROLE_PROPRIETARIO

    @property
    def is_gerente(self) -> bool:
        from app.services.rbac import ROLE_GERENTE, normalizar_cargo
        return normalizar_cargo(self.cargo or self.nivel_acesso) == ROLE_GERENTE

    @property
    def is_vendedor(self) -> bool:
        from app.services.rbac import ROLE_VENDEDOR, normalizar_cargo
        return normalizar_cargo(self.cargo or self.nivel_acesso) == ROLE_VENDEDOR

    def tem_permissao(self, permissao: str) -> bool:
        from app.services.rbac import usuario_tem_permissao
        return usuario_tem_permissao(self, permissao)

    def get_id(self):
        return f"u_{self.id_usuario}"

    @property
    def tipo(self):
        return "cliente" if self.nivel_acesso == "CLIENTE" else "vendedora"

    @property
    def is_cliente(self):
        return self.nivel_acesso == "CLIENTE"

    @property
    def is_vendedora(self):
        if self.nivel_acesso == "CLIENTE":
            return False
        return self.nivel_acesso == "ADMIN" or bool(self.cargo)

    def set_senha(self, senha: str) -> None:
        if not senha:
            raise ValueError("A senha não pode ser vazia.")
        self.senha_hash = generate_password_hash(senha)

    def verificar_senha(self, senha: str) -> bool:
        if not self.senha_hash or not senha:
            return False
        return check_password_hash(self.senha_hash, senha)

    check_senha = verificar_senha

    def to_dict(self):
        from app.services.rbac import normalizar_cargo
        cargo_norm = normalizar_cargo(self.cargo or self.nivel_acesso)
        return {
            "id_usuario": self.id_usuario,
            "id_cliente": self.id_usuario if self.is_cliente else None,
            "nome": self.nome,
            "telefone": self.telefone,
            "endereco": self.endereco,
            "pontos_acumulados": self.pontos_acumulados,
            "login": self.login,
            "email": self.email,
            "nivel_acesso": self.nivel_acesso,
            "cargo": cargo_norm,
            "ativo": self.ativo,
            "data_cadastro": self.data_cadastro.isoformat() if self.data_cadastro else None,
            "ultimo_login": self.ultimo_login.isoformat() if self.ultimo_login else None,
            "precisa_trocar_senha": self.precisa_trocar_senha,
            "tipo": self.tipo,
        }
