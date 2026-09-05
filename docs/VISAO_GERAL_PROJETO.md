# FideliZa

O FideliZa é um sistema acadêmico de fidelização para uma loja física. Ele reúne o portal da gestora, o portal do cliente e um terminal ESP8266 que registra compras no mesmo backend Flask. Compras geram pontos; pontos podem ser trocados por recompensas persistidas e administradas pela loja.

## 1. Visão do Produto

O sistema resolve o acompanhamento manual de clientes recorrentes, compras, pontos e benefícios. O público-alvo inicial é uma pequena loja com uma ou mais usuárias administrativas e clientes cadastrados por telefone.

A gestora consulta indicadores, cadastra clientes, registra compras, cria e gerencia recompensas e realiza uma entrega para um cliente. O cliente acompanha saldo e extrato, consulta o catálogo real e resgata quando possui pontos suficientes. O programa converte o valor inteiro de cada compra em pontos conforme `PONTOS_POR_REAL`.

As recompensas podem ser produtos físicos, descontos percentuais ou descontos em valor fixo. Sua disponibilidade depende de status, validade e estoque. O ESP8266 funciona como terminal simples de PDV: envia telefone e valor para a API de compras e acende um LED quando recebe HTTP 201.

## 2. Principais Funcionalidades

- autenticação independente de gestoras e clientes;
- auto-cadastro de cliente com Flask-WTF e CSRF;
- cadastro e consulta administrativa de clientes;
- registro de compras pela gestora ou pelo ESP8266;
- crédito e extrato de pontos;
- dashboards e relatórios de recorrência, churn e resgates;
- cadastro, edição, pausa e reativação de recompensas;
- controle de tipo, benefício, validade e estoque;
- catálogo de recompensas carregado do banco;
- resgate pelo cliente ou entrega pela gestora;
- histórico com snapshot do nome e custo da recompensa;
- health check em `/health`.

## 3. Stack Tecnológica

### Backend

- Python 3;
- Flask com Application Factory (`create_app`);
- Blueprints de autenticação, clientes, compras, resgates e recompensas;
- Flask-SQLAlchemy / SQLAlchemy;
- Flask-Login;
- Flask-Migrate / Alembic;
- Flask-WTF / CSRFProtect;
- Flask-Limiter.

### Frontend

- Jinja2 SSR;
- HTML5 e CSS próprio;
- Bootstrap 5;
- Font Awesome e Bootstrap Icons;
- JavaScript nativo e Fetch API.

Não há Node, React, Vue, Vite ou bundler.

### Banco de dados

SQLite é o padrão de desenvolvimento (`sqlite:///fidelizacao.db`). A URI pode ser substituída por PostgreSQL por meio de `DATABASE_URL`; o driver `psycopg2-binary` consta nas dependências. O arquivo `database/scripts_sql/schema_postgresql.sql` representa o schema equivalente para consulta e provisionamento manual, mas Alembic é o caminho recomendado.

### IoT

O firmware em C++ usa `ESP8266WiFi`, `ESP8266HTTPClient` e HTTP/JSON. O dispositivo autentica pelo header `X-Device-Key`.

## 4. Estrutura de Diretórios

```text
app/
  models/              entidades SQLAlchemy
  routes/              Blueprints web e REST
  config.py            configurações por ambiente
  extensions.py        extensões Flask
frontend/
  templates/           páginas Jinja2 de cliente e gestora
  static/css/           design visual compartilhado
database/scripts_sql/   representação manual do schema PostgreSQL
migrations/             ambiente e revisões Alembic
arduino/esp8266/        firmware do terminal físico
tests/                  testes unittest da funcionalidade de recompensas
docs/                   documentação técnica e de implementação
run.py                  ponto de entrada da aplicação
seed.py                 reset destrutivo e dados de demonstração
```

## 5. Arquitetura

```mermaid
flowchart LR
    G[Gestora] --> FV[Frontend Jinja da gestora]
    C[Cliente] --> FC[Frontend Jinja do cliente]
    E[ESP8266] -->|HTTP JSON + X-Device-Key| API[API Flask]
    FV -->|sessão + Fetch| API
    FC -->|sessão + Fetch| API
    API --> AU[Autenticação e RBAC]
    API --> CO[Compras e pontuação]
    API --> RE[Recompensas]
    API --> RS[Resgates]
    AU --> ORM[SQLAlchemy]
    CO --> ORM
    RE --> ORM
    RS --> ORM
    ORM --> DB[(SQLite / PostgreSQL)]
```

