# IT Clube — Sistema Integrado de Fidelização, Gestão de PDV & IoT

[![Testes Automatizados](https://img.shields.io/badge/testes-94%20aprovados%20(100%25)-success.svg)](backend/tests/)
[![Auditoria de Segurança](https://img.shields.io/badge/seguran%C3%A7a-OWASP%20Hardened-blue.svg)](SECURITY.md)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/flask-3.1-black.svg)](https://flask.palletsprojects.com/)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED.svg)](Dockerfile)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

O **IT Clube** é uma solução corporativa completa de fidelização de clientes e gestão operacional de PDV voltada para o varejo físico de moda e cosméticos. O sistema combina uma aplicação web de alto desempenho com arquitetura em camadas (**Backend**, **Frontend**, **Database** e **IoT**), controle de acesso baseado em papéis (**RBAC**), portal de autoatendimento para clientes, extrato transacional com **Ledger Imutável de Pontos**, catálogo com resgate presencial seguro, auditoria de segurança completa e integração com hardware embarcado (**ESP8266 NodeMCU**).

---

## 1. Regras Fundamentais de Negócio

1. **Regra de Pontuação Unificada (1 Compra = 1 Ponto):**
   - No IT Clube, cada compra registrada no PDV ou via terminal IoT soma rigorosamente **1 ponto** à conta do cliente, de forma totalmente desacoplada do valor financeiro da compra.
   - Compras de R$ 10,00, R$ 100,00 ou R$ 1.000,00 computam exatamente **+1 ponto**.
2. **Autoatendimento do Cliente com Fronteiras Rígidas:**
   - O cliente possui área própria em `/perfil` para atualizar seus dados cadastrais (nome, telefone e e-mail) e alterar sua senha com segurança.
   - **Imutabilidade de Pontos:** O cliente não pode alterar seu saldo, criar movimentações ou visualizar dados de outros clientes.
3. **Catálogo de Prêmios & Resgate Exclusivo em Loja Física:**
   - Os clientes visualizam todas as recompensas cadastradas. Quando o saldo é inferior ao custo, o card é exibido desabilitado informando *"Pontos insuficientes"* e calculando *"Faltam X pontos"*.
   - **Bloqueio de Auto-Resgate:** Clientes finais não podem efetuar resgates por conta própria (chamadas diretas a `POST /api/resgates/` retornam `403 Forbidden`). O resgate e a entrega do prêmio são confirmados exclusivamente pela vendedora/gestora no balcão da loja.
4. **Foco Operacional sem Exibição Financeira Desnecessária:**
   - O dashboard e os relatórios priorizam indicadores de retenção, recorrência e total de compras pontuadas, sem métricas financeiras acumuladas expostas na rotina de pontuação.

---

## 2. Estrutura Padronizada do Repositório

O projeto adota uma arquitetura em camadas desacopladas e padronizadas:

```text
sistema-fidelizacao-integrado/
├── backend/                      # Aplicação Flask, APIs e Lógica de Negócio
│   ├── app/
│   │   ├── __init__.py           # Application Factory e extensões
│   │   ├── config.py             # Configurações de ambiente (Dev, Test, Prod)
│   │   ├── extensions.py         # SQLAlchemy, Migrate, Login, CSRF, Limiter
│   │   ├── forms.py              # Formulários seguros Flask-WTF
│   │   ├── models/               # Modelos relacionais (Usuario, Cliente, Compra, etc.)
│   │   ├── repositories/         # Camada de acesso e consultas otimizadas
│   │   ├── routes/               # Blueprints REST e controllers
│   │   ├── security/             # Políticas de senha e sanitização
│   │   ├── services/             # Ledger de pontos, RBAC e auditoria
│   │   └── utils/                # Sanitizadores e utilitários auxiliares
│   ├── tests/                    # Suíte completa de testes automatizados (94 testes)
│   ├── Dockerfile                # Dockerfile individual do backend
│   ├── requirements.txt          # Dependências Python com versões pinadas
│   └── run.py                    # Script de inicialização do backend
├── frontend/                     # Camada de Apresentação e Recursos Estáticos
│   ├── static/
│   │   ├── css/style.css         # Identidade visual e paleta oficial IT Clube
│   │   ├── js/                   # Scripts auxiliares e manipulação do DOM
│   │   └── assets/               # Imagens e ícones
│   ├── templates/                # Templates Jinja2 organizados por contexto
│   │   ├── base_clientes.html    # Layout base do Portal do Cliente
│   │   ├── base_vendedora.html   # Layout base do Painel da Loja
│   │   ├── login.html            # Login com seletor de perfil (Vendedora / Cliente)
│   │   ├── cadastro.html         # Cadastro público de clientes
│   │   ├── clientes/             # Início, Meus Pontos, Prêmios, Histórico e Perfil
│   │   └── vendedora/            # Dashboard, Pontuar PDV, Resgate, Clientes, Relatórios
│   └── README.md                 # Documentação detalhada do frontend
├── database/                     # Migrações, Esquemas e Carga de Dados
│   ├── migrations/               # Histórico versionado Alembic / Flask-Migrate (0001 a 0004)
│   ├── schema/                   # DDL e diagramas relacionais
│   ├── scripts/                  # Scripts SQL de suporte
│   ├── seeds/                    # Carga inicial e massa de testes (seed.py)
│   └── README.md                 # Documentação da modelagem do banco
├── arduino/                      # Terminal Físico IoT (ESP8266 NodeMCU)
│   ├── esp8266/                  # Código-fonte do firmware (.ino)
│   └── README.md                 # Pinagem, esquemático e protocolo de segurança PSK
├── docs/                         # Documentação Técnica e de Engenharia
│   ├── architecture/             # Visão geral da arquitetura e fluxos
│   ├── security/                 # Relatório de mitigação de vulnerabilidades e hardening
│   ├── api/                      # Catálogo completo de endpoints REST
│   └── development/              # Guia de configuração e execução local
├── .dockerignore                 # Arquivos ignorados na geração das imagens Docker
├── .env.example                  # Template estrito de variáveis de ambiente
├── .gitignore                    # Regras de exclusão do controle de versão
├── docker-compose.yml            # Orquestração do Backend + PostgreSQL
├── Dockerfile                    # Imagem Docker segura de produção (non-root)
├── README.md                     # Documento principal do projeto
├── run.py                        # Ponto de entrada raiz da aplicação
├── SECURITY.md                   # Política de divulgação de vulnerabilidades
└── test_security_audit.py        # Suíte de verificação de segurança (SAST / DAST local)
```

---

## 3. Matriz de Perfis e Permissões (RBAC)

O sistema conta com controle de acesso granular implementado em [`backend/app/services/rbac.py`](backend/app/services/rbac.py):

| Módulo / Ação | Proprietária | Gerente | Vendedora | Cliente |
| :--- | :---: | :---: | :---: | :---: |
| **Pontuar Compra no PDV** | :white_check_mark: | :white_check_mark: | :white_check_mark: | :x: |
| **Validar e Dar Baixa em Resgates** | :white_check_mark: | :white_check_mark: | :white_check_mark: | :x: |
| **Consultar Catálogo de Prêmios** | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| **Cadastrar / Editar Recompensas** | :white_check_mark: | :white_check_mark: | :x: | :x: |
| **Gestão de Clientes da Loja** | :white_check_mark: | :white_check_mark: | Consulta | :x: |
| **Autoatendimento (Meu Perfil)** | :x: | :x: | :x: | :white_check_mark: |
| **Gestão de Equipe (Funcionários)** | :white_check_mark: | :x: | :x: | :x: |
| **Consulta à Trilha de Auditoria** | :white_check_mark: | :x: | :x: | :x: |
| **Relatórios e Análise de Retenção** | :white_check_mark: | :white_check_mark: | :x: | :x: |

---

## 4. Como Executar o Projeto

### 4.1. Execução Local Rápida

1. **Clone o repositório:**
   ```bash
   git clone <URL_DO_REPOSITORIO>
   cd sistema-fidelizacao-integrado
   ```

2. **Crie e ative o ambiente virtual:**
   ```bash
   python -m venv venv
   # Windows:
   .\venv\Scripts\Activate.ps1
   # Linux/macOS:
   source venv/bin/activate
   ```

3. **Instale as dependências:**
   ```bash
   pip install -r backend/requirements.txt
   ```

4. **Configure as variáveis de ambiente:**
   ```bash
   cp .env.example .env
   ```
   Edite o `.env` com sua chave secreta e configurações.

5. **Execute as migrações e popule o banco inicial:**
   ```bash
   flask db upgrade
   python database/seeds/seed.py
   ```

6. **Inicie o servidor:**
   ```bash
   python run.py
   ```
   Acesse a aplicação em `http://127.0.0.1:5000`.

### 4.2. Execução com Docker & Docker Compose

```bash
# Sobe a aplicação conteinerizada com banco de dados PostgreSQL
docker compose up --build -d

# Visualizar logs
docker compose logs -f backend
```

---

## 5. Credenciais Padrão de Demonstração

Após a execução do script `database/seeds/seed.py`, o sistema disponibiliza os seguintes acessos:

- **Proprietária / Admin:**
  - E-mail: `admin@loja.com`
  - Senha: `ITClube2026`
- **Vendedora (PDV):**
  - E-mail: `vendedora@loja.com`
  - Senha: `ITClube2026`
- **Cliente (Ana Silva):**
  - Telefone: `11999991111`
  - Senha: `ITClube2026`

---

## 6. Testes Automatizados & Qualidade

O projeto possui **100% de aprovação** em suas baterias de testes:

```bash
# Executa todos os 94 testes unitários e de integração
python -m unittest discover backend/tests

# Executa os testes de auditoria de segurança (SAST/DAST)
python test_security_audit.py
```

### Cobertura de Testes:
- **`test_itclube_regras.py`**: Validação de 1 compra = 1 ponto, independência do valor financeiro, autoatendimento, bloqueio de auto-resgate e privacidade de senhas em logs.
- **`test_pontos_ledger.py`**: Integridade e concorrência no livro contábil de pontos.
- **`test_recompensas.py`**: Estoque atômico, vigência de prêmios e permissões de resgate.
- **`test_security_audit.py`**: Mitigações para OWASP Top 10, proteção contra BOLA/IDOR, Anti-CSRF, PBKDF2 e isolamento de ambiente.
- **`test_rbac.py`**, **`test_cadastro.py`**, **`test_troca_senha.py`**, **`test_funcionarios.py`**, **`test_auditoria.py`**.

---

## 7. Licença

Este projeto é distribuído sob a licença **MIT**. Consulte o arquivo `LICENSE` para mais detalhes.
