# Procedimento de deploy no Render

Este documento descreve uma operação futura. Push, deploy, rollback, reativação do serviço e migração Neon exigem aprovações individuais e não foram executados nesta fase.

## Variáveis obrigatórias

- `FLASK_ENV=production`
- `DATABASE_URL`: URL PostgreSQL/Neon
- `SECRET_KEY`: segredo forte gerado fora do repositório
- `INITIAL_SETUP_TOKEN`: token temporário forte para o primeiro administrador
- `IOT_DEVICE_KEY`: chave nova com pelo menos 32 caracteres
- `TIMEZONE=America/Sao_Paulo`
- `SESSION_COOKIE_SECURE=True`
- `REMEMBER_COOKIE_SECURE=True`

O valor de `INITIAL_SETUP_TOKEN` deve ser configurado manualmente no painel. Não o adicione a `render.yaml` nem ao Git.

## Gate anterior ao deploy

1. Confirmar a branch ligada ao auto-deploy do Render.
2. Obter aprovação para qualquer push/merge nessa branch.
3. Validar o commit candidato em PostgreSQL efêmero.
4. Executar a suíte completa e `flask db check`.
5. Executar e validar o backup descrito em `MIGRATION_NEON_PLAN.md`.
6. Confirmar que a chave IoT exposta foi substituída por uma nova.

## Build e inicialização

O manifesto atual instala dependências e executa `flask --app wsgi:app db upgrade` durante o build. Isso significa que deploy e migração não são operações independentes.

O comando de inicialização usa Gunicorn com três workers e duas threads. O rate limiting em memória não é compartilhado entre workers; essa limitação deve ser aceita explicitamente ou corrigida antes de uso público prolongado.

## Validação pós-deploy

- `/health` responde `200` e confirma banco conectado.
- Revisão Alembic é `0008_consolidar_schema`.
- Existem apenas as tabelas de negócio `usuario`, `produto` e `historico`.
- Setup sem token falha; setup com token funciona somente quando não existe ADMIN.
- Compra adiciona um ponto e repetição da chave idempotente não duplica saldo.
- Resgate respeita saldo, validade e estoque.
- Dashboard não conta administradores como clientes.

## Rollback

Não executar downgrade das migrações `0007` ou `0008`. Em perda de dados, restaurar o backup validado em instância separada e obter nova aprovação antes de redirecionar a aplicação.
