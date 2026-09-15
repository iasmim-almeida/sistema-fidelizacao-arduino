from app.extensions import db, login_manager
from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.models.compra import Compra
from app.models.recompensa import Recompensa
from app.models.resgate import Resgate
from app.models.movimentacao_pontos import MovimentacaoPontos
from app.models.auditoria import Auditoria


@login_manager.user_loader
def load_user(user_id: str):
    if not user_id:
        return None
    user_id_str = str(user_id)
    if user_id_str.startswith("u_"):
        try:
            user = db.session.get(Usuario, int(user_id_str[2:]))
            if user and not user.ativo:
                return None
            return user
        except (ValueError, TypeError):
            return None
    elif user_id_str.startswith("c_"):
        try:
            client = db.session.get(Cliente, int(user_id_str[2:]))
            if client and not client.ativo:
                return None
            return client
        except (ValueError, TypeError):
            return None

    # Mitigação VULN-08: Rejeita IDs sem prefixo para evitar colisão e escalação de privilégios
    return None


__all__ = [
    "Usuario",
    "Cliente",
    "Compra",
    "Recompensa",
    "Resgate",
    "MovimentacaoPontos",
    "Auditoria",
    "load_user",
]
