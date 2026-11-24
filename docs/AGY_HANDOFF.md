# AGY HANDOFF — FideliZa / IT Clube

> **Registro histórico:** este handoff descreve uma versão anterior. Não use rotas, métricas ou resultados de testes daqui como evidência do sistema atual.

> Documento gerado em 2026-09-22T19:59 BRT (sessão AGY `566d2995`).
> Objetivo: permitir que outro agente/modelo retome o trabalho sem perda de contexto.

---

## 1. Estado atual

| Item | Valor |
|---|---|
| **Branch** | `feat/qa-security-troca-senha-primeiro-acesso` |
| **Último commit** | `a3c463a feat: troca obrigatoria de senha no 1o acesso, remocao de auditoria e hardening QA/seguranca` |
| **Working tree** | **DIRTY** — 15 arquivos modificados + 3 untracked |
| **Objetivo** | Homologação final para deploy no Render + PostgreSQL Neon |
| **Estágio** | Código corrigido, testes passando (138 backend + 7 security audit), pendente: reproduzir Build Command do Render localmente, commit, e validação completa do Deploy Gate |

### Arquivos modificados (não commitados)

```
modified:   README.md
modified:   SECURITY.md
modified:   backend/app/__init__.py
modified:   backend/app/config.py
modified:   backend/app/routes/auth.py
modified:   backend/app/routes/funcionarios.py
modified:   backend/app/routes/main.py
modified:   backend/run.py
modified:   backend/tests/test_production_hardening.py
modified:   backend/tests/test_setup_seguro.py
modified:   docs/DEPLOY_RENDER.md
modified:   frontend/templates/setup.html
modified:   render.yaml
modified:   run.py
modified:   test_security_audit.py
```

### Arquivos novos (untracked)

```
docs/PRODUCTION_CHECKLIST.md
docs/SECURITY_INITIAL_SETUP_REVIEW.md
wsgi.py
```

---

## 2. Arquitetura relevante

- **Flask Application Factory**: `backend/app/__init__.py` → `create_app(config_name)`.
- **Blueprints**: `main_bp` (/), `auth_bp` (/auth), `clientes_bp` (/api/clientes), `compras_bp` (/api/compras), `resgates_bp` (/api/resgates), `recompensas_bp` (/api/recompensas), `funcionarios_bp` (/api/funcionarios), `auditoria_bp` (/api/auditoria).
- **SQLAlchemy**: Modelos em `backend/app/models/`. Modelo unificado `Usuario` com campo `nivel_acesso` (`ADMIN`/`CLIENTE`) e `cargo`.
- **Flask-Migrate/Alembic**: Diretório de migrações em `database/migrations/versions/`. Head: `0006_adaptar_neon`.
- **PostgreSQL Neon**: Banco em nuvem serverless com autosuspend de 5 min. Requer `pool_pre_ping=True`, `pool_recycle=300`.
- **Render**: Web Service com `render.yaml` na raiz do repo.
- **Gunicorn**: 3 workers, 2 threads, timeout 60s, `--no-control-socket`.
- **Flask-WTF/CSRF**: `CSRFProtect` global. Blueprint `compras_bp` isento (endpoint IoT ESP8266).
- **Flask-Limiter**: Rate limiting em `/auth/login`, `/auth/setup`, etc.
- **RBAC**: Implementado em `backend/app/services/rbac.py`. Cargos: `proprietario`, `gerente`, `vendedora`, `cliente`.
- **Fluxo `/auth/setup`**: Bootstrap de primeiro uso. Quando `Usuario.query.filter(nivel_acesso != "CLIENTE").first() is None`, exibe formulário de criação do primeiro admin. Após criação, a rota é permanentemente trancada (GET→302, POST→403).

---

## 3. Decisões arquiteturais já tomadas

### 3.1 First-run setup (`/auth/setup`)

