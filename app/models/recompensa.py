from datetime import date, datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import current_app, has_app_context

from app.extensions import db


def agora_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


TIPOS_RECOMPENSA = (
    "produto_fisico",
    "desconto_percentual",
    "desconto_valor_fixo",
)
STATUS_RECOMPENSA = ("ativa", "pausada")


def data_local_atual() -> date:
    """Retorna a data de negócio no timezone configurado pela aplicação."""
    timezone_name = current_app.config.get("TIMEZONE", "America/Sao_Paulo") if has_app_context() else "America/Sao_Paulo"
    try:
        return datetime.now(ZoneInfo(timezone_name)).date()
    except ZoneInfoNotFoundError:
        return date.today()


class Recompensa(db.Model):
    __tablename__ = "recompensa"

    id_recompensa = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(
        db.Integer,
        db.ForeignKey("usuario.id_usuario", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    nome = db.Column(db.String(120), nullable=False)
    custo_pontos = db.Column(db.Integer, nullable=False)
    tipo = db.Column(db.String(30), nullable=False)
    valor_beneficio = db.Column(db.Numeric(10, 2), nullable=True)
    validade = db.Column(db.Date, nullable=False, index=True)
    quantidade_total = db.Column(db.Integer, nullable=False)
    quantidade_disponivel = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(10), nullable=False, default="ativa", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=agora_utc)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=agora_utc,
        onupdate=agora_utc,
    )

    __table_args__ = (
        db.CheckConstraint("custo_pontos > 0", name="ck_recompensa_custo_positivo"),
        db.CheckConstraint(
            "tipo IN ('produto_fisico', 'desconto_percentual', 'desconto_valor_fixo')",
            name="ck_recompensa_tipo",
        ),
        db.CheckConstraint(
            "status IN ('ativa', 'pausada')",
            name="ck_recompensa_status",
        ),
        db.CheckConstraint(
            "quantidade_total >= 0",
            name="ck_recompensa_quantidade_total",
        ),
        db.CheckConstraint(
            "quantidade_disponivel >= 0 AND quantidade_disponivel <= quantidade_total",
            name="ck_recompensa_quantidade_disponivel",
        ),
        db.CheckConstraint(
            "(tipo = 'produto_fisico' AND valor_beneficio IS NULL) OR "
            "(tipo = 'desconto_percentual' AND valor_beneficio > 0 AND valor_beneficio <= 100) OR "
            "(tipo = 'desconto_valor_fixo' AND valor_beneficio > 0)",
            name="ck_recompensa_valor_beneficio",
        ),
    )

    resgates = db.relationship("Resgate", back_populates="recompensa", lazy=True)

    @property
    def esta_expirada(self) -> bool:
        # A recompensa continua válida durante toda a data informada.
        return self.validade < data_local_atual()

    @property
    def esta_esgotada(self) -> bool:
        return self.quantidade_disponivel <= 0

    @property
    def estado(self) -> str:
        if self.status == "pausada":
            return "pausada"
        if self.esta_expirada:
            return "expirada"
        if self.esta_esgotada:
            return "esgotada"
        return "disponivel"

    def pode_ser_resgatada(self, saldo: int | None = None) -> bool:
        if self.estado != "disponivel":
            return False
        return saldo is None or saldo >= self.custo_pontos

    def motivo_indisponibilidade(self, saldo: int | None = None) -> str | None:
        mensagens = {
            "pausada": "Temporariamente indisponível",
            "expirada": "Expirada",
            "esgotada": "Esgotada",
        }
        if self.estado != "disponivel":
            return mensagens[self.estado]
        if saldo is not None and saldo < self.custo_pontos:
            return "Pontos insuficientes"
        return None

    @property
    def beneficio_formatado(self) -> str:
        if self.tipo == "produto_fisico":
            return "Produto físico"
        valor = Decimal(self.valor_beneficio or 0)
        if self.tipo == "desconto_percentual":
            numero = format(valor.normalize(), "f")
            return f"{numero}% de desconto"
        return f"R$ {valor:.2f}".replace(".", ",") + " de desconto"

    def to_dict(self, saldo_cliente: int | None = None, incluir_proprietario: bool = False):
        dados = {
            "id_recompensa": self.id_recompensa,
            "nome": self.nome,
            "custo_pontos": self.custo_pontos,
            "tipo": self.tipo,
            "valor_beneficio": (
                str(self.valor_beneficio) if self.valor_beneficio is not None else None
            ),
            "beneficio_formatado": self.beneficio_formatado,
            "validade": self.validade.isoformat(),
            "quantidade_total": self.quantidade_total,
            "quantidade_disponivel": self.quantidade_disponivel,
            "status": self.status,
            "estado": self.estado,
            "pode_resgatar": self.pode_ser_resgatada(saldo_cliente),
            "motivo_indisponibilidade": self.motivo_indisponibilidade(saldo_cliente),
            "pontos_faltantes": (
                max(0, self.custo_pontos - saldo_cliente)
                if saldo_cliente is not None
                else None
            ),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if incluir_proprietario:
            dados["id_usuario"] = self.id_usuario
        return dados