## 6. Diagrama de Componentes

```mermaid
flowchart TB
    APP[create_app] --> EXT[Extensões Flask]
    APP --> MAIN[main Blueprint]
    APP --> AUTH[auth Blueprint]
    APP --> CLI[clientes Blueprint]
    APP --> COM[compras Blueprint]
    APP --> RES[resgates Blueprint]
    APP --> REC[recompensas Blueprint]
    MAIN --> TPL[Templates Jinja2]
    AUTH --> MOD[Models SQLAlchemy]
    CLI --> MOD
    COM --> MOD
    RES --> MOD
    REC --> MOD
    EXT --> MOD
    MOD --> DB[(Banco)]
    MIG[Flask-Migrate / Alembic] --> DB
```

## 7. Modelo de Dados

```mermaid
erDiagram
    USUARIO ||--o{ RECOMPENSA : cria
    CLIENTE ||--o{ COMPRA : realiza
    CLIENTE ||--o{ RESGATE : efetua
    RECOMPENSA o|--o{ RESGATE : referencia

    USUARIO {
        int id_usuario PK
        string nome
        string login UK
        string email UK
        string senha_hash
        string nivel_acesso
    }
    CLIENTE {
        int id_cliente PK
        string nome
        string telefone UK
        string email UK
        string senha_hash
        datetime data_cadastro
        int pontos_acumulados
    }
    COMPRA {
        int id_compra PK
        int id_cliente FK
        datetime data
        decimal valor
        int pontos_gerados
    }
    RECOMPENSA {
        int id_recompensa PK
        int id_usuario FK
        string nome
        int custo_pontos
        string tipo
        decimal valor_beneficio
        date validade
        int quantidade_total
        int quantidade_disponivel
        string status
        datetime created_at
        datetime updated_at
    }
    RESGATE {
        int id_resgate PK
        int id_cliente FK
        int id_recompensa FK
        datetime data
        int pontos_utilizados
        string descricao_recompensa
    }
```

`RESGATE.id_recompensa` é anulável para preservar históricos anteriores à funcionalidade. Todo novo resgate o preenche. `pontos_utilizados` e `descricao_recompensa` são snapshots imutáveis do momento do resgate.

## 8. Fluxo de Pontuação

```mermaid
sequenceDiagram
    participant O as Gestora ou ESP8266
    participant API as POST /api/compras/
    participant DB as Banco
    participant C as Cliente
    O->>API: telefone/id_cliente + valor
    API->>API: autenticar sessão ou X-Device-Key
    API->>DB: buscar cliente
    API->>API: calcular int(valor) x PONTOS_POR_REAL
    API->>DB: inserir Compra
    API->>DB: creditar pontos_acumulados
    API->>DB: commit
    API-->>O: HTTP 201 + novo saldo
    DB-->>C: saldo disponível no portal
```

## 9. Fluxo de Resgate

```mermaid
sequenceDiagram
    participant A as Cliente ou Gestora
    participant API as POST /api/resgates/
    participant DB as Banco
    A->>API: id_recompensa e, para gestora, id_cliente
    API->>DB: carregar e bloquear Recompensa
    API->>DB: carregar e bloquear Cliente
    API->>API: validar proprietário no fluxo administrativo
    API->>API: validar ativa, validade e estoque
    API->>API: ler custo do banco e validar saldo
    API->>DB: UPDATE condicional do estoque
    API->>DB: UPDATE condicional do saldo
    API->>DB: inserir Resgate com FK e snapshots
    API->>DB: commit único
    API-->>A: HTTP 201 + novo saldo e estoque
    Note over API,DB: Qualquer falha provoca rollback
```

## 10. Fluxo da Gestora e Catálogo

