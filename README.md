# 💳 FideliZa — Sistema de Fidelização Integrado (Back + Front + DB + Arduino)

Sistema integrado de fidelização completo:
- **Área da Vendedora (Admin):** Gerencia a loja, visualiza indicadores gerenciais (faturamento, clientes cadastrados, pontos distribuídos), pontua compras no PDV e valida resgates de recompensas.
- **Área do Cliente (Portal Exclusivo):** Painel do cliente para acompanhamento do saldo individual de pontos, extrato de compras e resgate de vouchers no catálogo de prêmios.
- **Módulo ESP8266 (IoT):** Terminal físico conectado à rede Wi-Fi que envia compras via REST API (`POST /api/compras/`) e confirma o crédito com feedback visual no LED verde.

---

## 🧱 Stack Tecnológica
- **Back-end:** Python 3 + Flask (Application Factory + Blueprints)
- **ORM & Banco:** SQLAlchemy + SQLite (desenvolvimento) / PostgreSQL (produção)
- **Autenticação & Sessões:** Flask-Login com autenticação dupla independente (Vendedora/Admin e Cliente)
- **Front-end:** HTML5, Bootstrap 5, Font Awesome, Bootstrap Icons e Jinja2 SSR
- **Hardware/IoT:** ESP8266 (C++ / Arduino IDE)

---

## 🚀 Como Rodar o Projeto

```bash
# 1. Ativar o ambiente virtual (Windows PowerShell)
.venv\Scripts\Activate.ps1

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Criar e popular o banco de dados com usuários de demonstração
python seed.py

# 4. Iniciar o servidor
python run.py
```

Acesse **http://127.0.0.1:5000** no navegador.

---

## 🔑 Acessos de Demonstração (Disponíveis na Tela Inicial)

A tela inicial (`/`) possui um seletor com as duas opções de login e botões de preenchimento em 1-clique:

| Perfil | Identificador | Senha | Dashboard de Destino |
|---|---|---|---|
| **👩‍💼 Vendedora (Admin)** | `admin@loja.com` | `1234` | `/dashboard` |
| **🛍️ Cliente (Ana Silva)** | `11999991111` | `1234` | `/bemvindo` |
| **🛍️ Cliente (Carlos Oliveira)** | `11988882222` | `1234` | `/bemvindo` |

---

## 🗺️ Rotas e Separação de Dashboards

### Área da Vendedora (Requer perfil de Vendedora)
| Rota | Descrição |
|---|---|
| `/dashboard` | Visão geral da loja: total de clientes, pontos distribuídos, faturamento e compras recentes |
| `/clientes` | Cadastro e listagem de todos os clientes |
| `/pontuar` | Identificação de cliente por telefone e cálculo automático de pontos |
| `/resgate` | Entrega de brindes e validação de cupons |
| `/relatorios` | Relatórios consolidados de vendas, top clientes e fluxo de pontos |

### Área do Cliente (Requer perfil de Cliente)
| Rota | Descrição |
|---|---|
| `/bemvindo` | Dashboard individual do cliente com saldo atual e resumo de vantagens |
| `/meuspontos` | Extrato detalhado de saldo, total ganho e total utilizado |
| `/recompensas` | Vitrine de prêmios com resgate de voucher em tempo real |
| `/historico` | Extrato das compras e resgates do próprio cliente logado |

---

## 🔌 API REST (JSON)

| Método | Endpoint | Proteção | Descrição |
|---|---|---|---|
| POST | `/auth/login` | Público | Autenticação de Vendedora (retorna redirecionamento `/dashboard`) |
| POST | `/auth/cliente/login` | Público | Autenticação de Cliente (retorna redirecionamento `/bemvindo`) |
| POST | `/auth/logout` | Autenticado | Encerra a sessão atual de qualquer perfil |
| GET | `/auth/me` | Autenticado | Retorna os dados e perfil (`vendedora` ou `cliente`) do usuário logado |
| GET | `/api/clientes/me` | Cliente | Retorna os dados e saldo atualizados do cliente logado |
| GET | `/api/clientes/` | RBAC | Lista todos (vendedora) ou busca por telefone |
| POST | `/api/clientes/` | Vendedora | Cadastra novo cliente com senha padrão `1234` |
| GET | `/api/compras/` | RBAC | Retorna todas as compras (vendedora) ou apenas compras do cliente autenticado |
| POST | `/api/compras/` | PDV/IoT | Registra compra, credita pontos e atualiza saldo |
| GET | `/api/resgates/` | RBAC | Retorna todos os resgates (vendedora) ou apenas os resgates do cliente autenticado |
| POST | `/api/resgates/` | RBAC | Efetua resgate e deduz pontos com validação de saldo |
