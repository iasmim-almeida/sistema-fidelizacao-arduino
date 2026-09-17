from datetime import date, datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import current_app, has_app_context
from sqlalchemy.orm import synonym
import uuid

from app.extensions import db


def agora_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def data_local_atual():
    timezone_name = current_app.config.get("TIMEZONE", "America/Sao_Paulo") if has_app_context() else "America/Sao_Paulo"
    try:
        return datetime.now(ZoneInfo(timezone_name)).date()
    except ZoneInfoNotFoundError:
        return date.today()


TIPOS_RECOMPENSA = ("produto_fisico", "desconto_percentual", "desconto_valor_fixo")
STATUS_RECOMPENSA = ("ativa", "pausada")


class Produto(db.Model):
    __tablename__ = "produto"

    id_produto = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey("usuario.id_usuario", ondelete="SET NULL"), nullable=True, index=True)
    nome_cupom = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.String(255), nullable=True)
    codigo = db.Column(db.String(50), nullable=False, unique=True, default=lambda: f"PROD-{uuid.uuid4().hex[:16].upper()}")
    validade = db.Column(db.Date, nullable=False, index=True)
    custo_pontos = db.Column(db.Integer, nullable=False)
    tipo = db.Column(db.String(30), nullable=False, default="produto_fisico")
    valor_beneficio = db.Column(db.Numeric(10, 2), nullable=True)
    quantidade_total = db.Column(db.Integer, nullable=True)
    quantidade_disponivel = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(10), nullable=False, default="ativa", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=agora_utc)
    updated_at = db.Column(db.DateTime, nullable=False, default=agora_utc, onupdate=agora_utc)

    id_recompensa = synonym("id_produto")
    nome = synonym("nome_cupom")

    @property
    def esta_expirada(self):
        return self.validade < data_local_atual()

    @property
    def esta_esgotada(self):
        return self.quantidade_disponivel is not None and self.quantidade_disponivel <= 0

    @property
    def estado(self):
        if self.status == "pausada":
            return "pausada"
        if self.esta_expirada:
            return "expirada"
        if self.esta_esgotada:
            return "esgotada"
        return "disponivel"

    def pode_ser_resgatada(self, saldo=None):
        return self.estado == "disponivel" and (saldo is None or saldo >= self.custo_pontos)

    def motivo_indisponibilidade(self, saldo=None):
        mensagens = {"pausada": "Temporariamente indisponível", "expirada": "Expirada", "esgotada": "Esgotada"}
        if self.estado != "disponivel":
            return mensagens[self.estado]
        if saldo is not None and saldo < self.custo_pontos:
            return "Pontos insuficientes"
        return None

    @property
    def beneficio_formatado(self):
        if self.tipo == "produto_fisico":
            return "Produto físico"
        valor = Decimal(self.valor_beneficio or 0)
        if self.tipo == "desconto_percentual":
            return f"{format(valor.normalize(), 'f')}% de desconto"
        return f"R$ {valor:.2f}".replace(".", ",") + " de desconto"

    def to_dict(self, saldo_cliente=None, incluir_proprietario=False):
        dados = {
            "id_recompensa": self.id_produto,
            "id_produto": self.id_produto,
            "nome": self.nome_cupom,
            "nome_cupom": self.nome_cupom,
            "descricao": self.descricao,
            "codigo": self.codigo,
            "custo_pontos": self.custo_pontos,
            "tipo": self.tipo,
            "valor_beneficio": str(self.valor_beneficio) if self.valor_beneficio is not None else None,
            "beneficio_formatado": self.beneficio_formatado,
            "validade": self.validade.isoformat(),
            "quantidade_total": self.quantidade_total,
            "quantidade_disponivel": self.quantidade_disponivel,
            "status": self.status,
            "estado": self.estado,
            "pode_resgatar": self.pode_ser_resgatada(saldo_cliente),
            "motivo_indisponibilidade": self.motivo_indisponibilidade(saldo_cliente),
            "pontos_faltantes": max(0, self.custo_pontos - saldo_cliente) if saldo_cliente is not None else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if incluir_proprietario:
            dados["id_usuario"] = self.id_usuario
        return dados


Recompensa = Produto