```mermaid
flowchart TD
    G[Gestora autenticada] --> F[Preenche formulário]
    F --> V[Validação server-side]
    V --> P[(Recompensa persistida com id_usuario da sessão)]
    P --> A{Ativa, válida e com estoque?}
    A -->|Sim| CAT[Cliente vê opção disponível]
    A -->|Não| IND[Cliente vê pausa/esgotamento ou expirada fica oculta]
    CAT --> S{Saldo suficiente?}
    S -->|Não| BLOQ[Pontos insuficientes e botão bloqueado]
    S -->|Sim| BTN[Botão de resgate habilitado]
    BTN --> RES[Transação de resgate]
```

## 11. Autenticação e Autorização

Flask-Login armazena o identificador na sessão. `Usuario.get_id()` produz `u_<id>` e `Cliente.get_id()` produz `c_<id>`, eliminando colisões entre tabelas. O `user_loader` rejeita IDs sem prefixo.

Os decorators `vendedora_required` e `cliente_required` protegem páginas. APIs também verificam `is_vendedora` e `is_cliente`. Na criação de recompensa, `id_usuario` vem exclusivamente de `current_user`. Leitura individual, edição, pausa, reativação e entrega administrativa filtram simultaneamente `id_recompensa` e `current_user.id_usuario`; um ID de outra gestora retorna 404.

Clientes nunca escolhem `id_cliente` como autoridade: o backend usa a sessão. No fluxo administrativo, a gestora informa o cliente, mas só pode escolher recompensa própria. Como o modelo não possui vínculo Cliente-Loja, o catálogo do cliente é global no modelo atual de loja única.

## 12. Sistema de Pontos

O saldo atual fica em `Cliente.pontos_acumulados`. `POST /api/compras/` converte a parte inteira do valor da compra em pontos e multiplica por `PONTOS_POR_REAL` (padrão 1). A compra e o crédito são gravados no mesmo commit.

No resgate, o custo vem de `Recompensa.custo_pontos`. Um `UPDATE` com condição `pontos_acumulados >= custo` evita saldo negativo mesmo sob concorrência. O débito, a redução do estoque e o histórico pertencem à mesma transação.

## 13. Sistema de Recompensas

Tipos persistidos:

- `produto_fisico`: benefício financeiro nulo;
- `desconto_percentual`: decimal maior que zero e até 100;
- `desconto_valor_fixo`: decimal monetário maior que zero.

O status administrativo é `ativa` ou `pausada`. `expirada` e `esgotada` são estados derivados. A data é obrigatória e inclusiva: uma recompensa permanece válida até o fim da data informada no timezone `TIMEZONE`, padrão `America/Sao_Paulo`. Criações com data passada são rejeitadas.

O estoque mantém quantidade total e disponível. No cadastro, ambas começam iguais. Ao editar o total, a quantidade já resgatada (`total - disponível`) é preservada; não se pode reduzir o total abaixo do consumo histórico. Somente um resgate confirmado reduz a disponibilidade.

Regra de disponibilidade:

```text
status = ativa
AND validade >= data local atual
AND quantidade_disponivel > 0
```

Regra para o cliente:

```text
recompensa disponível
AND pontos_acumulados >= custo_pontos
```

Recompensas pausadas e esgotadas permanecem visíveis com estado bloqueado. Expiradas ficam visíveis na administração e são ocultadas do catálogo do cliente. Recompensas com saldo insuficiente permanecem visíveis com a mensagem “Pontos insuficientes” e a diferença de pontos.

O antigo código aleatório de voucher no navegador foi removido. Não existia validação posterior do voucher; ampliar esse detalhe para um novo domínio não era necessário. A interface apresenta o ID persistido do resgate como comprovante da operação.

## 14. Como Subir o Projeto (Linux/WSL)

Pré-requisitos: Python 3.10 ou superior, módulo `venv` e acesso ao banco escolhido.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env  # caso você crie um arquivo local a partir dos nomes abaixo
flask --app run.py db upgrade
FLASK_ENV=development python run.py
```

Acesse `http://127.0.0.1:5000`.

O arquivo `.env.example` contém apenas placeholders seguros. Copie-o para `.env`, substitua as chaves e não versione segredos; o `.gitignore` já ignora `.env`.

### Variáveis de ambiente

