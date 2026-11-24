import click
from flask import Flask
from app.extensions import db
from app.models.usuario import Usuario
from app.services.rbac import ROLE_VENDEDORA
from app.security.password import validar_complexidade_senha


def register_cli_commands(app: Flask):
    @app.cli.command("schema-status")
    def schema_status():
        """Confere revisão sem imprimir URI ou credenciais."""
        from alembic.script import ScriptDirectory
        from alembic.config import Config
        from app import MIGRATIONS_DIR
        config = Config()
        config.set_main_option("script_location", MIGRATIONS_DIR)
        expected = set(ScriptDirectory.from_config(config).get_heads())
        applied = set(db.session.execute(db.text("SELECT version_num FROM alembic_version")).scalars())
        click.echo(f"Esperada: {', '.join(sorted(expected))}; aplicada: {', '.join(sorted(applied))}")
        if applied != expected:
            raise click.ClickException("Revisão divergente")

    def _executar_criacao_vendedora(nome, login, email, senha, force):
        """Cria ou bootstraps de forma segura a conta da Vendedora (Admin) do IT Clube."""
        nome = str(nome).strip()
        login = str(login).strip().lower()
        email = str(email).strip().lower()

        if not nome or not login or not email:
            click.echo(click.style("Erro: Nome, login e e-mail são obrigatórios.", fg="red"))
            raise click.Abort()

        valida, msg = validar_complexidade_senha(senha)
        if not valida:
            click.echo(click.style(f"Erro na senha: {msg}", fg="red"))
            raise click.Abort()

        vendedora_existente = Usuario.query.filter(
            Usuario.nivel_acesso == "ADMIN",
            Usuario.ativo == True
        ).first()

        if vendedora_existente and not force:
            click.echo(click.style(
                f"Aviso: Já existe uma vendedora (admin) ativa cadastrada ({vendedora_existente.login}). "
                "Use a flag --force se deseja realmente registrar outra conta administradora.",
                fg="yellow"
            ))
            return

        usuario = Usuario.query.filter((Usuario.login == login) | (Usuario.email == email)).first()
        if usuario:
            usuario.nome = nome
            usuario.login = login
            usuario.email = email
            usuario.cargo = ROLE_VENDEDORA
            usuario.nivel_acesso = "ADMIN"
            usuario.ativo = True
            usuario.precisa_trocar_senha = False
            usuario.set_senha(senha)
            msg_final = f"Conta Vendedora (Admin) '{login}' atualizada com êxito!"
        else:
            usuario = Usuario(
                nome=nome,
                login=login,
                email=email,
                cargo=ROLE_VENDEDORA,
                nivel_acesso="ADMIN",
                ativo=True,
                precisa_trocar_senha=False
            )
            usuario.set_senha(senha)
            db.session.add(usuario)
            msg_final = f"Conta Vendedora (Admin) '{login}' criada com êxito!"

        db.session.commit()

        click.echo(click.style(msg_final, fg="green", bold=True))

    @app.cli.command("create-vendedora")
    @click.option("--nome", prompt="Nome completo", help="Nome da Vendedora (Admin)")
    @click.option("--login", prompt="Login de acesso", help="Login da Vendedora (Admin)")
    @click.option("--email", prompt="E-mail", help="E-mail corporativo da Vendedora (Admin)")
    @click.option(
        "--senha",
        prompt=True,
        hide_input=True,
        confirmation_prompt=True,
        help="Senha forte da Vendedora (Admin)"
    )
    @click.option(
        "--force",
        is_flag=True,
        default=False,
        help="Permite criar uma nova administradora mesmo se já existir uma cadastrada."
    )
    def create_vendedora_command(nome, login, email, senha, force):
        _executar_criacao_vendedora(nome, login, email, senha, force)

    @app.cli.command("create-owner")
    @click.option("--nome", prompt="Nome completo", help="Nome da Vendedora (Admin)")
    @click.option("--login", prompt="Login de acesso", help="Login da Vendedora (Admin)")
    @click.option("--email", prompt="E-mail", help="E-mail corporativo da Vendedora (Admin)")
    @click.option(
        "--senha",
        prompt=True,
        hide_input=True,
        confirmation_prompt=True,
        help="Senha forte da Vendedora (Admin)"
    )
    @click.option(
        "--force",
        is_flag=True,
        default=False,
        help="Permite criar uma nova administradora mesmo se já existir uma cadastrada."
    )
    def create_owner_command(nome, login, email, senha, force):
        """Alias compatível para create-vendedora."""
        _executar_criacao_vendedora(nome, login, email, senha, force)