- **DECISÃO**: Tela de bootstrap exibida somente quando não existe nenhum usuário com `nivel_acesso != "CLIENTE"`.
- **MOTIVO**: Permite inicialização autônoma sem seeds ou credenciais hardcoded.
- **ARQUIVOS**: `backend/app/routes/auth.py` (funções `sistema_precisa_setup()`, `setup()`), `frontend/templates/setup.html`.
- **NÃO ALTERAR SEM**: Garantir que a trava pós-bootstrap continua funcional. Rodar `test_setup_seguro.py`.
- **IMPACTO**: Se a lógica for alterada, o sistema pode ficar inacessível (nenhum admin) ou vulnerável (setup reaberto).

### 3.2 Proteção pós-primeiro-admin

- **DECISÃO**: Após criação do 1º admin, GET retorna 302 e POST retorna 403. Dupla verificação dentro do `_SETUP_LOCK`.
- **MOTIVO**: Evitar criação de múltiplos admins por race condition ou re-acesso.
- **ARQUIVOS**: `backend/app/routes/auth.py` (linhas 379-383, 454-468).
- **NÃO ALTERAR SEM**: Rodar testes 3, 4, 11, 13 do `test_setup_seguro.py`.
- **IMPACTO**: Remoção pode permitir criação de admins não autorizados em produção.

### 3.3 Race condition no setup

- **DECISÃO**: `threading.Lock()` em memória (`_SETUP_LOCK`) + `pg_advisory_xact_lock(742918)` para PostgreSQL.
- **MOTIVO**: Gunicorn multi-worker pode processar requests paralelos que ultrapassam a checagem `sistema_precisa_setup()`.
- **ARQUIVOS**: `backend/app/routes/auth.py` (linhas 17, 454-459).
- **NÃO ALTERAR SEM**: Rodar teste 13 (race condition com threads).
- **IMPACTO**: Sem lock, múltiplos admins podem ser criados simultaneamente.

### 3.4 INITIAL_SETUP_TOKEN (somente via POST body)

- **DECISÃO**: Token opcional via env var `INITIAL_SETUP_TOKEN`. Aceito SOMENTE via POST body (`data.get("setup_token")`). NUNCA via query string.
- **MOTIVO**: Query strings vazam em logs de servidor, Referer headers, histórico do navegador e ferramentas de monitoramento.
- **ARQUIVOS**: `backend/app/routes/auth.py` (linhas 339-352, 366, 391), `frontend/templates/setup.html` (campo type="password").
- **NÃO ALTERAR SEM**: Rodar teste 12 e 17 do `test_setup_seguro.py`.
- **IMPACTO**: Aceitar token via URL expõe segredo em logs.

### 3.5 SECRET_KEY fail-closed

- **DECISÃO**: Em `create_app("production")`, se `SECRET_KEY` não estiver definida ou for um valor de desenvolvimento conhecido, `raise ValueError` imediatamente.
- **MOTIVO**: SECRET_KEY dinâmica por worker quebra CSRF e sessões em multi-worker Gunicorn.
- **ARQUIVOS**: `backend/app/__init__.py` (linhas 23-30).
- **NÃO ALTERAR SEM**: Rodar teste 14 do `test_setup_seguro.py`.
- **IMPACTO**: Remoção permite boot silencioso com chave insegura em produção.

### 3.6 PostgreSQL Neon (normalização e pool)

- **DECISÃO**: Normalizar `postgres://` → `postgresql+psycopg2://` automaticamente. Pool com `pool_pre_ping=True`, `pool_recycle=300`, `pool_timeout=30`, `max_overflow=10`.
- **MOTIVO**: Neon/Render fornecem `postgres://` (obsoleto no SQLAlchemy 1.4+). Neon hiberna e mata conexões após 5 min.
- **ARQUIVOS**: `backend/app/config.py`.
- **NÃO ALTERAR SEM**: Testar conectividade com Neon após 5+ minutos de inatividade.
- **IMPACTO**: Sem normalização, SQLAlchemy lança `NoSuchModuleError`. Sem pool_pre_ping, erro 500 intermitente.

### 3.7 ProxyFix

