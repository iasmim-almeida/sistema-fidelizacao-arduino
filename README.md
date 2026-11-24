# IT Clube

Sistema de fidelização de clientes integrado a um ESP8266 NodeMCU. O produto registra uma compra como exatamente um ponto, mantém o saldo e o extrato do cliente e permite resgates presenciais de recompensas.

O sistema não é um PDV financeiro: compras não possuem valor monetário, faturamento ou pontuação proporcional a valor.

## Escopo funcional

- Perfis: Administrador, apresentado como vendedora, e Cliente.
- Clientes: cadastro, perfil, primeiro acesso, ativação, saldo e extrato.
- Pontos: COMPRA, RESGATE, AJUSTE_POSITIVO e AJUSTE_NEGATIVO no histórico transacional.
- Recompensas: custo em pontos, tipo de benefício, validade, estoque e status.
- Relatórios: Frequência de Recompra, Taxa de Rotatividade e Índice de Resgate.
- IoT: `POST /api/compras/` autenticado e com suporte a idempotência.

Não existem módulos de gestão de equipes nem auditoria operacional. Logs técnicos permanecem separados do histórico transacional.

## Arquitetura

- Flask, Jinja2 e API JSON.
- Flask-Login, Flask-WTF/CSRF e Flask-Limiter.
- SQLAlchemy e Alembic/Flask-Migrate.
- PostgreSQL/Neon como banco operacional.
- SQLite apenas para testes unitários isolados.
- Gunicorn no Render.

O schema consolidado possui três tabelas de negócio: `usuario`, `produto` e `historico`.

## Execução local com PostgreSQL descartável

Requer Docker Compose com daemon ativo. O banco usa `tmpfs` e desaparece quando o container é removido.

```bash
docker compose -f compose.local.yml up -d
python -m venv venv
venv/bin/pip install -r requirements.txt
export FLASK_ENV=development
export DATABASE_URL='postgresql://itclube_demo:itclube_demo_local@127.0.0.1:5433/itclube_demo'
export SECRET_KEY='gere-uma-chave-local-forte'
export IOT_DEVICE_KEY='gere-uma-chave-local-com-32-ou-mais-caracteres'
export INITIAL_SETUP_TOKEN='gere-um-token-local-de-setup'
venv/bin/flask --app run.py db upgrade
venv/bin/flask --app run.py run
```

Não reutilize as credenciais locais em Render, Neon ou hardware real.

## Testes isolados

```bash
cd backend
env -u DATABASE_URL -u PGHOST -u PGDATABASE -u PGUSER -u PGPASSWORD \
  FLASK_ENV=testing PYTHONDONTWRITEBYTECODE=1 \
  ../venv/bin/python -m unittest discover -s tests -v
cd ..
venv/bin/python test_security_audit.py
```

As verificações de controles de segurança não substituem SAST, DAST, pentest ou medição de cobertura.

## Migrações

As migrações `0007` e `0008` removem dados aprovados como fora do escopo: valor monetário de compras e auditoria operacional. Elas não possuem downgrade capaz de recuperar os dados removidos. Consulte [MIGRATION_NEON_PLAN.md](docs/MIGRATION_NEON_PLAN.md) antes de qualquer execução persistente.

## Firmware

O repositório contém somente um protótipo de conectividade. O firmware acadêmico com teclado matricial e LCD não foi localizado. Consulte [arduino/README.md](arduino/README.md).

## Documentação

- [Arquitetura](docs/architecture/overview.md)
- [API](docs/api/endpoints.md)
- [Banco e migrações](database/README.md)
- [Execução e testes](docs/development/setup.md)
- [Segurança](SECURITY.md)
- [Plano de migração Neon](docs/MIGRATION_NEON_PLAN.md)
- [Deploy Render](docs/DEPLOY_RENDER.md)

Nenhum comando deste documento autoriza push, deploy ou migração em banco persistente.
