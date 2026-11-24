# Testes locais

## Suíte unitária isolada

```bash
cd backend
env -u DATABASE_URL -u POSTGRES_URL -u PGHOST -u PGDATABASE \
    -u PGUSER -u PGPASSWORD -u PGPASSFILE \
    FLASK_ENV=testing PYTHONDONTWRITEBYTECODE=1 \
    ../venv/bin/python -m unittest discover -s tests -v
```

## Controles de segurança

```bash
env -u DATABASE_URL -u PGHOST -u PGDATABASE -u PGUSER -u PGPASSWORD \
    PYTHONDONTWRITEBYTECODE=1 venv/bin/python test_security_audit.py
```

O segundo comando executa sete verificações funcionais. Não é um scanner SAST/DAST e não mede cobertura.

## Banco e migrações

Com PostgreSQL descartável configurado em `DATABASE_URL`:

```bash
venv/bin/flask --app run.py db upgrade
venv/bin/flask --app run.py db current
venv/bin/flask --app run.py db check
```

Critérios: head `0008_consolidar_schema`, apenas `usuario`, `produto`, `historico` e `alembic_version`, preservação dos dados fictícios e nenhuma operação Alembic pendente.

Relate separadamente testes descobertos/aprovados e cobertura. Não transforme taxa de aprovação em percentual de cobertura.