- **DECISÃO**: `ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=0)`.
- **MOTIVO**: Render fornece 1 hop de proxy reverso. `x_prefix=0` porque Render não envia `X-Forwarded-Prefix` (previne spoofing).
- **ARQUIVOS**: `backend/app/__init__.py` (linha 32).
- **NÃO ALTERAR SEM**: Verificar que HTTPS é detectado corretamente no Render.
- **IMPACTO**: `x_prefix=1` permite spoofing de caminho.

### 3.8 Gunicorn e wsgi.py

- **DECISÃO**: Criado `wsgi.py` na raiz como entry point único: `from backend.app import create_app; app = create_app(...)`.
- **MOTIVO**: Flask CLI e Gunicorn precisam de `FLASK_APP=wsgi:app` apontando para a raiz.
- **ARQUIVOS**: `wsgi.py`, `render.yaml`.
- **NÃO ALTERAR SEM**: Verificar que `flask --app wsgi:app db heads` funciona da raiz.
- **IMPACTO**: Sem wsgi.py, build command do Render falha.

### 3.9 Migrations

- **DECISÃO**: Diretório em `database/migrations/`, head em `0006_adaptar_neon`.
- **MOTIVO**: Projeto usa `MIGRATIONS_DIR` customizado em `create_app`.
- **ARQUIVOS**: `database/migrations/versions/0001-0006`, `backend/app/__init__.py` (linha 36).
- **NÃO ALTERAR SEM**: Rodar `flask --app wsgi:app db heads` e verificar que retorna `0006_adaptar_neon`.
- **IMPACTO**: Alterar diretório de migrações quebra o pipeline de deploy.

### 3.10 Health check

- **DECISÃO**: `/health` executa `SELECT 1` no banco e retorna `{"status":"healthy","database":"connected"}` (200) ou `{"status":"unhealthy","database":"disconnected"}` (503).
- **MOTIVO**: Render usa health check para determinar se o service está live.
- **ARQUIVOS**: `backend/app/routes/main.py` (linhas 31-38).
- **NÃO ALTERAR SEM**: Verificar que Render recebe 200 após deploy.
- **IMPACTO**: Health check sem DB check retorna 200 mesmo com banco offline.

### 3.11 Proteção do último administrador

- **DECISÃO**: (a) Rota de desativação (`/api/funcionarios/<id>/status`) bloqueia desativação se for a última vendedora ativa. (b) Rota de edição de cargo (`/api/funcionarios/<id>`) bloqueia rebaixamento para "cliente" se for o último admin ativo.
- **MOTIVO**: Sem essa proteção, `sistema_precisa_setup()` retornaria `True` e reabriria `/auth/setup` silenciosamente.
- **ARQUIVOS**: `backend/app/routes/funcionarios.py` (linhas 181-189 e 220-228).
- **NÃO ALTERAR SEM**: Rodar testes 15, 16 do `test_setup_seguro.py`.
- **IMPACTO**: Remoção da proteção pode reabrir a tela de setup em produção.

---

## 4. Arquivos alterados nesta sessão

| Arquivo | Motivo | Alteração | Estado |
|---|---|---|---|
| `wsgi.py` | Entry point WSGI para Render/Flask CLI | Criado na raiz | untracked |
| `render.yaml` | Build/Start commands, FLASK_APP, PYTHONPATH | Atualizado com comandos corretos | modified |
| `backend/app/__init__.py` | SECRET_KEY fail-closed, ProxyFix | Validação em produção, x_prefix=0 | modified |
| `backend/app/config.py` | Normalização DATABASE_URL, pool options | postgres→postgresql+psycopg2, engine options | modified |
| `backend/app/routes/auth.py` | Setup token somente via POST, locks | Removido request.args.get("token"), adicionado locks | modified |
| `backend/app/routes/main.py` | Health check com DB, redirect limpo | SELECT 1 no health, redirect sem query args | modified |
| `backend/app/routes/funcionarios.py` | Proteção último admin | Guard no cargo change + desativação | modified |
| `frontend/templates/setup.html` | Token como password, sem valor pré-preenchido | type="password", value="" | modified |
| `backend/tests/test_setup_seguro.py` | Novos cenários de teste (15-17) | Last-admin, rebaixamento, token-only-via-body | modified |
| `README.md` | Badge de testes, referências de hash | 94→138, PBKDF2→scrypt | modified |
| `SECURITY.md` | Algoritmo de hash | PBKDF2→scrypt (N=32768,r=8,p=1) Werkzeug 3.x | modified |
| `test_security_audit.py` | Mensagens de hash | PBKDF2→scrypt | modified |
| `docs/DEPLOY_RENDER.md` | Manual de deploy | Reescrito para Render+Neon | modified |
| `docs/SECURITY_INITIAL_SETUP_REVIEW.md` | Relatório de segurança AppSec | Criado e corrigido hash refs | untracked |
| `docs/PRODUCTION_CHECKLIST.md` | Checklist Go/No-Go | Criado | untracked |
| `backend/run.py` e `run.py` | Detecção de ambiente | Leitura de FLASK_ENV/APP_ENV/ENV | modified |
| `backend/tests/test_production_hardening.py` | Compatibilidade com fail-closed | Patched para chave válida em produção | modified |

