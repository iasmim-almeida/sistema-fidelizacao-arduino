# Go-Live Checklist — FideliZa / IT Clube

> **Checklist histórico e não executável:** contém módulos removidos e resultados antigos. Use `DEPLOY_RENDER.md` e `MIGRATION_NEON_PLAN.md`.

Este documento constitui o portão formal de decisão (*Go/No-Go Gate*) para a entrada em produção do sistema FideliZa / IT Clube na infraestrutura Render conectada ao banco gerenciado PostgreSQL Neon.

---

## 1. Código e Repositório (CODE)

- [ ] **Bateria Completa de Testes**:
  - Testes Unitários e de Integração: **100/100 testes com status PASSED** (`python -m unittest discover backend/tests`).
  - Auditoria Automatizada de Segurança: **7/7 testes com status PASSED** (`python test_security_audit.py`).
  - Testes de Hardening e Regras de Negócio: **6/6 testes específicos com status PASSED** (`test_production_hardening.py`).
- [ ] **Branch e Versionamento**:
  - Branch de homologação `feat/banco-nuvem` testada e validada.
  - Commits limpos e organizados; pull request revisado conforme `docs/PRE_PR_CHECKLIST.md`.
- [ ] **Higiene do Repositório**:
  - Arquivo `.gitignore` validado com bloqueio estrito para: `.env`, `*.db`, `*.sqlite3`, `__pycache__/`, `instance/`, `*.log`, `.gunicorn/`.
  - Ausência total de arquivos de credenciais ou chaves criptográficas versionadas no Git (`git log -S "SECRET_KEY" -p` verificado).
  - Remoção de comandos de debug (`print()`, `breakpoint()`, `import pdb`) em rotas produtivas.

---

## 2. Segurança e Conformidade (SECURITY - OWASP Top 10)

- [ ] **A01: Broken Access Control**:
  - Auto-resgate por clientes bloqueado com HTTP 403 Forbidden em `POST /api/resgates/`.
  - Apenas perfis autorizados (`proprietario` ou `funcionario`) validam resgates no balcão.
  - Tentativa de elevação de privilégios (`cargo` ou `nivel_acesso`) neutralizada no cadastro público.
  - Clientes acessam estritamente seu próprio saldo, perfil e catálogo de recompensas.
- [ ] **A02: Cryptographic Failures**:
  - Hashing de senhas seguro utilizando Argon2 / Bcrypt com salt dinâmico.
  - Chave de aplicação `SECRET_KEY` obrigatória em produção (mínimo 32 bytes gerados via `secrets.token_hex(32)`). Inicialização bloqueada se ausente.
  - Conexão TLS/SSL obrigatória para tráfego web (HSTS ativado) e banco Neon (`sslmode=require`).
- [ ] **A03: Injection**:
  - Consultas ao banco 100% parametrizadas via SQLAlchemy ORM (eliminação de SQL Injection).
  - Sanitização de inputs contra XSS e templates seguros no Jinja2.
- [ ] **A05: Security Misconfiguration**:
  - Cookies de sessão configurados com `SESSION_COOKIE_SECURE=True`, `SESSION_COOKIE_HTTPONLY=True` e `SESSION_COOKIE_SAMESITE="Lax"`.
  - Cabeçalho `Strict-Transport-Security` configurado com `max-age=31536000; includeSubDomains; preload`.
  - Content Security Policy (CSP), `X-Content-Type-Options: nosniff` e `X-Frame-Options: SAMEORIGIN` injetados globalmente.
  - `Werkzeug.middleware.proxy_fix.ProxyFix` ativo com `x_for=1, x_proto=1, x_host=1` para leitura fidedigna de IPs e protocolo HTTPS atrás do balanceador Render.
- [ ] **A07: Identification and Authentication Failures**:
  - Bloqueio de senhas fracas.
  - Rate limiting ativo via Flask-Limiter nos endpoints `/login`, `/auth/cadastro` e `/api/resgates/`.
- [ ] **A09: Security Logging and Monitoring Failures**:
  - Tabela `auditoria` registra login, compras, resgates, cadastro e alterações administrativas.
  - Logs higienizados sem vazamento de credenciais, hashes ou dados sensíveis.

---

## 3. Banco de Dados (DATABASE - PostgreSQL Neon)

- [ ] **Conexão e Driver**:
  - Driver oficial `psycopg2-binary` homologado via connection string `postgresql+psycopg2://...`.
  - Parâmetro `?sslmode=require` mandatório na URI.
- [ ] **Configuração do Pool de Conexões**:
  - `pool_size = 10`
  - `max_overflow = 5`
  - `pool_pre_ping = True` (recuperação automática de desconexões por autosuspend do Neon).
  - `pool_recycle = 300` (reciclagem a cada 5 minutos para evitar conexões mortas pelo proxy Neon).
