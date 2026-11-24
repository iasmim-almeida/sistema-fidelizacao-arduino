# Plano de migração PostgreSQL/Neon

Este documento é um procedimento futuro. Ele não autoriza nem executa alterações no Neon.

## Impacto

- `0007` remove `historico.valor_compra` e os valores não podem ser recuperados por downgrade.
- `0008` remove `auditoria` e `auditoria_legado`, adiciona constraints/índices e `historico.chave_idempotencia`.
- `usuario`, `produto`, `historico`, saldos e movimentos transacionais devem ser preservados.

## Pré-validação em PostgreSQL efêmero

1. Restaurar uma cópia sanitizada e sem dados pessoais.
2. Registrar a revisão Alembic e contagens por tabela/tipo.
3. Validar produtos contra as novas constraints de custo, tipo, status e estoque.
4. Executar `flask db upgrade`.
5. Confirmar `0008_consolidar_schema` e executar `flask db check`.
6. Comparar contagens e somas de saldo antes/depois.
7. Testar compra idempotente e duas tentativas concorrentes de resgate.
8. Executar a suíte completa.

## Backup antes da janela aprovada

1. Gerar backup lógico completo do Neon com ferramenta compatível com a versão PostgreSQL.
2. Gerar export separado de `historico.valor_compra`, `auditoria` e `auditoria_legado` com timestamp e checksum.
3. Armazenar o backup fora do repositório e validar restauração em banco efêmero.
4. Registrar contagens de `usuario`, `produto`, `historico` e totais por tipo de movimento.

## Execução futura

1. Obter aprovação individual para backup, deploy e migração.
2. Suspender escrita ou definir janela de manutenção.
3. Aplicar uma única vez a revisão validada.
4. Verificar health check, schema, contagens, saldo, compra e resgate.
5. Não usar `downgrade` de `0007`/`0008` como rollback.

## Rollback

Em falha destrutiva, interromper escrita e restaurar o backup validado em uma instância separada. A decisão de apontar a aplicação para a restauração é uma operação de produção e exige nova aprovação.
