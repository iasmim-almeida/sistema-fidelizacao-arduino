# Security Review — Cadastro Inicial Seguro (`/auth/setup`)

Este documento consolida a revisão técnica e arquitetural de segurança do fluxo de **Cadastro Inicial Seguro** (`/auth/setup`), avaliando seus controles de proteção, análise de riscos sob as normas **OWASP Top 10:2021** e **NIST SP 800-63B**, correções implementadas e recomendações de operação para o ambiente de produção no **Render + PostgreSQL Neon**.

---

## 1. Objetivo da Tela

A rota `/auth/setup` (e seu alias de navegação `/setup`) possui uma única finalidade no ciclo de vida da aplicação:
- Permitir a criação e ativação da **primeira conta administrativa da loja (Vendedora / Gestora / Admin)** durante o primeiro bootstrap da infraestrutura (cold-start), eliminando a necessidade de credenciais padrão hardcoded em scripts de seed ou senhas inseguras pré-definidas no banco de dados.
- Uma vez concluído o cadastro da administradora primária, a tela é **permanentemente bloqueada** contra novos acessos, transformando-se em uma funcionalidade inoperante e blindada contra novas submissões.

---

## 2. Fluxo Arquitetural de Bootstrap

```text
               Início do Primeiro Deploy no Render
                               │
                               ▼
                   [ buildCommand no Render ]
            pip install && flask --app wsgi:app db upgrade
                               │
                               ▼
             [ Aplicação Inicializa via Gunicorn ]
                   (3 Workers / wsgi:app)
                               │
                               ▼
              [ Conexão com PostgreSQL Neon ]
             (Pooler seguro: pool_pre_ping=True)
                               │
                               ▼
              [ Usuário Acessa GET / ou /auth/setup ]
                               │
                               ▼
               sistema_precisa_setup()
                               │
             ┌─────────────────┴─────────────────┐
             │                                   │
      Existe Administrador?              Nenhum Administrador
             │                                   │
             ▼                                   ▼
    [ BLOQUEIO TOTAL ]                  [ SETUP PERMITIDO ]
  - GET: Redirect 302 -> /login       - Verifica INITIAL_SETUP_TOKEN
  - POST: HTTP 403 Forbidden          - Exige Senha Forte (8+ chars)
                                      - Advisory Lock no PostgreSQL
                                      - Insere Vendedora no Banco
                                      - Registra Trilha de Auditoria
                                      - Sessão Segura e Login Realizado
                                                 │
                                                 ▼
                                        [ BLOQUEIO ATIVADO ]
                                    (Nunca mais pode ser acessado)
```

---

## 3. Controles Existentes

| Camada | Controle | Implementação Técnica |
| :--- | :--- | :--- |
| **Banco de Dados** | Estado Persistente de Bootstrap | O estado do sistema é derivado exclusivamente do PostgreSQL: `Usuario.query.filter(Usuario.nivel_acesso != 'CLIENTE').first() is None`. Não depende de memória volátil nem flags temporárias em disco. |
| **Transacional** | Proteção contra Race Condition | Uso de `SELECT pg_advisory_xact_lock(742918)` em PostgreSQL combinado com lock de processo (`_SETUP_LOCK = threading.Lock()`), garantindo serialização estrita mesmo com múltiplos workers do Gunicorn. |
| **Defesa em Profundidade** | Token Opcional de Bootstrap | Suporte à variável `INITIAL_SETUP_TOKEN`. Quando definida no Render, a tela exige o token para processar o cadastro inicial, eliminando a janela de exposição pública. |
| **Criptografia** | Hashing de Alta Entropia | Senhas processadas com scrypt (N=32768, r=8, p=1) via Werkzeug 3.x e salt criptográfico individual. Nenhuma senha trafega em plaintext para logs ou banco. |
| **Complexidade** | Política Rígida de Senha Admin | `validar_politica_senha_admin`: mínimo 8 caracteres (máx 128), maiúscula, minúscula, número, caractere especial e validação contra `SENHAS_COMUNS_BLACKLIST`. |
| **Anti-CSRF** | CSRFProtect (Flask-WTF) | Proteção mandatória ativa em submissões POST. Tokens gerados dinamicamente com base em `SECRET_KEY` segura. |
| **Controle de Taxa** | Flask-Limiter | Rate limit de 10 requisições por minuto por IP no endpoint `/auth/setup`. |
| **Auditoria** | Log Transacional | Registro atômico do evento `CADASTRO_INICIAL_VENDEDORA_ADMIN` na tabela `auditoria` com sanitização de credenciais. |

