# Ambiente de desenvolvimento

## Pré-requisitos

- Python 3.12
- PostgreSQL 16 ou Docker Compose
- ambiente virtual Python

## Banco PostgreSQL descartável

```bash
docker compose -f compose.local.yml up -d
export DATABASE_URL='postgresql://itclube_demo:itclube_demo_local@127.0.0.1:5433/itclube_demo'
```

O compose usa `tmpfs`; não o utilize para dados que precisem persistir.

## Aplicação

```bash
python -m venv venv
venv/bin/pip install -r requirements.txt
export FLASK_ENV=development
export SECRET_KEY='segredo-local-forte'
export INITIAL_SETUP_TOKEN='token-local-de-setup'
export IOT_DEVICE_KEY='chave-local-com-32-ou-mais-caracteres'
venv/bin/flask --app run.py db upgrade
venv/bin/flask --app run.py run
```

## Testes unitários

Os testes usam SQLite em memória e devem remover variáveis externas:

```bash
cd backend
env -u DATABASE_URL -u PGHOST -u PGDATABASE -u PGUSER -u PGPASSWORD \
  FLASK_ENV=testing PYTHONDONTWRITEBYTECODE=1 \
  ../venv/bin/python -m unittest discover -s tests -v
```

## Migrações

Valide `upgrade`, preservação de dados fictícios e `db check` em PostgreSQL descartável. Nunca use a URL Neon operacional para desenvolvimento.

## Dados fictícios opcionais

O seed é bloqueado em produção e não contém senhas padrão. Use-o somente no banco descartável depois de definir `SEED_ADMIN_PASSWORD` e `SEED_CLIENT_PASSWORD` com valores locais fortes.

## Demonstração offline

Os assets web são locais. Para uma apresentação independente da internet, inicialize o PostgreSQL descartável, aplique as migrações e use apenas dados fictícios. Mantenha capturas ou vídeo como contingência para falha do hardware.
