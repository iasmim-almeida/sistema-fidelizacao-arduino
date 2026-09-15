# Visão Geral da Arquitetura — IT Clube

O **IT Clube** é uma solução completa de fidelização de clientes com integração física e digital, desenhada para lojas físicas do varejo de moda e beleza.

---

## 1. Diagrama Arquitetural de Alto Nível

```mermaid
flowchart TD
    subgraph Cliente["Cliente Final"]
        AppWeb["Portal do Cliente (Web / Mobile)"]
    end

    subgraph Loja["Loja Física / PDV"]
        Balcao["Terminal Web da Vendedora"]
        ESP["Terminal IoT ESP8266 + LED"]
    end

    subgraph Backend["Backend Application (Flask)"]
        Rotas["Controllers / Blueprints (Auth, Clientes, Compras, Resgates)"]
        RBAC["Serviço de RBAC & Autenticação (Flask-Login)"]
        Ledger["Serviço de Ledger de Pontos Atômico"]
        Audit["Serviço de Auditoria & Trilha de Segurança"]
        Repos["Camada de Repositórios & Modelos SQLAlchemy"]
    end

    subgraph Dados["Persistência de Dados"]
        Postgres[("PostgreSQL / SQLite")]
    end

    AppWeb -->|HTTPS / REST + CSRF| Rotas
    Balcao -->|HTTPS / REST + CSRF| Rotas
    ESP -->|HTTP / PSK (X-Device-Key)| Rotas

    Rotas --> RBAC
    Rotas --> Ledger
    Rotas --> Audit
    Ledger --> Repos
    Audit --> Repos
    Repos --> Postgres
```

---

## 2. Camadas do Sistema

### 2.1. Camada de Apresentação (Frontend)
- Baseada em templates server-rendered **Jinja2**, estilizada com **Bootstrap 5**, **FontAwesome** e CSS customizado.
- Arquitetura de duas personas:
  1. **Portal do Cliente:** Consulta de saldo, extrato, catálogo de prêmios e gestão de conta (nome, telefone, e-mail e senha).
  2. **Portal da Loja / PDV:** Identificação por telefone, crédito de pontos (+1 ponto por compra), catálogo de prêmios, baixa e validação presencial de resgates, e relatórios analíticos de clientes ativos vs inativos.

### 2.2. Camada de Aplicação (Backend)
- Construído com **Python 3.12+** e framework **Flask**, modularizado através de Blueprints:
  - `auth`: Autenticação com proteção contra enumeração, sessões assinadas e controle de força de senhas.
  - `clientes`: Consulta, filtragem e autoatendimento seguro do cliente via `/me`.
  - `compras`: Processamento transacional de compras e pontuação (1 compra = 1 ponto).
  - `recompensas`: Manutenção de benefícios e catálogo com controle de vigência e estoque.
  - `resgates`: Baixa atômica de pontos e emissão do prêmio confirmada pela vendedora.
  - `main`: Roteamento de páginas e agregação de dashboards.

### 2.3. Camada de Domínio & Regras de Negócio
- **Regra de Pontuação:** Cada compra confirmada gera exatamente 1 ponto (`pontos_gerados = 1`), independentemente do valor transacionado.
- **Ledger Duplo de Pontos:** Cada alteração no saldo do cliente é acompanhada de um registro imutável em `movimentacao_pontos`, garantindo auditoria contábil.
- **Controle de Acesso Baseado em Papéis (RBAC):** Papéis segregados para `proprietario`, `gerente`, `vendedor` e `cliente`.

### 2.4. Camada de Integração IoT (Hardware)
- Microcontrolador **ESP8266** configurado com chave pré-compartilhada (`X-Device-Key`) para envio de compras e ativação de sinalizador luminoso (LED Verde).