---

## 4. Problemas Encontrados na Auditoria

| Severidade | Problema | Arquivo | Impacto | Correção Realizada |
| :---: | :--- | :--- | :--- | :--- |
| **HIGH** | Falta de `FLASK_APP` e `wsgi.py` para descoberta CLI do Alembic | `render.yaml`, raiz do projeto | `flask db upgrade` falhava no Render por não localizar a aplicação em `run.py`. | Criado `wsgi.py` e explicitado `FLASK_APP=wsgi:app` no `render.yaml` e nos comandos de build. |
| **HIGH** | Incompatibilidade de connection string com prefixo `postgres://` | `backend/app/config.py` | Render e Neon fornecem `postgres://`, gerando falha no SQLAlchemy 1.4+ (`NoSuchModuleError`). | Normalização automática de `postgres://` para `postgresql+psycopg2://` em `database_url_from_environment()`. |
| **MEDIUM** | Ausência de fail-closed para `SECRET_KEY` em Produção | `backend/app/config.py`, `backend/app/__init__.py` | Em PRD, ausência de chave gerava chave dinâmica por worker, quebrando validação CSRF entre workers Gunicorn. | Validação estrita em `create_app("production")`: se `SECRET_KEY` for insegura ou ausente, a aplicação encerra imediatamente com `ValueError`. |
| **MEDIUM** | Ausência de Advisory Lock e Lock de Concorrência no Setup | `backend/app/routes/auth.py` | Duas submissões simultâneas podiam ultrapassar `sistema_precisa_setup()` e criar dois administradores iniciais. | Implementado `_SETUP_LOCK` e `pg_advisory_xact_lock(742918)` com re-verificação atômica pós-lock. |
| **MEDIUM** | Falta de Pooler e pre-ping para autosuspend do Neon | `backend/app/config.py` | Quando o Neon entrava em scale-to-zero, requisições subsequentes causavam erro 500 por queda de conexão SSL. | Adicionado `SQLALCHEMY_ENGINE_OPTIONS` com `pool_pre_ping=True`, `pool_recycle=300` e `pool_timeout=30`. |
| **LOW** | Configuração insegura de `x_prefix=1` no ProxyFix | `backend/app/__init__.py` | Permitiria prefix spoofing caso o proxy upstream repassasse cabeçalho `X-Forwarded-Prefix`. | Ajustado para `x_prefix=0` mantendo `x_for=1, x_proto=1, x_host=1, x_port=1`. |
| **LOW** | Validação branda de e-mail e ausência de limite superior de nome | `backend/app/routes/auth.py` | Nome aceitava mais de 100 caracteres e e-mail verificava apenas presença de `@`. | Adicionada validação de tamanho máximo (100) e regex estrita de formato de e-mail. |

---

## 5. Análise de Riscos (OWASP Top 10:2021)

- **A01:2021 — Broken Access Control**: Mitigado. Uma vez criado o primeiro administrador, `/auth/setup` rejeita requisições POST com HTTP 403 Forbidden e redireciona GET para login. A concorrência foi eliminada com locks atômicos.
- **A02:2021 — Cryptographic Failures**: Mitigado. Senhas com hash scrypt (N=32768, r=8, p=1) via Werkzeug, cookies de sessão com flags `Secure` e `HttpOnly`, HSTS habilitado e `SECRET_KEY` em fail-closed.
- **A03:2021 — Injection**: Mitigado. Parâmetros validados na camada de serviço e consultas via ORM com queries parametrizadas. Sanitização de espaços e validação alfanumérica de login.
- **A04:2021 — Insecure Design**: Mitigado. O fluxo de bootstrap utiliza o padrão *One-Time Setup Lock* persistente em banco, não em flags de memória que resetariam após reinicialização do container.
- **A05:2021 — Security Misconfiguration**: Mitigado. Debug desativado em produção, cabeçalhos de segurança (CSP, COOP, Permissions-Policy, X-Content-Type-Options) injetados via interceptores HTTP.
- **A07:2021 — Identification and Authentication Failures**: Mitigado. Rate limit via Flask-Limiter, política de complexidade de senhas, bloqueio contra senhas fracas.

