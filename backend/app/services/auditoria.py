import json
import logging
from flask import request, has_request_context
from flask_login import current_user
from app.extensions import db
from app.models.auditoria import Auditoria

logger = logging.getLogger(__name__)

# Campos e padrões sensíveis que NUNCA devem constar nos logs
CAMPOS_SENSIVEIS = {
    "senha", "senha_hash", "confirmar_senha", "password", "token",
    "secret", "secret_key", "cookie", "device_key", "iot_device_key"
}


def sanitizar_detalhes(detalhes):
    """Remove qualquer chave sensível recursivamente de dicionários ou strings."""
    if detalhes is None:
        return None
    if isinstance(detalhes, dict):
        limpo = {}
        for k, v in detalhes.items():
            if any(s in str(k).lower() for s in CAMPOS_SENSIVEIS):
                limpo[k] = "[REMOVIDO_POR_SEGURANCA]"
            elif isinstance(v, dict):
                limpo[k] = sanitizar_detalhes(v)
            elif isinstance(v, list):
                limpo[k] = [sanitizar_detalhes(item) if isinstance(item, dict) else item for item in v]
            else:
                limpo[k] = v
        return json.dumps(limpo, ensure_ascii=False)
    if isinstance(detalhes, (list, tuple)):
        return json.dumps(detalhes, ensure_ascii=False)
    return str(detalhes)


def registrar_auditoria(
    acao: str,
    entidade: str,
    entidade_id=None,
    detalhes=None,
    usuario_id: int | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> Auditoria | None:
    """Registra uma operação administrativa de forma segura e não bloqueante."""
    try:
        # Deriva o usuário responsável se não fornecido explicitamente
        if usuario_id is None and has_request_context():
            if current_user and current_user.is_authenticated and getattr(current_user, "is_vendedora", False):
                usuario_id = getattr(current_user, "id_usuario", None)

        # Captura metadados da requisição HTTP quando presente
        if ip is None and has_request_context():
            ip = request.headers.get("X-Forwarded-For", request.remote_addr)
            if ip and "," in ip:
                ip = ip.split(",")[0].strip()

        if user_agent is None and has_request_context():
            ua = request.user_agent.string if request.user_agent else ""
            user_agent = ua[:250] if ua else None

        registro = Auditoria(
            id_usuario=usuario_id,
            acao=str(acao).upper()[:50],
            entidade=str(entidade).lower()[:50],
            entidade_id=str(entidade_id)[:50] if entidade_id is not None else None,
            detalhes=sanitizar_detalhes(detalhes),
            ip=ip[:45] if ip else None,
            user_agent=user_agent,
        )
        db.session.add(registro)
        # Não forçamos commit imediatamente para participar da transação pai quando houver;
        # se for operação isolada, o chamador comita ou chamamos db.session.flush()
        db.session.flush()
        return registro
    except Exception as e:
        logger.warning(f"Falha ao registrar log de auditoria ({acao} - {entidade}): {e}")
        return None
