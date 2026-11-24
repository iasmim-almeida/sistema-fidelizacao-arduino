# API atual

Todas as respostas são JSON, exceto as rotas de página e redirecionamento.

## Autenticação

| Método | Rota | Uso |
|---|---|---|
| GET/POST | `/auth/setup` | Primeiro administrador; token obrigatório em produção |
| POST | `/auth/login` | Login administrativo |
| POST | `/auth/cliente/login` | Login do cliente |
| POST | `/auth/logout` | Encerra sessão; exige CSRF |
| GET | `/auth/me` | Sessão atual |
| POST | `/auth/alterar-senha` | Senha administrativa |

## Clientes

| Método | Rota |
|---|---|
| GET/POST | `/api/clientes/` |
| GET/PATCH/PUT | `/api/clientes/<id>` |
| GET/PATCH/PUT | `/api/clientes/me` |
| POST | `/api/clientes/me/alterar-senha` |
| POST | `/api/clientes/<id>/status` |
| POST | `/api/clientes/<id>/pontos/ajuste` |
| GET | `/api/clientes/<id>/extrato` |

## Compras

`GET /api/compras/` lista somente movimentos `COMPRA` permitidos ao perfil atual.

`POST /api/compras/` aceita:

```json
{"telefone":"11999999999"}
```

Ou `id_cliente` inteiro. Campos financeiros não fazem parte do contrato. A resposta nova usa `201`; uma repetição de `X-Idempotency-Key` usa `200`, `duplicada=true` e não adiciona ponto.

Autenticação:

- sessão administrativa + `X-CSRFToken`; ou
- dispositivo + `X-Device-Key`.

## Recompensas e resgates

| Método | Rota |
|---|---|
| GET/POST | `/api/recompensas/` |
| GET/PATCH | `/api/recompensas/<id>` |
| GET/POST | `/api/resgates/` |

Resgates usam custo, validade e estoque persistidos no servidor. Clientes não concluem resgates diretamente.

## Indicadores

- `GET /api/dashboard/estatisticas`
- `GET /api/relatorios/indicadores?dias=30`

Frequência de Recompra = compras do período / clientes ativos. Índice de Resgate = magnitude dos pontos de movimentos `RESGATE` / pontos de movimentos `COMPRA` no período. Rotatividade = clientes cadastrados sem movimento `COMPRA` nos últimos 30 dias / total de clientes cadastrados; ajustes não representam retorno à loja. Para períodos de avaliação inferiores a 30 dias, a API retorna `rotatividade_aplicavel=false` e `taxa_rotatividade=null`.

As rotas `/api/funcionarios/` e `/api/auditoria/` não existem.
