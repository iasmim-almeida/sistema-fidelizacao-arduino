import re


def limpar_telefone(telefone: str | None) -> str:
    """Extrai apenas os dígitos de uma string de telefone."""
    if not telefone:
        return ""
    return re.sub(r"\D", "", str(telefone).strip())


def validar_email_formato(email: str | None) -> bool:
    """Valida formato básico de e-mail."""
    if not email:
        return False
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()))