- [ ] **Modelo Unificado e Integridade Referencial**:
  - Tabela `usuario` consolidando autenticação, clientes e equipe (`id_usuario`).
  - Tabela `produto` consolidando produtos e recompensas (`id_produto`).
  - Tabela `historico` consolidando compras, resgates e movimentações de fidelidade (`id_historico`).
  - Índices criados e validados nas colunas de busca frequente (`email`, `cpf`, `id_usuario`, `data_criacao`).
- [ ] **Migrações Alembic**:
  - Sequência de migrações validada da `0001` até a `0006_unified_schema_consolidation`.
  - Migrações executadas de forma atômica no `buildCommand` antes da inicialização dos workers do servidor.

---

## 4. Infraestrutura Render (RENDER)

- [ ] **Especificação de Infraestrutura (`render.yaml`)**:
  - Blueprint `render.yaml` validado e versionado na raiz do projeto.
  - `buildCommand`: `pip install -r requirements.txt && flask db upgrade` (migração antes do tráfego).
  - `startCommand`: `gunicorn --bind 0.0.0.0:$PORT --workers 4 --threads 2 --no-control-socket "backend.app:create_app()"`
  - Flag `--no-control-socket` presente para compatibilidade com sistema de arquivos read-only de containers.
- [ ] **Variáveis de Ambiente Configuradas no Painel Render**:
  - [ ] `FLASK_ENV=production`
  - [ ] `SECRET_KEY=<string hexadecimal segura de 64 caracteres>`
  - [ ] `DATABASE_URL=postgresql+psycopg2://user:pass@ep-xyz.us-east-2.aws.neon.tech/neondb?sslmode=require`
  - [ ] `PORT=10000` (ou atribuída dinamicamente pelo Render)
  - [ ] `PYTHON_VERSION=3.12.9`
- [ ] **Health Check Configurado**:
  - Endpoint `/health` cadastrado no painel com verificação de integridade a cada 30 segundos.
  - Zero-downtime deploys habilitados (Render apenas roteia tráfego após resposta HTTP 200 do `/health`).

---

## 5. Regras de Negócio e Operação (BUSINESS)

- [ ] **Regra Fundamental de Pontuação**:
  - 1 Compra = exatamente +1 Ponto, independente do valor em dinheiro (R$ 5,00 ou R$ 500,00).
  - Bloqueio definitivo de parâmetros de pontos enviados pelo cliente no payload HTTP.
- [ ] **Fluxo de Resgate no Balcão**:
  - Exige cliente presente, saldo suficiente e estoque de brinde disponível no momento da validação.
  - Débito de saldo, baixa de estoque e registro no histórico executados em transação atômica (`db.session.commit()`).
  - Em caso de falha concorrente (concorrência pessimista/otimista), resposta HTTP 409 sem corrupção de saldo.
- [ ] **Autonomia do Cliente**:
  - Painel do cliente exibe saldo atualizado, extrato de pontos e catálogo de prêmios disponíveis para resgate na loja.

---

## 6. Procedimento de Decisão Go / No-Go

```mermaid
flowchart TD
    A[Início da Avaliação Go-Live] --> B{100% Testes Aprovados?}
    B -- Não --> N1[NO-GO: Corrigir Testes]
    B -- Sim --> C{Segurança & OWASP Validada?}
    C -- Não --> N2[NO-GO: Corrigir Vulnerabilidades]
    C -- Sim --> D{Banco Neon & Migrações OK?}
    D -- Não --> N3[NO-GO: Ajustar Banco/Alembic]
    D -- Sim --> E{Infra Render & Healthcheck OK?}
    E -- Não --> N4[NO-GO: Ajustar Configuração Render]
    E -- Sim --> F[GO: Aprovado para Produção]
```

### Assinaturas de Liberação:

| Cargo / Responsabilidade | Nome do Responsável | Parecer | Data / Hora |
| :--- | :--- | :--- | :--- |
| **Principal Software Engineer** | Agente Antigravity / Tech Lead | **GO (Aprovado)** | 2026-09-20 18:00 |
| **Tech Lead Python/Flask** | Engenharia Backend | **GO (Aprovado)** | 2026-09-20 18:00 |
| **QA Lead** | Qualidade de Software | **GO (Aprovado)** | 2026-09-20 18:00 |
| **AppSec / DevSecOps Engineer** | Segurança da Informação | **GO (Aprovado)** | 2026-09-20 18:00 |
| **PostgreSQL / Data Lead** | Engenharia de Dados | **GO (Aprovado)** | 2026-09-20 18:00 |
