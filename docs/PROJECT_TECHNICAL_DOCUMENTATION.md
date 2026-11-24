# Documentação técnica consolidada

## Objetivo

O IT Clube registra fidelidade para uma loja de variedades. Uma compra válida gera exatamente um ponto. O sistema não registra o valor monetário da compra nem calcula faturamento.

## Perfis

- Administrador/Vendedora: gerencia clientes, pontua, ajusta saldo, mantém recompensas, confirma resgates e consulta indicadores.
- Cliente: consulta saldo, extrato, recompensas e perfil.

Gestão de equipes e auditoria operacional foram removidas por requisito. O histórico de pontos permanece obrigatório.

## Componentes

- `backend/app/routes`: autenticação, clientes, compras, recompensas, resgates e páginas.
- `backend/app/models`: aliases funcionais sobre `Usuario`, `Produto` e `Historico`.
- `backend/app/services/pontos.py`: alteração de saldo e criação do ledger.
- `backend/app/services/rbac.py`: permissões do administrador e bloqueio de clientes.
- `frontend`: templates Jinja2 e assets locais.
- `database/migrations`: cadeia Alembic.
- `arduino`: protótipo ESP8266; firmware acadêmico completo ausente.

## Integridade

- Consultas de cliente filtram `nivel_acesso='CLIENTE'`.
- Consultas de compra filtram `tipo_movimentacao='COMPRA'`.
- Consultas de resgate filtram `tipo_movimentacao='RESGATE'`.
- Compras geram um ponto no mesmo commit que o histórico.
- Resgates validam produto e cliente com locks e updates condicionais.
- Idempotência de compra usa `historico.chave_idempotencia`.

## Indicadores

Para um período configurável, com 30 dias na interface:

- Frequência de Recompra: compras / clientes ativos.
- Taxa de Rotatividade: clientes cadastrados sem compra há mais de 30 dias / total de clientes cadastrados × 100.
- Índice de Resgate: pontos resgatados / pontos emitidos × 100.

Divisão por zero retorna `0.0`. Resgates, ajustes e administradores não são contabilizados como compras ou clientes.

O texto acadêmico também menciona a “última movimentação” do cliente. Para não tratar ajustes administrativos como retorno à loja, a implementação usa exclusivamente movimentos `COMPRA` como evidência de visita. A Taxa de Rotatividade é marcada como não aplicável quando o período avaliado tem menos de 30 dias.

## Produção

`create_app('production')` exige PostgreSQL, `SECRET_KEY` forte e `IOT_DEVICE_KEY` com pelo menos 32 caracteres. O primeiro setup exige `INITIAL_SETUP_TOKEN`. Render executa `db upgrade` no build, portanto qualquer publicação depende de backup e aprovação individual.

## Limitações verificadas

- A monografia `TCC_final.docx` não estava disponível no workspace durante a consolidação.
- PostgreSQL local não estava disponível na estação: Docker estava instalado, mas sem daemon; `psql`/`initdb` não estavam instalados.
- A cadeia foi validada em SQLite descartável como verificação preliminar. PostgreSQL permanece obrigatório no CI e antes do deploy.
- O firmware com teclado e LCD não existe nas branches ou no histórico acessível.

Consulte os documentos específicos de arquitetura, API, testes, segurança e migração para os procedimentos atuais.
