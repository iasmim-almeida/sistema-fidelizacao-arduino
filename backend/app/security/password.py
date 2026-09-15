import re

SENHAS_COMUNS_BLACKLIST = {
    "1234", "123456", "12345678", "123456789", "password", "senha123",
    "admin123", "fideliza2026", "administrador", "admin@loja.com",
    "fideliza", "mudar123", "trocar123", "qwerty", "111111", "000000",
    "admin", "root", "master", "gestor", "itclube", "itclube2026"
}


def validar_politica_senha_cliente(senha: str) -> tuple[bool, str | None]:
    """Valida requisitos de senha para cliente final (min 8 chars, letra + número)."""
    if not senha or len(senha) < 8:
        return False, "A senha deve conter no mínimo 8 caracteres."
    if len(senha) > 64:
        return False, "A senha deve conter no máximo 64 caracteres."
    if senha.strip().lower() in SENHAS_COMUNS_BLACKLIST:
        return False, "Esta senha é muito comum e insegura. Escolha outra senha."
    if not re.search(r"^(?=.*[A-Za-z])(?=.*\d).+$", senha):
        return False, "A senha deve conter ao menos uma letra e um número."
    return True, None


def validar_politica_senha_admin(senha: str) -> tuple[bool, str | None]:
    """Valida requisitos de senha para administração."""
    if not senha or len(senha) < 8:
        return False, "A nova senha deve possuir no mínimo 8 caracteres."
    if len(senha) > 128:
        return False, "A nova senha deve possuir no máximo 128 caracteres."
    if senha.strip().lower() in SENHAS_COMUNS_BLACKLIST:
        return False, "Esta senha é muito comum e insegura. Escolha outra senha."
    if not re.search(r"[a-z]", senha):
        return False, "A nova senha deve conter ao menos uma letra minúscula."
    if not re.search(r"[A-Z]", senha):
        return False, "A nova senha deve conter ao menos uma letra maiúscula."
    if not re.search(r"\d", senha):
        return False, "A nova senha deve conter ao menos um número."
    if not re.search(r"[^A-Za-z0-9]", senha):
        return False, "A nova senha deve conter ao menos um caractere especial (ex: !@#$%&*)."
    return True, None
