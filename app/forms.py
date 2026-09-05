import re
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError, Regexp
from app.models.cliente import Cliente


class CadastroClienteForm(FlaskForm):
    """
    Formulário seguro para auto-cadastro de clientes.
    Aplica validação estrita de entrada, formato e proteção CSRF nativa via Flask-WTF.
    """
    nome = StringField(
        "Nome Completo",
        validators=[
            DataRequired(message="O nome e obrigatorio."),
            Length(min=3, max=120, message="O nome deve ter entre 3 e 120 caracteres.")
        ]
    )

    telefone = StringField(
        "Telefone / WhatsApp",
        validators=[
            DataRequired(message="O telefone e obrigatorio."),
            Regexp(
                r"^\(?\d{2}\)?\s?9?\d{4}-?\d{4}$",
                message="Formato de telefone invalido. Digite com DDD (ex: 11999998888)."
            )
        ]
    )

    senha = PasswordField(
        "Senha de Acesso",
        validators=[
            DataRequired(message="A senha e obrigatoria."),
            # Mitigação VULN-02: Mínimo 8 caracteres e rejeição de senhas fracas
            Length(min=8, max=64, message="A senha deve possuir entre 8 e 64 caracteres."),
            Regexp(
                r"^(?=.*[A-Za-z])(?=.*\d).+$",
                message="A senha deve conter ao menos uma letra e um numero."
            )
        ]
    )

    confirmar_senha = PasswordField(
        "Confirmar Senha",
        validators=[
            DataRequired(message="A confirmacao de senha e obrigatoria."),
            EqualTo("senha", message="As senhas informadas nao conferem.")
        ]
    )

    submit = SubmitField("Criar Minha Conta")

    def validate_senha(self, field):
        """Impede o uso de senhas padrões conhecidas ou inseguras."""
        if field.data in ("1234", "12345678", "password", "senha123", "admin123"):
            raise ValidationError("Esta senha e muito comum e insegura. Escolha outra senha.")

    def validate_telefone(self, field):
        """Verifica duplicidade de telefone no banco de dados."""
        tel_limpo = re.sub(r"\D", "", field.data or "")
        if not tel_limpo:
            raise ValidationError("Telefone invalido.")
        cliente_existente = Cliente.query.filter(
            (Cliente.telefone == field.data) | (Cliente.telefone == tel_limpo)
        ).first()
        if cliente_existente:
            raise ValidationError("Este telefone ja esta cadastrado no sistema.")


SENHAS_COMUNS_BLACKLIST = {
    "1234", "123456", "12345678", "123456789", "password", "senha123",
    "admin123", "fideliza2026", "administrador", "admin@loja.com",
    "fideliza", "mudar123", "trocar123", "qwerty", "111111", "000000",
    "admin", "root", "master", "gestor"
}


def validar_politica_senha_admin(nova_senha: str) -> tuple[bool, str | None]:
    """
    Valida a política mínima de segurança de senha para administradores:
    - Mínimo de 8 e máximo de 128 caracteres;
    - Ao menos uma letra minúscula;
    - Ao menos uma letra maiúscula;
    - Ao menos um dígito numérico;
    - Ao menos um caractere especial (!@#$%...);
    - Não constar na blacklist de senhas fracas/comuns.
    """
    if not nova_senha or len(nova_senha) < 8:
        return False, "A nova senha deve possuir no minimo 8 caracteres."
    if len(nova_senha) > 128:
        return False, "A nova senha deve possuir no maximo 128 caracteres."
    if nova_senha.strip().lower() in SENHAS_COMUNS_BLACKLIST:
        return False, "Esta senha e muito comum e insegura. Escolha outra senha."
    if not re.search(r"[a-z]", nova_senha):
        return False, "A nova senha deve conter ao menos uma letra minuscula."
    if not re.search(r"[A-Z]", nova_senha):
        return False, "A nova senha deve conter ao menos uma letra maiuscula."
    if not re.search(r"\d", nova_senha):
        return False, "A nova senha deve conter ao menos um numero."
    if not re.search(r"[^A-Za-z0-9]", nova_senha):
        return False, "A nova senha deve conter ao menos um caractere especial (ex: !@#$%&*)."
    return True, None


class AlterarSenhaAdminForm(FlaskForm):
    """Formulário para alteração de senha de administradores/vendedoras."""
    senha_atual = PasswordField(
        "Senha Atual",
        validators=[DataRequired(message="A senha atual e obrigatoria.")]
    )
    nova_senha = PasswordField(
        "Nova Senha",
        validators=[
            DataRequired(message="A nova senha e obrigatoria."),
            Length(min=8, max=128, message="A nova senha deve possuir entre 8 e 128 caracteres."),
        ]
    )
    confirmar_nova_senha = PasswordField(
        "Confirmar Nova Senha",
        validators=[
            DataRequired(message="A confirmacao da nova senha e obrigatoria."),
            EqualTo("nova_senha", message="As senhas informadas nao conferem.")
        ]
    )
    submit = SubmitField("Salvar Nova Senha")

    def validate_nova_senha(self, field):
        valida, motivo = validar_politica_senha_admin(field.data)
        if not valida:
            raise ValidationError(motivo)

