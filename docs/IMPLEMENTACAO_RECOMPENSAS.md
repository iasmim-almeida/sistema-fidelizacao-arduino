# Implementação do Sistema de Recompensas

## Objetivo

Substituir os prêmios hardcoded e o resgate baseado em dados enviados pelo navegador por recompensas reais, persistidas, administráveis e resgatadas de forma transacional.

## Diagnóstico inicial

O projeto já utilizava Flask Application Factory, Blueprints, SQLAlchemy, Flask-Login, Flask-WTF, Flask-Limiter, Jinja2, Bootstrap e dois perfis. `Cliente.pontos_acumulados` mantinha o saldo; `Compra` creditava e `Resgate` debitava.

Foram encontrados dois catálogos hardcoded: `PREMIOS` no portal do cliente e dois radios na tela da vendedora. `POST /api/resgates/` confiava em `pontos_utilizados` e `descricao_recompensa` do frontend. Um voucher `Math.random()` era exibido sem persistência ou validação. Flask-Migrate estava configurado, mas não existia diretório de migrations. `run.py` executava `db.create_all()` durante import, inclusive em comandos Flask. `seed.py` executava `db.drop_all()`.

O Git não possuía alterações rastreadas no início. O arquivo não rastreado `repomix-output.md`, pertencente ao usuário, foi preservado.

## Arquitetura encontrada

- backend Flask monolítico modular;
- Application Factory em `app/__init__.py`;
- rotas web no Blueprint `main`;
- APIs em Blueprints de auth, clientes, compras e resgates;
- models simples por arquivo;
- frontend SSR com scripts embutidos nas páginas;
- SQLite no desenvolvimento e URL configurável para PostgreSQL;
- firmware ESP8266 separado, chamando somente a API de compras.

## Decisões arquiteturais

- manter a arquitetura Flask/Jinja/Bootstrap, sem introduzir Node;
- criar `Recompensa` com tipo e status controlados por strings validadas e constraints de banco;
- tornar validade obrigatória e inclusiva durante toda a data no timezone configurado;
- derivar `disponivel`, `pausada`, `expirada` e `esgotada`, evitando redundância;
- manter total e disponível para separar estoque cadastrado de consumo histórico;
- ao editar o total, preservar unidades já consumidas;
- manter snapshots do resgate e adicionar FK anulável para compatibilidade histórica;
- ocultar expiradas do catálogo, mas mantê-las na administração;
- mostrar pausadas, esgotadas e opções com pontos insuficientes como bloqueadas;
- usar 404 em recurso administrativo de outra gestora para reduzir enumeração;
- manter catálogo global para clientes porque o banco não modela loja/tenant;
- remover o voucher aleatório e usar o ID persistido do resgate como comprovante;
- usar locks pessimistas no PostgreSQL e updates condicionais atômicos em ambos os bancos.

## Models criados/modificados

### `Recompensa`

Campos: proprietário, nome, custo, tipo, valor do benefício, validade, quantidade total/disponível, status e timestamps. Constraints impedem custo inválido, estoque negativo, status/tipo desconhecido e benefício incompatível.

Helpers centralizam data local, expiração, esgotamento, estado, resgatabilidade, motivo de bloqueio, benefício formatado e serialização.

### `Usuario`

Recebeu relacionamento com recompensas.

### `Resgate`

Recebeu `id_recompensa` e relacionamento. A FK aceita nulo e usa `ON DELETE SET NULL`; descrição e pontos continuam obrigatórios como snapshots.

## Banco de dados

Criada a tabela `recompensa`, três índices (`id_usuario`, `status`, `validade`) e índice da recompensa em `resgate`. O schema PostgreSQL de referência foi atualizado. `psycopg2-binary` passou a fazer parte das dependências.

## Migration criada

- `0001_schema_legado`: baseline que só cria uma tabela antiga se ela não existir;
- `0002_recompensas`: tabela, constraints, índices e FK anulável no resgate.

A migration foi validada em SQLite vazio e em schema legado sintético contendo resgate histórico. O registro permaneceu intacto e recebeu `id_recompensa = NULL`. `run.py` deixou de chamar `create_all()` para não competir com Alembic. O seed marca o head depois de seu reset explícito.

## Endpoints

| Método | Endpoint | Regra |
|---|---|---|
| GET | `/api/recompensas/` | gestora vê apenas as próprias; cliente vê catálogo não expirado |
| POST | `/api/recompensas/` | somente gestora; proprietário vem da sessão |
| GET | `/api/recompensas/<id>` | controle de perfil e propriedade |
| PATCH | `/api/recompensas/<id>` | somente proprietária; campos explícitos |
| POST | `/api/resgates/` | recebe ID da recompensa e, na administração, ID do cliente |

## Frontend da gestora

A rota `/gestao-recompensas` e um item no menu dão acesso a listagem, formulário responsivo, criação, edição, pausa e reativação. A interface apresenta benefício, custo, validade, total/disponível e estado derivado. Possui carregamento, vazio, erro, sucesso, cancelamento e trava de duplo envio.

Dados vindos da API são inseridos com `textContent`/elementos DOM, sem interpolação em `innerHTML`.

## Frontend do cliente