| Variável | Obrigatória | Exemplo/uso |
|---|---:|---|
| `SECRET_KEY` | produção | `troque-por-uma-chave-longa-e-aleatoria` |
| `DATABASE_URL` | não | `sqlite:///fidelizacao.db` |
| `FLASK_ENV` | não | `development` ou `production` |
| `PONTOS_POR_REAL` | não | `1` |
| `TIMEZONE` | não | `America/Sao_Paulo` |
| `IOT_DEVICE_KEY` | produção/IoT | `troque-por-uma-chave-de-dispositivo` |
| `HOST` | não | `0.0.0.0` em produção |
| `PORT` | não | `5000` |

Os defaults de `SECRET_KEY` e `IOT_DEVICE_KEY` existem apenas para desenvolvimento e devem obrigatoriamente ser substituídos em produção.

### SQLite

Sem `DATABASE_URL`, o Flask-SQLAlchemy cria `instance/fidelizacao.db`. Aplique sempre:

```bash
flask --app run.py db upgrade
```

### PostgreSQL

Exemplo de URI, sem credencial real:

```text
DATABASE_URL=postgresql+psycopg2://usuario:senha@localhost:5432/fideliza
```

Crie o banco e execute `flask --app run.py db upgrade`. O PostgreSQL aplica efetivamente `SELECT ... FOR UPDATE`; no SQLite, os updates condicionais mantêm as invariantes e o locking é do próprio arquivo.

### Seed de demonstração

> **Atenção:** `python seed.py` executa `db.drop_all()` e apaga os dados das tabelas da aplicação. Use somente em banco descartável de desenvolvimento, nunca em produção ou em uma base que precise ser preservada.

Depois do reset, o script recria o schema pelos models, marca o head do Alembic e popula gestora, clientes, compras, recompensas e resgate de demonstração.

## 15. Migrations

As revisões são:

- `0001_schema_legado`: baseline tolerante às quatro tabelas antigas;
- `0002_recompensas`: cria `recompensa`, índices e adiciona `resgate.id_recompensa` anulável.

Em banco novo ou legado, execute:

```bash
flask --app run.py db upgrade
flask --app run.py db current
flask --app run.py db check
```

O baseline consulta as tabelas existentes antes de criá-las. Assim, um SQLite anterior à adoção do Alembic pode receber o upgrade sem excluir resgates existentes.

## 16. Integração ESP8266

Endpoint: `POST /api/compras/`.

Headers:

```http
Content-Type: application/json
X-Device-Key: chave-configurada-no-servidor
```

Payload:

```json
{"telefone": "11999991111", "valor": 50.00}
```

A resposta HTTP 201 inclui compra, cliente e `saldo_atualizado`. O firmware acende o LED verde nesse status. Ajuste `SERVIDOR` para o IP do computador acessível na mesma rede. Nunca publique a chave real em firmware ou documentação pública; em uma implantação real, provisionamento e rotação devem ser planejados.

## 17. Rotas Web

| Rota | Perfil | Objetivo |
|---|---|---|
| `/` | público | login unificado |
| `/cadastro` | público | redirecionar para auto-cadastro |
| `/auth/cadastro` | público | formulário e envio do cadastro |
| `/health` | público | health check |
| `/dashboard` | gestora | indicadores da loja |
| `/clientes` | gestora | cadastro/listagem de clientes |
| `/pontuar` | gestora | registrar compra no PDV |
| `/resgate` | gestora | entregar recompensa real |
| `/gestao-recompensas` | gestora | criar, editar, pausar e reativar |
| `/relatorios` | gestora | relatórios do programa |
| `/bemvindo` | cliente | dashboard pessoal |
| `/meuspontos` | cliente | saldo e totais |
| `/recompensas` | cliente | catálogo persistido |
| `/historico` | cliente | compras e resgates próprios |

## 18. API