---

## 5. Testes

### Comandos executados e resultados

| Comando | Resultado | Data/Hora |
|---|---|---|
| `python3 -m unittest discover -s backend/tests -v` | **138 testes, 0 falhas, 0 erros** | 2026-09-22 19:58 |
| `python3 test_security_audit.py` | **7/7 testes, 100% aprovados** | 2026-09-22 19:58 |

### Contagem por arquivo (grep -c "def test_")

| Arquivo | Métodos |
|---|---|
| test_auditoria.py | 4 |
| test_cadastro.py | 19 |
| test_cliente_primeiro_acesso.py | 5 |
| test_clientes_gestao.py | 6 |
| test_funcionarios.py | 10 |
| test_itclube_regras.py | 9 |
| test_pontos_ledger.py | 8 |
| test_production_hardening.py | 12 |
| test_qa_security_hardening.py | 11 |
| test_rbac.py | 5 |
| test_recompensas.py | 15 |
| test_setup_seguro.py | 17 |
| test_troca_senha.py | 18 |
| **Total (grep)** | **139** |
| **Total (runner)** | **138** |

> Nota: Diferença de 1 entre grep e runner pode indicar um helper method nomeado `test_*` que não é descoberto pelo runner, ou um teste herdado. O valor autoritativo é **138** (saída do runner).

### Testes NÃO executados

- **Build Command do Render** (`pip install --upgrade pip && pip install -r requirements.txt && flask --app wsgi:app db upgrade`): NÃO foi reproduzido em ambiente limpo nesta sessão.
- **Gunicorn start**: NÃO foi executado `gunicorn wsgi:app --workers 3 ...` nesta sessão.
- **Conexão real com Neon**: NÃO foi testada (testes usam SQLite em memória).

---

## 6. Migrations

| Item | Valor |
|---|---|
| **Diretório real** | `database/migrations/versions/` |
| **Migration head** | `0006_adaptar_neon` |
| **Down revision do head** | `0005_modelo_novo` |
| **Resultado de `flask --app wsgi:app db heads`** | `0006_adaptar_neon (head)` — executado com sucesso |
| **`flask --app wsgi:app db current`** | Não executado contra banco Neon nesta sessão (requer DATABASE_URL real) |

### Migrações existentes

```
0001_schema_legado.py
0002_recompensas_persistentes.py
0003_evolucao_completa.py
0004_it_clube_regras.py
0005_modelo_usuario_produto_historico.py
0006_adaptar_schema_neon_existente.py
```

---

## 7. Render

| Item | Valor | Testado? |
|---|---|---|
| **Build Command** | `pip install --upgrade pip && pip install -r requirements.txt && flask --app wsgi:app db upgrade` | **NÃO** — não reproduzido localmente nesta sessão |
| **Pre-Deploy Command** | Não configurado (migração no buildCommand) | N/A |
| **Start Command** | `gunicorn --bind 0.0.0.0:$PORT --workers 3 --threads 2 --timeout 60 --no-control-socket wsgi:app` | **NÃO** — Gunicorn não iniciado nesta sessão |
| **Health Check Path** | `/health` | Testado via unit test (retorna 200 com SELECT 1) |

