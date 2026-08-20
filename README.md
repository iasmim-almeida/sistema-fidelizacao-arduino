# 💳 FideliZa — Sistema de Fidelização (Back + Front + DB + Arduino)

Sistema integrado de fidelização: a **vendedora** identifica o cliente pelo
**telefone** no PDV, registra a compra (que gera pontos) e valida resgates de
recompensas. O **cliente** consulta saldo, histórico e resgata prêmios. Um
módulo **ESP8266** confirma a pontuação com LED verde.

## 🧱 Stack
- **Back-end:** Flask (application factory + blueprints)
- **ORM:** SQLAlchemy + Flask-Migrate
- **Auth:** Flask-Login (sessão/cookie, senha com hash) — **login por e-mail**
- **Front-end:** Bootstrap 5 + Font Awesome, templates Jinja (tema FideliZa 💗)
- **Banco:** SQLite (dev) → PostgreSQL (produção)

## 🚀 Como rodar (SQLite / desenvolvimento)
```bash
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows
pip install -r requirements.txt
python seed.py                     # cria banco + admin + clientes exemplo
python run.py
```
Acesse **http://127.0.0.1:5000** → login: **admin@loja.com** / senha: **1234**

## 🗺️ Rotas (páginas)
| Rota | Área | Descrição |
|---|---|---|
| `/` | — | Login (chama `POST /auth/login`) |
| `/dashboard` | Vendedora | Indicadores + atividade |
| `/clientes` | Vendedora | Lista + cadastro de clientes |
| `/pontuar` | Vendedora | Identifica por telefone e pontua |
| `/resgate` | Vendedora | Valida e entrega recompensas |
| `/relatorios` | Vendedora | Totais, top clientes, movimentações |
| `/bemvindo` | Cliente | Identificação por telefone + onboarding |
| `/meuspontos` | Cliente | Saldo e estatísticas |
| `/recompensas` | Cliente | Vitrine de prêmios (resgate real) |
| `/historico` | Cliente | Extrato de compras e resgates |

## 🔌 API (JSON)
| Método | Rota | Descrição |
|---|---|---|
| POST | `/auth/login` | `{email, senha}` ou `{login, senha}` |
| POST | `/auth/logout` | encerra sessão |
| GET | `/auth/me` | usuário logado |
| GET/POST | `/api/clientes/` | lista/cadastra (`?telefone=` busca) |
| GET | `/api/clientes/<id>` | detalhe |
| GET/POST | `/api/compras/` | lista/registra (aceita `telefone` ou `id_cliente`) |
| GET/POST | `/api/resgates/` | lista/registra (valida saldo) |

### Regra de pontuação
Cada **R$ 1,00** gera **`PONTOS_POR_REAL`** pontos (padrão 1). Configurável no `.env`.

## 🐘 Migração para PostgreSQL
1. Crie o banco: `CREATE DATABASE fidelizacao_db;`
2. No `.env`, troque `DATABASE_URL` para:
   `postgresql://postgres:senha@localhost:5432/fidelizacao_db`
3. `pip install psycopg2-binary`
4. `python seed.py` (ou use Flask-Migrate). Referência: `database/scripts_sql/schema_postgresql.sql`

> Como usamos SQLAlchemy, **o código dos models não muda** na migração.

## 🔩 ESP8266
`arduino/esp8266/fidelizacao_esp8266.ino` faz `POST /api/compras/` com
`{telefone, valor}` e acende LED verde no HTTP 201. Requer `host=0.0.0.0`
(já configurado no `run.py`) para ser alcançável na rede local.

## 📝 Notas / próximos passos
- As rotas `/api/*` estão públicas (para facilitar dev). Para produção, adicione
  `@login_required` nelas.
- O front do cliente identifica o usuário por telefone (guardado em `localStorage`),
  já que o back não possui login de cliente final.