| Método | Endpoint | Perfil | Descrição |
|---|---|---|---|
| POST | `/auth/login` | público | login da gestora |
| POST | `/auth/vendedora/login` | público | alias do login da gestora |
| POST | `/auth/cliente/login` | público | login do cliente |
| POST | `/auth/logout` | autenticado | encerra a sessão |
| GET | `/auth/me` | autenticado | perfil da sessão |
| GET | `/api/clientes/me` | cliente | dados próprios |
| GET | `/api/clientes/` | autenticado | próprio cliente ou lista administrativa |
| GET | `/api/clientes/<id>` | autenticado/RBAC | cliente por ID com proteção BOLA |
| POST | `/api/clientes/` | gestora | cadastra cliente |
| GET | `/api/compras/` | autenticado/RBAC | compras visíveis ao perfil |
| POST | `/api/compras/` | gestora ou ESP8266 | registra compra e credita pontos |
| GET | `/api/resgates/` | autenticado/RBAC | histórico visível ao perfil |
| POST | `/api/resgates/` | cliente ou gestora | resgata pelo `id_recompensa` |
| GET | `/api/recompensas/` | autenticado/RBAC | catálogo do cliente ou recursos da gestora |
| POST | `/api/recompensas/` | gestora | cria recompensa própria |
| GET | `/api/recompensas/<id>` | autenticado/RBAC | detalhe autorizado |
| PATCH | `/api/recompensas/<id>` | gestora proprietária | edita, pausa ou reativa |

POST/PATCH de recompensas e resgates feitos pelo navegador exigem o token CSRF enviado no header `X-CSRFToken`.

## 19. Segurança

- senhas são armazenadas com hashing Werkzeug;
- sessão distingue perfis com IDs prefixados;
- decorators e verificações por perfil protegem páginas e APIs;
- consultas de recompensa administrativa filtram pelo proprietário e retornam 404 em IDOR/BOLA;
- payloads são mapeados explicitamente; proprietário, estoque disponível e timestamps são protegidos contra mass assignment;
- custo e descrição do resgate vêm exclusivamente da recompensa persistida;
- CSRF protege mutações de recompensas e resgates; cadastro web usa Flask-WTF;
- login possui rate limit;
- ORM parametriza queries;
- transação única, `FOR UPDATE` e updates condicionais protegem saldo/estoque;
- erros fazem rollback e respostas não expõem stack trace;
- API IoT compara a chave com `hmac.compare_digest`;
- valores de compra e benefício utilizam `Decimal`/`Numeric`, não `float` no backend.

Os Blueprints legados de clientes e compras continuam isentos de CSRF para manter o contrato existente e, no caso de compras, permitir o ESP8266. Esse desenho deve ser revisto antes de exposição pública ampla.

## 20. Testes

Suítes:

- `test_security_audit.py`: sete verificações legadas de autenticação, IoT, sessão, senha, CSRF de cadastro e produção;
- `tests/test_recompensas.py`: autenticação/perfil, criação e validações, IDOR, status, estoque, catálogo, custo confiável, estados indisponíveis, rollback, última unidade, histórico legado e CSRF.

Execução:

```bash
python -m unittest discover -s tests -v
python test_security_audit.py
python -m compileall -q app migrations tests run.py seed.py test_security_audit.py
flask --app run.py db check
```

Execute a suíte legada com `DATABASE_URL` apontando para um banco temporário previamente populado; ela usa registros de demonstração. Nunca aponte `seed.py` para a base corrente apenas para preparar testes.

Exemplo seguro em um banco descartável:

```bash
TEST_DB=$(mktemp /tmp/fideliza-test-XXXXXX.db)
DATABASE_URL="sqlite:///$TEST_DB" python seed.py
DATABASE_URL="sqlite:///$TEST_DB" python test_security_audit.py
```

## 21. Limitações Atuais

- não existe entidade Loja nem associação Cliente-Loja; o catálogo do cliente é global e a separação entre gestoras aplica-se à administração e à entrega;
- SQLite não oferece row lock igual ao PostgreSQL; updates condicionais protegem invariantes, mas PostgreSQL é preferível para concorrência real;
- não existe voucher de uso único/QR Code nem fluxo separado de emissão e consumo;
- imagens de catálogo não fazem parte do model;
- os Blueprints legados de clientes/compras mantêm a política de CSRF anterior;
- defaults de desenvolvimento para chaves não são adequados à produção.

## 22. Evoluções Futuras

- modelar lojas e associação explícita cliente-loja;
- emitir voucher único ou QR Code com validade e confirmação de entrega;
- notificações de estoque, expiração e novo benefício;
- auditoria de alterações administrativas;
- imagens e categorias de catálogo;
- campanhas com período de início e limites por cliente;
- analytics de conversão por recompensa;
- rotação/provisionamento seguro de chaves IoT.