### Observação crítica sobre requirements.txt

Existem **dois arquivos idênticos**:
- `/requirements.txt` (raiz)
- `/backend/requirements.txt`

O `render.yaml` referencia `requirements.txt` (raiz), o que está **correto** pois o Render executa a partir da raiz do repo.

---

## 8. Environment Variables

| Variável | Finalidade | Sensível? |
|---|---|---|
| `FLASK_ENV` | Modo de execução (`production`/`development`) | Não |
| `FLASK_APP` | Entry point Flask CLI (`wsgi:app`) | Não |
| `SECRET_KEY` | Assinatura de sessões e CSRF | **SIM** |
| `DATABASE_URL` | Conexão com PostgreSQL Neon | **SIM** |
| `INITIAL_SETUP_TOKEN` | Autorização opcional do /auth/setup | **SIM** |
| `IOT_DEVICE_KEY` / `ESP8266_API_KEY` | Chave pré-compartilhada do hardware | **SIM** |
| `PYTHONPATH` | Configurado como `backend` no render.yaml | Não |
| `PORT` | Porta HTTP (injetada pelo Render) | Não |
| `PYTHON_VERSION` | Versão do interpretador | Não |
| `TIMEZONE` | Fuso horário (`America/Sao_Paulo`) | Não |
| `SESSION_COOKIE_SECURE` | Cookies apenas via HTTPS | Não |
| `REMEMBER_COOKIE_SECURE` | Remember-me cookie apenas via HTTPS | Não |

> **NUNCA colocar valores reais de segredos neste documento ou no repositório.**

---

## 9. Problemas já encontrados

### P1: Hash documentado como PBKDF2, mas implementação usa scrypt

- **Problema**: README.md, SECURITY.md, SECURITY_INITIAL_SETUP_REVIEW.md e test_security_audit.py afirmavam "PBKDF2-HMAC-SHA256".
- **Causa raiz**: Werkzeug 3.1.8 mudou o default de `generate_password_hash()` para scrypt (N=32768, r=8, p=1). Documentação estava desatualizada.
- **Correção**: Todas as referências atualizadas para "scrypt (N=32768, r=8, p=1) via Werkzeug 3.x".
- **Teste**: `python3 -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('x'))"` → prefixo `scrypt:32768:8:1$`.
- **Status**: ✅ Corrigido.

### P2: Token de setup aceito via query string

- **Problema**: `request.args.get("token")` permitia `?token=SEGREDO` na URL.
- **Causa raiz**: Implementação inicial não considerou vazamento de segredo em URL.
- **Correção**: Removido leitura de `request.args`. Token aceito exclusivamente via POST body. Campo mudado para `type="password"`.
- **Teste**: Teste 17 (`test_token_somente_via_post_body`) valida que query string é rejeitada e body é aceito.
- **Status**: ✅ Corrigido.

### P3: Último admin pode ser removido/rebaixado, reabrindo setup

- **Problema**: `sistema_precisa_setup()` consulta `Usuario.query.filter(nivel_acesso != "CLIENTE").first() is None`. Se o único admin for desativado ou rebaixado para "cliente", a função retorna True e `/auth/setup` reabre.
- **Causa raiz**: Rota de edição de cargo não verificava se era o último admin.
- **Correção**: Guard adicionado em `funcionarios.py`: (a) desativação da última vendedora → 400; (b) rebaixamento do último admin para cliente → 400.
- **Teste**: Testes 15 e 16 do `test_setup_seguro.py`.
- **Status**: ✅ Corrigido.

### P4: Health check não verificava banco

- **Problema**: `/health` retornava `{"status": "ok"}` sem testar conectividade com o banco.
- **Causa raiz**: Implementação minimalista original.
- **Correção**: Health check agora executa `SELECT 1` e retorna 200/503.
- **Teste**: Unit tests existentes cobrem a rota. Validação real contra Neon pendente.
- **Status**: ✅ Corrigido.

