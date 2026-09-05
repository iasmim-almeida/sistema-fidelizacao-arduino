from datetime import datetime, timezone
from app.extensions import db


def agora_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Auditoria(db.Model):
    __tablename__ = "auditoria"

    id_auditoria = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(
        db.Integer,
        db.ForeignKey("usuario.id_usuario", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    acao = db.Column(db.String(50), nullable=False, index=True)
    entidade = db.Column(db.String(50), nullable=False, index=True)
    entidade_id = db.Column(db.String(50), nullable=True, index=True)
    detalhes = db.Column(db.Text, nullable=True)
    ip = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    data_hora = db.Column(db.DateTime, nullable=False, default=agora_utc, index=True)

    usuario = db.relationship("Usuario", backref="auditorias")

    def to_dict(self):
        return {
            "id_auditoria": self.id_auditoria,
            "id_usuario": self.id_usuario,
            "usuario_nome": self.usuario.nome if self.usuario else "Sistema/Anônimo",
            "usuario_login": self.usuario.login if self.usuario else None,
            "acao": self.acao,
            "entidade": self.entidade,
            "entidade_id": self.entidade_id,
            "detalhes": self.detalhes,
            "ip": self.ip,
            "user_agent": self.user_agent,
            "data_hora": self.data_hora.isoformat() if self.data_hora else None,
        }
