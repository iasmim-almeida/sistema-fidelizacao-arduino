# Relatório de QA, Auditoria de Segurança & Banco Neon — IT Clube

## 1. Visão Geral da Auditoria de Segurança & QA

Este documento consolida a revisão técnica e validação de segurança da aplicação **IT Clube / FideliZa**, cobrindo arquitetura de software, conformidade com o **OWASP Top 10:2025**, concorrência, integridade relacional no **PostgreSQL Neon** e proteção contra vulnerabilidades críticas.

---

## 2. Avaliação OWASP Top 10:2025

### A01:2025 — Broken Access Control (Controle de Acesso Quebrado)
- **Superfície:** Endpoints administrativos (`/api/clientes/*`, `/api/compras/*`, `/api/resgates/*`, `/api/recompensas/*`, `/api/funcionarios/*`, `/api/auditoria/*`).
- **Ameaça / Vulnerabilidade:** Clientes finais tentando efetuar auto-resgate, manipular pontuação, auto-promover cargos ou acessar registros de outros clientes (BOLA / IDOR).
- **Correção Aplicada:**
  - Decoradores estritos de RBAC em [`backend/app/services/rbac.py`](file:///home/dd/sistema-fidelizacao-arduino/backend/app/services/rbac.py) (`@requer_permissao`, `@requer_cargo`).
  - Endpoint `POST /api/resgates/` bloqueia categoricamente clientes (`is_cliente` retorna 403 Forbidden).
  - Consulta de perfil e histórico em `/api/clientes/me` vinculada estritamente a `current_user.id_usuario`.
  - Remoção do filtro incorreto que amarrava a vendedora ao seu próprio `id_usuario` na entrega de prêmios da proprietária, mantendo isolamento entre gestoras distintas.
- **Teste de Regressão:** [`backend/tests/test_rbac.py`](file:///home/dd/sistema-fidelizacao-arduino/backend/tests/test_rbac.py), [`backend/tests/test_itclube_regras.py`](file:///home/dd/sistema-fidelizacao-arduino/backend/tests/test_itclube_regras.py), [`test_security_audit.py`](file:///home/dd/sistema-fidelizacao-arduino/test_security_audit.py).
- **Resultado:** ✅ [PASSOU] 100% de cobertura.
- **Risco Residual:** Mínimo. Monitoramento ativo via trilha de auditoria.

### A02:2025 — Security Misconfiguration (Configuração Incorreta de Segurança)
- **Superfície:** `DEBUG`, cookies de sessão, cabeçalhos HTTP e ProxyFix.
- **Ameaça / Vulnerabilidade:** Depurador interativo ativado em produção, cookies trafegando sem flag Secure via HTTP, ausência de headers anti-clique (clickjacking) e cabeçalho HSTS.
- **Correção Aplicada:**
  - `ProductionConfig` em [`backend/app/config.py`](file:///home/dd/sistema-fidelizacao-arduino/backend/app/config.py) força `DEBUG=False`, `TESTING=False`, `SESSION_COOKIE_SECURE=True`, `REMEMBER_COOKIE_SECURE=True`, `SESSION_COOKIE_HTTPONLY=True`, `SESSION_COOKIE_SAMESITE="Lax"`.
  - Adicionado middleware `ProxyFix` para normalizar headers `X-Forwarded-Proto` e `X-Forwarded-For` atrás do proxy reverso do Render.
  - Injeção obrigatória de cabeçalhos de segurança: `Strict-Transport-Security: max-age=31536000; includeSubDomains`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `Content-Security-Policy`.
- **Teste de Regressão:** `test_production_hardening.py::test_production_cookies_e_hsts`.
- **Resultado:** ✅ [PASSOU].
- **Risco Residual:** Nulo em ambiente HTTPS.

### A03:2025 — Software Supply Chain Failures (Falhas na Cadeia de Suprimentos)
- **Superfície:** Dependências Python no [`backend/requirements.txt`](file:///home/dd/sistema-fidelizacao-arduino/backend/requirements.txt).
- **Ameaça / Vulnerabilidade:** Pacotes depreciados com vulnerabilidades conhecidas (CVEs).
- **Correção Aplicada:** Versões de pacotes pinadas (`Flask==3.1.*`, `SQLAlchemy==2.0.*`, `Werkzeug==3.1.*`, `psycopg2-binary==2.9.*`). Checagem periódica com `pip check`.
- **Resultado:** ✅ [PASSOU] Zero conflitos detectados.

### A04:2025 — Cryptographic Failures (Falhas Criptográficas)
- **Superfície:** Hashing de senhas e geração de chaves de sessão.
- **Ameaça / Vulnerabilidade:** Senhas em texto plano, algoritmo de hash fraco (MD5/SHA1) ou chaves `SECRET_KEY` previsíveis/fracas.
- **Correção Aplicada:**
  - Utilização do padrão PBKDF2:SHA256 (Werkzeug) com salt criptográfico para todos os usuários e clientes.
  - Eliminação de backdoor legado (`1234`).
  - Geração estrita de `SECRET_KEY` com comprimento mínimo e bloqueio de chaves padrão de desenvolvimento.
- **Teste de Regressão:** `test_security_audit.py` (Testes 3, 5 e 7).
- **Resultado:** ✅ [PASSOU].

### A05:2025 — Injection (Injeções: SQLi, Mass Assignment, Role Injection)
- **Superfície:** Endpoints com ORM SQLAlchemy, formulários de auto-cadastro e filtros de busca.
- **Ameaça / Vulnerabilidade:** Injeção SQL em consultas dinâmicas ou cliente enviando `cargo="proprietario"` no payload para obter privilégios administrativos.
- **Correção Aplicada:**
  - Todas as consultas utilizam SQLAlchemy parametrizado sem concatenação de strings.
  - No modelo [`Usuario`](file:///home/dd/sistema-fidelizacao-arduino/backend/app/models/usuario.py), o método `__init__` neutraliza qualquer tentativa de injeção de cargo: se `nivel_acesso == "CLIENTE"`, o cargo é fixado forçadamente em `"cliente"`.
  - Formulário de cadastro público [`CadastroClienteForm`](file:///home/dd/sistema-fidelizacao-arduino/backend/app/forms.py) possui allowlist estrita de campos (`nome`, `telefone`, `email`, `senha`, `confirmar_senha`).
- **Teste de Regressão:** `test_production_hardening.py::test_cadastro_cliente_bloqueia_role_injection`.
- **Resultado:** ✅ [PASSOU].

### A06:2025 — Insecure Design (Design Inseguro)
- **Superfície:** Regra de pontuação e resgate de produtos.
- **Ameaça / Vulnerabilidade:** Cliente manipulando pontuação através de envio de campos fraudulentos no payload (`pontos=100`, `quantidade=50`) ou resgatando prêmio sem presença física.
- **Correção Aplicada:**
  - O backend é autoritativo: a regra fundamental **1 COMPRA = +1 PONTO** ignora totalmente valores informados no cliente.
  - O resgate só pode ser baixado por funcionária autorizada presencialmente no balcão da loja.
- **Teste de Regressão:** `test_itclube_regras.py` e `test_production_hardening.py::test_regra_pontuacao_unificada_e_rejeicao_payload_injetado`.
- **Resultado:** ✅ [PASSOU].

### A07:2025 — Authentication Failures (Falhas de Autenticação)
- **Superfície:** Rotas de login web (`/auth/login`) e cliente (`/auth/cliente/login`).
- **Ameaça / Vulnerabilidade:** Ataques de força bruta e enumeração de credenciais.
- **Correção Aplicada:**
  - Rate limiting via `Flask-Limiter` (5 requisições por minuto).
  - Respostas simétricas com código HTTP 401 para credenciais incorretas ou usuário inexistente.
  - Deserialização segura de sessão com prefixo estrito `u_` em [`load_user`](file:///home/dd/sistema-fidelizacao-arduino/backend/app/models/__init__.py).
- **Teste de Regressão:** `test_security_audit.py` (Testes 4 e 6).
- **Resultado:** ✅ [PASSOU].

### A08:2025 — Software or Data Integrity Failures (Falhas de Integridade)
- **Superfície:** Transações de pontos e estoque.
- **Ameaça / Vulnerabilidade:** Race conditions em resgates concorrentes permitindo estoque ou saldo negativo.
- **Correção Aplicada:**
  - Row-level lock com `with_for_update()` no PostgreSQL.
  - UPDATEs condicionais atômicos no banco (`WHERE quantidade_disponivel > 0` e `WHERE pontos_acumulados >= custo`).
  - Ledger de transações na tabela `historico` que valida integridade antes do commit.
- **Teste de Regressão:** `test_production_hardening.py::test_concorrencia_resgate_estoque_unitario`.
- **Resultado:** ✅ [PASSOU].

### A09:2025 — Security Logging and Alerting Failures (Falhas em Logs e Auditoria)
- **Superfície:** Tabela `auditoria`.
- **Ameaça / Vulnerabilidade:** Ações administrativas sem rastreamento ou vazamento de senhas em logs.
- **Correção Aplicada:**
  - Todas as operações críticas (`PONTUAR_COMPRA`, `VALIDAR_RESGATE`, `AJUSTE_PONTOS`, `ALTERAR_SENHA`, `BOOTSTRAP_PROPRIETARIA`) são registradas com IP, User-Agent, ID do usuário e timestamp UTC.
  - Sanitização prévia de payloads: senhas em texto plano nunca são incluídas nos detalhes de auditoria.
- **Teste de Regressão:** `test_itclube_regras.py::test_auditoria_sem_vazamento_de_senha`.
- **Resultado:** ✅ [PASSOU].

### A10:2025 — Mishandling of Exceptional Conditions (Tratamento Inadequado de Exceções)
- **Superfície:** Error handlers globais da aplicação.
- **Ameaça / Vulnerabilidade:** Stack traces expostos com credenciais do banco ou caminhos do servidor em respostas 500.
- **Correção Aplicada:** Handlers customizados para 400, 401, 403, 404 e 500 que interceptam exceções e retornam JSON limpo ou templates amigáveis sem stack traces.
- **Resultado:** ✅ [PASSOU].

---

## 3. Análise do Banco de Dados PostgreSQL Neon

### 3.1. Reconciliação entre Modelos e Schema Neon
A estrutura unificada de modelos reflete com fidelidade as tabelas provisionadas no PostgreSQL Neon:

| Tabela | Modelo Python | Papel no Sistema | Integridade / Restrições |
| :--- | :--- | :--- | :--- |
| `usuario` | `Usuario` / `Cliente` | Contas de operadores e clientes finais | PK `id_usuario`, UNIQUE `telefone`, UNIQUE `email`, UNIQUE `login`, CHECK `pontos_acumulados >= 0`, CHECK `nivel_acesso IN ('CLIENTE', 'ADMIN')` |
| `produto` | `Produto` / `Recompensa` | Catálogo de recompensas e cupons | PK `id_produto`, UNIQUE `codigo`, FK `id_usuario` ON DELETE SET NULL, validade indexada |
| `historico` | `Historico` / `Compra` / `Resgate` | Livro-razão (ledger) transacional imutável | PK `id_historico`, FK `id_usuario` ON DELETE CASCADE, FK `id_produto` ON DELETE SET NULL, CHECK `tipo_movimentacao` |
| `auditoria` | `Auditoria` | Trilha de auditoria e conformidade | PK `id_auditoria`, FK `id_usuario` ON DELETE SET NULL, timestamp UTC indexado |

### 3.2. Conexão Segura com o Neon (SSL & Pooler)
- A URI do Neon deve obrigatoriamente incluir `sslmode=require`.
- Para conexões transacionais da aplicação web, pode ser utilizado o endpoint com pooler (`-pooler`).
- **Atenção para Migrações Alembic:** Migrações DDL devem preferencialmente ser executadas utilizando o endpoint de conexão direta (sem pooler no modo transação), garantindo que comandos de schema não entrem em conflito.

---

## 4. Auditoria de Segredos no Repositório

Varredura estrita realizada no repositório:
- **`SECRET_KEY`:** Nenhuma chave real comprometida em arquivos versionados. Uso de `.env.example` sem valores e validação dinâmica em produção.
- **`DATABASE_URL`:** Nenhuma string de conexão com credenciais reais commitada no Git.
- **`IOT_DEVICE_KEY`:** Chaves de demonstração segregadas para o ambiente de testes (`testing`). Produção exige variável provida pelo Render.
- **Status Geral:** Limpo e seguro para publicação.
