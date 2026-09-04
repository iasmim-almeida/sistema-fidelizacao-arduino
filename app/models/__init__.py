from app.extensions import login_manager
from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.models.compra import Compra
from app.models.resgate import Resgate


@login_manager.user_loader
def load_user(user_id: str):
    if not user_id:
        return None
    user_id_str = str(user_id)
    if user_id_str.startswith("u_"):
        try:
            return Usuario.query.get(int(user_id_str[2:]))
        except (ValueError, TypeError):
            return None
    elif user_id_str.startswith("c_"):
        try:
            return Cliente.query.get(int(user_id_str[2:]))
        except (ValueError, TypeError):
            return None

    # Mitigação VULN-08: Rejeita IDs sem prefixo para evitar colisão e escalação de privilégios
    return None


__all__ = ["Usuario", "Cliente", "Compra", "Resgate", "load_user"]
