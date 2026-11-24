# Checklist de Produção (Production Readiness Checklist) — FideliZa / IT Clube

> **Checklist histórico:** não autoriza deploy nem migração. O procedimento vigente está em `DEPLOY_RENDER.md`.

Este checklist operacional e de segurança deve ser executado e validado formalmente antes da liberação do tráfego para usuários finais no ambiente Render + PostgreSQL Neon.

---

## 1. Configuração e Variáveis de Ambiente

- [ ] **`FLASK_ENV=production`**:
  - `DEBUG = False` garantido estritamente em tempo de execução.
  - `TESTING = False`.
  - Página de erro amigável sem tracebacks do Werkzeug ou exposição de código-fonte.
- [ ] **`SECRET_KEY` Criptograficamente Forte**:
  - Variável de ambiente `SECRET_KEY` configurada no Render com no mínimo 64 caracteres hexadecimais (gerada via `python3 -c "import secrets; print(secrets.token_hex(32))"`).
  - Bloqueio fail-closed: aplicação recusa inicializar se `SECRET_KEY` for nula, vazia ou default de desenvolvimento (`raise ValueError`).
- [ ] **`DATABASE_URL` com Neon Connection Pooling**:
  - Connection string aponta para o endpoint com pooler PgBouncer do Neon (`ep-xyz-pooler...neondb`).
  - Driver `postgresql+psycopg2://` explícito e normalizado.
  - Parâmetro `?sslmode=require` presente na URL.
  - Pool do SQLAlchemy configurado com `pool_pre_ping=True`, `pool_recycle=300`, `pool_timeout=30`, `max_overflow=10`.
- [ ] **`INITIAL_SETUP_TOKEN` (Opcional / Recomendado)**:
  - Token seguro configurado nas variáveis de ambiente caso seja desejado blindar o acesso ao endpoint `/auth/setup` durante a janela inicial.

---

## 2. Banco de Dados e Migrações

- [ ] **Migrações Alembic Aplicadas com Sucesso**:
  - `flask --app wsgi:app db upgrade` executado no `buildCommand` antes de subir o servidor web.
  - Schema consolidado até a migração `0006_unified_schema_consolidation` sem erros de chave primária ou colunas duplicadas.
- [ ] **Auditoria de Conexão e Autosuspend**:
  - Aplicação recupera conexões sem lançar erro 500 mesmo após o Neon hibernar (`pool_pre_ping=True`).
- [ ] **Plano de Contingência de Banco de Dados**:
  - Procedimento documentado em `docs/ROLLBACK.md`.
  - Endpoint `/health` verifica conectividade com o banco via `SELECT 1` e retorna status 503 se o Neon estiver inacessível.

---

## 3. Fluxo de Bootstrap Seguro e Trava de Segurança

- [ ] **Setup Inicial Executado com Sucesso**:
  - Acesso a `/auth/setup` (com `setup_token` se exigido) permite criar a primeira vendedora administradora com senha forte (mínimo 8 caracteres, maiúscula, minúscula, dígito, caractere especial).
- [ ] **Trava de Segurança Ativa e Irreversível**:
  - Imediatamente após a criação do primeiro administrador, `sistema_precisa_setup()` retorna `False`.
  - Qualquer requisição `GET /auth/setup` é redirecionada para `/auth/login` com mensagem informativa.
  - Qualquer requisição `POST /auth/setup` é terminada com `403 Forbidden`.
  - Trava em memória (`threading.Lock`) e trava a nível de banco (`SELECT pg_advisory_xact_lock(...)`) impedem race conditions na criação concorrente de múltiplos administradores.

---

## 4. Segurança de Rede, Sessões e Aplicação (OWASP Top 10)

- [ ] **Cookies de Sessão Seguros**:
  - `SESSION_COOKIE_SECURE = True` (cookies apenas trafegam via HTTPS).
  - `SESSION_COOKIE_HTTPONLY = True` (cookies inacessíveis para scripts client-side / mitigação XSS).
  - `SESSION_COOKIE_SAMESITE = 'Lax'` (proteção contra CSRF cross-origin).
- [ ] **Proteção CSRF Ativa**:
  - Flask-WTF CSRFProtect ativo globalmente em todos os formulários (`POST`, `PUT`, `DELETE`).
  - Meta tags e tokens validados em todas as submissões.
- [ ] **Rate Limiting Ativo**:
  - Flask-Limiter protegendo rotas críticas (`/auth/login`, `/auth/setup`, `/api/resgates/`).
- [ ] **Headers de Segurança HTTP Ativos**:
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: SAMEORIGIN`
  - `Content-Security-Policy` ajustado para assets locais e CDNs aprovadas.
- [ ] **ProxyFix Configurado Adequadamente**:
  - `ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=0)`
  - Confiança apenas em 1 salto de proxy reverso (Render Edge) e desativação de `x_prefix` contra spoofing de caminho.

---

## 5. Servidor de Aplicação (WSGI / Gunicorn)

- [ ] **Gunicorn Multi-worker em Produção**:
  - Execução via `gunicorn wsgi:app --workers 3 --threads 2 --bind 0.0.0.0:$PORT --timeout 120 --no-control-socket`.
  - `wsgi.py` presente na raiz do repositório como entry point unificado.
  - Sem uso do servidor embutido do Flask (`flask run`) em produção.
- [ ] **Logs Estruturados e Limpeza**:
  - Ausência de senhas, tokens de autenticação, CPF ou dados sensíveis nos logs do stdout/stderr.
  - Remoção de comandos `print()` e debug interativo.

---

## 6. Procedimento de Validação Final

| Passo | Ação | Critério de Aceite | Status |
|---|---|---|---|
| 1 | Inspecionar painel do Render | Variáveis de ambiente configuradas corretamente | [ ] |
| 2 | Acompanhar logs de Build | `pip install` e `flask db upgrade` sem erros | [ ] |
| 3 | Acompanhar logs de Start | Gunicorn inicializado com 3 workers na porta `$PORT` | [ ] |
| 4 | Acessar `https://<seu-app>.onrender.com/health` | HTTP 200 OK com payload `{"status": "healthy", "database": "connected"}` | [ ] |
| 5 | Acessar `https://<seu-app>.onrender.com/auth/setup` | Carrega tela de setup (ou redireciona para login se admin já existir) | [ ] |
| 6 | Submeter cadastro de vendedora | Sucesso: admin criado e redirecionado para login | [ ] |
| 7 | Tentar acessar `GET /auth/setup` novamente | Redirecionamento 302 para `/auth/login` | [ ] |
| 8 | Tentar submeter `POST /auth/setup` via curl | HTTP 403 Forbidden imediato | [ ] |
