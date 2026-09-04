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