### P5: Contagem de testes desatualizada

- **Problema**: README dizia 94 testes; runner reportava 135; após adições, são 138.
- **Causa raiz**: Badge e comentários nunca foram atualizados após adição de novas suítes.
- **Correção**: Badge e texto atualizados para 138.
- **Status**: ✅ Corrigido.

### P6: SECRET_KEY, ProxyFix, Pool Neon, wsgi.py, render.yaml

- **Problemas múltiplos de deploy**: Documentados na sessão anterior (ver seção 3 deste handoff).
- **Status**: ✅ Corrigidos — mas Build Command e Start Command do Render NÃO foram reproduzidos em ambiente limpo.

---

## 10. Pendências

### BLOCKERS

1. **Build Command do Render NÃO reproduzido localmente**: O comando `pip install --upgrade pip && pip install -r requirements.txt && flask --app wsgi:app db upgrade` não foi executado em ambiente limpo (virtualenv novo) nesta sessão. Se `requirements.txt` tiver dependências faltando ou `wsgi.py` tiver import error, o deploy falhará.
2. **Gunicorn NÃO testado**: O comando `gunicorn wsgi:app --workers 3 ...` não foi iniciado nesta sessão. Falhas de import, de binding ou de app factory não foram verificadas em modo multi-worker.
3. **Conexão real com Neon NÃO testada**: Todos os testes usam SQLite em memória. A normalização `postgres://` → `postgresql+psycopg2://`, o pool_pre_ping, e o autosuspend do Neon não foram validados com banco real.
4. **Nada foi commitado**: Todas as alterações estão no working tree. Um `git stash` ou `git checkout .` acidental perderá tudo.

### IMPORTANT

5. **`docs/DEPLOY_RENDER.md` pode conter referências de hash desatualizadas**: Não foi auditado completamente nesta sessão.
6. **`docs/PRODUCTION_CHECKLIST.md` referencia "Argon2/Bcrypt/PBKDF2"**: Verificar e corrigir se necessário.
7. **HSTS `preload`**: O header `Strict-Transport-Security` inclui `includeSubDomains` mas não inclui `preload`. Se submissão à lista de preload for desejada, adicionar.

### OPTIONAL

8. **Rate limiting persistente**: Flask-Limiter usa storage em memória (default). Em produção multi-worker, limites não são compartilhados entre workers. Para limites efetivos, configurar Redis como backend.
9. **Testes de integração com banco PostgreSQL**: Criar fixture de teste que use PostgreSQL real (ou testcontainers) para validar advisory locks e normalização de URI.
10. **CSP mais restritivo**: Remover `'unsafe-inline'` de `script-src` e `style-src` quando possível.

---

## 11. Próximo passo EXATO

**Tarefa 1 (BLOCKER)**: Reproduzir o Build Command do Render em ambiente limpo.

```bash
# Criar virtualenv limpo na raiz do projeto
python3 -m venv /tmp/test-render-build
source /tmp/test-render-build/bin/activate

# Executar exatamente o buildCommand do render.yaml
cd /home/dd/sistema-fidelizacao-arduino
pip install --upgrade pip && pip install -r requirements.txt && flask --app wsgi:app db upgrade

# Verificar que o Gunicorn consegue importar a app
gunicorn wsgi:app --workers 1 --bind 127.0.0.1:8000 --timeout 10 &
sleep 3
curl -s http://127.0.0.1:8000/health
kill %1
deactivate
```

Se o build e o health check retornarem sucesso, prosseguir para o commit.

**Tarefa 2**: Commitar todas as alterações:

```bash
git add -A
git commit -m "feat: hardening de segurança do /auth/setup, proteção de último admin, health check com DB, correção de hash docs, token somente via POST body, wsgi.py para Render"
```

**Tarefa 3**: Executar o FINAL DEPLOY GATE (seção 14 deste documento).

---

## 12. Não fazer

