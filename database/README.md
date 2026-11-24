# Banco de dados

PostgreSQL/Neon é o banco operacional oficial. SQLite é usado somente por testes unitários isolados.

## Modelo consolidado

- `usuario`: administradores e clientes, discriminados por `nivel_acesso`.
- `produto`: recompensas, benefícios, validade e estoque.
- `historico`: ledger transacional de compras, resgates e ajustes.

`Cliente` é alias de `Usuario`; `Compra`, `Resgate` e `MovimentacaoPontos` são aliases de `Historico`. Toda consulta especializada deve aplicar o discriminador correspondente.

## Migrações

- `0001` a `0004`: evolução do schema legado.
- `0005`: consolida tabelas em `usuario`, `produto`, `historico` e a antiga auditoria.
- `0006`: adapta schemas Neon preexistentes.
- `0007`: remove `historico.valor_compra`.
- `0008`: remove auditoria operacional e legado, corrige índices/constraints e adiciona idempotência.

As migrações antigas não devem ser reescritas porque podem ter sido aplicadas. `0007` e `0008` são destrutivas e dependem de backup para recuperação.

O arquivo `schema/schema_postgresql.sql` é referência do estado final. A cadeia Alembic é a fonte executável.

## Validação

```bash
flask --app run.py db upgrade
flask --app run.py db current
flask --app run.py db check
```

Execute somente contra banco descartável durante desenvolvimento. Para Neon, siga `docs/MIGRATION_NEON_PLAN.md` e obtenha aprovação individual.