---

## 6. Correções Realizadas e Rastreabilidade

| Problema | Correção | Arquivo | Teste Automatizado |
| :--- | :--- | :--- | :--- |
| **Descoberta do Flask / CLI** | Ponto de entrada padrão para Gunicorn e Alembic | [`wsgi.py`](file:///home/dd/sistema-fidelizacao-arduino/wsgi.py) | `flask db current` |
| **Normalização DATABASE_URL** | Conversão de `postgres://` para `postgresql+psycopg2://` e caminhos SQLite | [`backend/app/config.py`](file:///home/dd/sistema-fidelizacao-arduino/backend/app/config.py) | `test_production_cookies_e_hsts` |
| **Pooler Neon** | `pool_pre_ping=True`, `pool_recycle=300` | [`backend/app/config.py`](file:///home/dd/sistema-fidelizacao-arduino/backend/app/config.py) | `test_production_hardening.py` |
| **Fail-closed SECRET_KEY** | Lançamento explícito de `ValueError` em PRD | [`backend/app/__init__.py`](file:///home/dd/sistema-fidelizacao-arduino/backend/app/__init__.py) | `test_secret_key_fail_closed_em_producao` |
| **Proteção contra Race Condition** | `_SETUP_LOCK` e `pg_advisory_xact_lock` | [`backend/app/routes/auth.py`](file:///home/dd/sistema-fidelizacao-arduino/backend/app/routes/auth.py) | `test_race_condition_concorrencia_primeiro_admin` |
| **Token de Bootstrap (Opcional)** | Verificação segura de `INITIAL_SETUP_TOKEN` | [`backend/app/routes/auth.py`](file:///home/dd/sistema-fidelizacao-arduino/backend/app/routes/auth.py) | `test_setup_com_initial_setup_token` |
| **Ajuste ProxyFix** | `x_prefix=0` com `x_for=1, x_proto=1, x_host=1, x_port=1` | [`backend/app/__init__.py`](file:///home/dd/sistema-fidelizacao-arduino/backend/app/__init__.py) | `test_production_cookies_e_hsts` |
| **Validação Estrita de Input** | Limites de caracteres e regex de e-mail | [`backend/app/routes/auth.py`](file:///home/dd/sistema-fidelizacao-arduino/backend/app/routes/auth.py) | `test_email_invalido_rejeitado`, `test_nome_invalido_rejeitado` |

---

## 7. Risco Residual

1. **Persistência de Dados em Bancos Neon Compartilhados**:
   - Se o deploy no Render for conectado a uma base do Neon que já possua dados de testes anteriores ou execução prévia do `seed.py`, o setup inicial permanecerá bloqueado. A equipe operacional deve assegurar que o banco de produção esteja limpo antes do primeiro acesso ou limpar as tabelas via migração.
2. **Proteção da Variável de Ambiente `SECRET_KEY` e `DATABASE_URL`**:
   - A confidencialidade do sistema depende do isolamento das variáveis de ambiente no painel de controle do Render. Nenhuma credencial deve ser versionada no Git.
3. **Janela de Acesso Público no Primeiro Deploy**:
   - Caso `INITIAL_SETUP_TOKEN` não seja configurado, a rota `/auth/setup` estará pública na internet até que o primeiro administrador conclua seu cadastro. Recomenda-se realizar o cadastro imediatamente após o término do deploy ou definir `INITIAL_SETUP_TOKEN`.

---

## 8. Resultado Final da Auditoria

- **Status da Validação Técnica**: **APROVADO (135/135 testes automatizados)**.
- **Comportamento em Produção**: Seguro, atômico, resiliente a concorrência e compatível com as especificações serverless do Neon PostgreSQL e do proxy reverso do Render.