O array `PREMIOS` foi removido. O catálogo usa `/api/recompensas/`, mostra saldo, tipo, benefício, custo, validade e estoque. Saldo insuficiente não oculta o item: aplica aparência bloqueada, botão desabilitado, “Pontos insuficientes” e diferença de pontos. O botão fica travado durante a chamada.

Expiradas são ocultas; pausadas e esgotadas permanecem visíveis e bloqueadas.

## Alterações no resgate

O endpoint não aceita custo ou descrição como fonte da verdade. Payloads antigos com esses campos são rejeitados. O backend:

1. deriva ou valida o cliente pelo perfil;
2. carrega recompensa e cliente com `FOR UPDATE`;
3. valida propriedade administrativa, status, validade, estoque e saldo;
4. faz updates condicionais de estoque e saldo;
5. registra FK e snapshots;
6. faz flush/refresh ainda dentro da transação;
7. executa um único commit.

A tela de entrega administrativa carrega clientes e recompensas reais, bloqueia opções incompatíveis com saldo/estado e envia somente IDs.

## Segurança aplicada

- autenticação e RBAC;
- propriedade derivada da sessão;
- filtro anti-IDOR/BOLA;
- allowlist de campos e rejeição de mass assignment;
- validação rigorosa de nome, inteiros, decimal, tipo, status e data;
- Numeric/Decimal para benefícios financeiros;
- custo e descrição exclusivamente do banco;
- CSRF em mutações de recompensas e resgates;
- DOM seguro contra XSS armazenada nas telas novas;
- rollback em qualquer falha;
- updates condicionais contra saldo/estoque negativos;
- `FOR UPDATE` para PostgreSQL;
- respostas genéricas sem stack trace.

## Testes adicionados

`tests/test_recompensas.py` cobre 14 cenários:

- anônimo e perfil cliente na administração;
- criação válida e proprietário da sessão;
- nome, custo, tipo, benefício, estoque e validade inválidos;
- IDOR entre gestoras;
- pausa, reativação e preservação do consumo;
- recompensa visível com saldo insuficiente;
- resgate completo;
- manipulação de custo/descrição/cliente;
- pausa, expiração, esgotamento e falta de pontos;
- última unidade;
- rollback simulado;
- entrega administrativa restrita à proprietária;
- histórico legado sem FK;
- CSRF ausente e válido.

## Testes executados

| Comando | Resultado |
|---|---|
| `python3 -m compileall -q app run.py seed.py test_security_audit.py` (baseline) | passou |
| `DATABASE_URL=<sqlite-temporario> python3 test_security_audit.py` (baseline) | 7/7 passou |
| `python3 -m unittest discover -s tests -v` | 14/14 passou |
| `DATABASE_URL=<sqlite-temporario> python3 test_security_audit.py` (regressão) | 7/7 passou |
| smoke Flask test client: login gestora/cliente, criação, catálogo, resgate, páginas e compra IoT | passou ponta a ponta |
| `flask --app run.py db upgrade` em banco vazio | passou até `0002_recompensas` |
| `flask --app run.py db upgrade` em schema legado sintético | passou e preservou histórico |
| ciclo `upgrade -> downgrade 0001 -> upgrade` em SQLite temporário | passou |
| `flask --app run.py db check` | nenhuma operação pendente |
| `python3 -m compileall -q app migrations tests run.py seed.py test_security_audit.py` | passou |

Todos os bancos usados em seed/testes foram arquivos temporários em `/tmp`; nenhum banco corrente do projeto foi apagado.

## Problemas encontrados

- ausência de migrations apesar de Flask-Migrate configurado;
- `create_all()` durante import do entrypoint;
- seed destrutivo sem aviso explícito no terminal;
- catálogo e entrega duplicados/hardcoded;
- custo e descrição controlados pelo cliente;
- voucher apenas aleatório no navegador;
- estoque/validade/status inexistentes;
- construção HTML insegura para dados administrativos nas telas afetadas.

## Correções realizadas durante a revisão

- removido `create_all()` do entrypoint após a primeira validação detectar conflito com Alembic;
- seed passou a avisar destrutividade e marcar o head da migration;
- refresh dos registros movido para antes do commit, evitando resposta de falha depois de commit bem-sucedido;
- CSRF ativado para os dois Blueprints mutáveis novos/alterados e tokens adicionados aos fetches;
- data mínima do formulário calculada no timezone local do navegador, sem conversão UTC;
- renderização de recompensa/histórico refeita com APIs DOM seguras;
- senha fraca de demonstração substituída e chave IoT padrão removida da configuração de produção;
- responsividade do sidebar e logout administrativo corrigidos;
- schema PostgreSQL, models e migrations alinhados e verificados por `db check`.

## Limitações

- ausência de entidade Loja e associação Cliente-Loja;
- locking do SQLite é menos granular que o PostgreSQL;
- não há emissão/consumo de voucher único;
- integração concorrente real com PostgreSQL não foi executada porque não havia servidor externo disponível;
- APIs legadas de clientes/compras permanecem com a política CSRF anterior.

## Próximos passos

- introduzir tenant/loja e associação de clientes;
- voucher/QR Code persistido com confirmação de uso;
- auditoria administrativa;
- imagens e categorias;
- testes de carga concorrente em PostgreSQL;
- rotação e provisionamento de chaves do ESP8266.