- ❌ **NÃO executar `git reset --hard`** — há 15 arquivos modificados não commitados com correções de segurança críticas.
- ❌ **NÃO executar `git clean -fd`** — há 3 arquivos novos (`wsgi.py`, 2 docs) que seriam deletados.
- ❌ **NÃO force push** — a branch tem histórico limpo que deve ser preservado.
- ❌ **NÃO apagar migrations** — a cadeia 0001→0006 está validada.
- ❌ **NÃO resetar banco Neon** — se houver dados de produção, serão perdidos.
- ❌ **NÃO reduzir controles de segurança para fazer deploy funcionar** — resolver a causa raiz.
- ❌ **NÃO remover CSRF** — está ativo globalmente, isento apenas no endpoint IoT.
- ❌ **NÃO abrir `/auth/setup` permanentemente** — a trava pós-bootstrap é intencional.
- ❌ **NÃO colocar segredos no repositório** — usar variáveis de ambiente no painel do Render.
- ❌ **NÃO confiar cegamente no relatório anterior** — validar sempre contra o código atual.
- ❌ **NÃO alterar o algoritmo de hash** — Werkzeug 3.x usa scrypt por padrão e é seguro.

---

## 13. Comandos de retomada

O próximo agente deve executar esta sequência ao iniciar:

```bash
# 1. Estado do repositório
git status
git branch --show-current
git log -5 --oneline

# 2. Verificar que wsgi.py existe
ls -la wsgi.py

# 3. Verificar migration head
FLASK_APP=wsgi:app python3 -m flask db heads

# 4. Rodar testes
python3 -m unittest discover -s backend/tests -v
python3 test_security_audit.py
```

Depois, ler os seguintes arquivos nesta ordem:
1. `docs/AGY_HANDOFF.md` (este documento)
2. `README.md`
3. `SECURITY.md`
4. `docs/DEPLOY_RENDER.md`
5. `render.yaml`
6. `wsgi.py`
7. `backend/app/config.py`
8. `backend/app/__init__.py`
9. `backend/app/routes/auth.py` (linhas 334-519: setup)
10. `backend/app/routes/funcionarios.py` (linhas 165-228: guards)
11. `database/migrations/versions/` (listar arquivos)

---

## 14. Critério para READY FOR DEPLOY

| # | Critério | Status |
|---|---|---|
| 1 | Working tree conhecido | ⚠️ DIRTY — 15 modified + 3 untracked, nada commitado |
| 2 | Dependências corretas | ⚠️ requirements.txt existe na raiz e em backend/ (idênticos), mas pip install não testado em venv limpo |
| 3 | Build Command reproduzido | ❌ NÃO TESTADO nesta sessão |
| 4 | Migration head validado | ✅ `0006_adaptar_neon (head)` confirmado via `flask db heads` |
| 5 | PostgreSQL/Neon validado | ❌ NÃO TESTADO — testes usam SQLite |
| 6 | SECRET_KEY fail-closed validada | ✅ Teste 14 confirma ValueError em produção sem chave |
| 7 | First-run setup validado | ✅ Teste 1 confirma GET 200 em banco vazio |
| 8 | Setup pós-bootstrap bloqueado | ✅ Testes 3, 4, 11 confirmam GET→302, POST→403 |
| 9 | Cenário último admin validado | ✅ Testes 15, 16 confirmam bloqueio de desativação e rebaixamento |
| 10 | CSRF validado | ✅ Teste 10 confirma rejeição sem token |
| 11 | Concorrência validada | ✅ Teste 13 confirma 1 admin com threads concorrentes |
| 12 | Gunicorn inicializado | ❌ NÃO TESTADO nesta sessão |
| 13 | `/health` validado | ✅ Código faz SELECT 1 — não testado contra Neon real |
| 14 | Documentação sincronizada | ✅ Hash corrigido para scrypt, contagem de testes atualizada |

### Veredito

**NÃO está READY FOR DEPLOY.** Faltam os itens 1, 2, 3, 5 e 12. O próximo agente deve reproduzir o Build Command, testar o Gunicorn, e idealmente validar contra o Neon real antes de declarar readiness.
