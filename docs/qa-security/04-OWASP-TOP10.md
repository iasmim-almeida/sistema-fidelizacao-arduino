# 04 — Análise de Riscos: OWASP Top 10

> **Relatório histórico de QA:** não constitui certificação nem substitui a revisão atual em `../../SECURITY.md`.

Avaliação detalhada da aplicação em relação às categorias do **OWASP Top 10 (2021)**:

---

### A01:2021 — Broken Access Control (Quebra de Controle de Acesso)
- **Cenário**: Usuários acessando dados ou recursos de outros usuários (IDOR/BOLA) ou usuários comuns acessando rotas de administração.
- **Análise no Sistema**:
  - Acesso vertical: Endpoints de funcionários, auditoria, ajuste de pontos e relatórios são protegidos por `@vendedora_required` e `@permissao_requerida`. Clientes recebem HTTP 403.
  - Acesso horizontal (IDOR): A rota `/api/clientes/me` retorna estritamente os dados do cliente logado. Na rota `/api/clientes/<id>`, se o usuário autenticado for cliente e o `<id>` for diferente do seu, retorna HTTP 403 imediato.
  - Segregação de Portais: Corrigida falha onde clientes podiam autenticar na rota `/auth/login` de vendedora e vice-versa. Agora ambos validam ativamente `is_vendedora` e `is_cliente`.
- **Status**: **PROTEGIDO / VALIDADO EM TESTES**

---

### A02:2021 — Cryptographic Failures (Falhas Criptográficas)
- **Cenário**: Armazenamento de senhas em texto puro, algoritmos fracos ou transmissão desprotegida.
- **Análise no Sistema**:
  - Todas as senhas são armazenadas como hash PBKDF2-HMAC-SHA256 gerados pelo Werkzeug.
  - A chave secreta (`SECRET_KEY`) possui checagem de segurança em produção, emitindo alerta e gerando chave de alta entropia caso ausente ou insegura.
  - Comunicação com hardware IoT utiliza chave pré-compartilhada verificada com `hmac.compare_digest` para prevenir ataques de temporização (*timing attacks*).
  - HSTS ativado em conexões seguras com `max-age=31536000; includeSubDomains`.
- **Status**: **PROTEGIDO / VALIDADO EM TESTES**

---

### A03:2021 — Injection (Injeção de Código / SQL)
- **Cenário**: SQL Injection, Command Injection ou Template Injection permitindo extração de dados ou execução remota.
- **Análise no Sistema**:
  - SQLAlchemy ORM e Core são utilizados em 100% dos acessos ao banco de dados com parametrização de binds.
  - Inexistência de interpolação de strings em consultas SQL (`"SELECT ... " + valor`).
  - Nenhum uso de `os.system` ou `subprocess.Popen` com entradas controladas por usuários da aplicação web.
  - Auto-escaping ativo por padrão em templates Jinja2.
- **Status**: **PROTEGIDO / VALIDADO EM TESTES**

---

### A04:2021 — Insecure Design (Design Inseguro)
- **Cenário**: Falhas na modelagem de negócio, como resgate com saldo negativo ou geração arbitrária de pontos.
- **Análise no Sistema**:
  - Saldo não negativo garantido por validações em camada de serviço (`novo_saldo < 0`) e cláusulas SQL atômicas (`WHERE pontos_acumulados >= custo`).
  - Ledger contábil de pontos imutável com rastreamento de saldo anterior e posterior.
  - Bloqueio pessimista com `with_for_update()` para prevenir condições de corrida (*race conditions*) em acessos concorrentes.
  - Fluxo obrigatório de troca de senha no primeiro acesso para clientes cadastrados pela loja.
- **Status**: **PROTEGIDO / VALIDADO EM TESTES**

---

### A05:2021 — Security Misconfiguration (Configuração Insegura)
- **Cenário**: Modos de debug ativados em produção, headers de segurança ausentes ou stack traces expostos.
- **Análise no Sistema**:
  - Handlers de erro customizados para 400, 401, 403, 404 e 500 mascaram exceções internas.
  - `DEBUG = False` na configuração de produção (`ProductionConfig`).
  - Cabeçalhos de segurança implementados: `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, `Referrer-Policy`, `Content-Security-Policy`, `Permissions-Policy` e `Cross-Origin-Opener-Policy`.
- **Status**: **PROTEGIDO / VALIDADO EM TESTES**

---

### A06:2021 — Vulnerable and Outdated Components (Componentes Desatualizados)
- **Cenário**: Uso de bibliotecas de terceiros com vulnerabilidades públicas conhecidas (CVEs).
- **Análise no Sistema**:
  - Dependências principais em versões estáveis e recentes: Flask 3.1.3, Flask-SQLAlchemy 3.1.1, WTForms 3.2.2, Flask-WTF 1.3.0, Flask-Limiter 4.1.1, Gunicorn 22.0.0.
  - Sem uso de bibliotecas depreciadas ou com vulnerabilidades críticas ativas.
- **Status**: **PROTEGIDO / VALIDADO EM TESTES**

---

### A07:2021 — Identification and Authentication Failures (Falhas de Autenticação)
- **Cenário**: Ataques de força bruta, senhas fracas, sessões fixas ou enumeração de usuários.
- **Análise no Sistema**:
  - Rate limiting ativo via Flask-Limiter (10 requisições/min nos logins; 5/min no cadastro).
  - Respostas uniformes de erro em falhas de login de clientes e vendedoras para impossibilitar a enumeração de contas (CWE-204).
  - Políticas de complexidade e bloqueio de senhas comuns (`SENHAS_COMUNS_BLACKLIST`).
  - Sessão completamente destruída no logout (`logout_user()` e `session.clear()`).
- **Status**: **PROTEGIDO / VALIDADO EM TESTES**

---

### A08:2021 — Software and Data Integrity Failures (Falhas de Integridade)
- **Cenário**: Desserialização insegura de objetos (ex: pickle/yaml) ou aceitação de parâmetros arbitrários.
- **Análise no Sistema**:
  - Ausência de serializadores inseguros. Todas as trocas de dados ocorrem via JSON nativo parseado de forma segura.
  - Proteção contra *Mass Assignment*: dicionários de entrada possuem whitelist estrita de campos aceitos (ex: `CHAVES_PERMITIDAS` em resgates).
- **Status**: **PROTEGIDO / VALIDADO EM TESTES**

---

### A09:2021 — Security Logging and Monitoring Failures (Falhas em Logs e Monitoramento)
- **Cenário**: Eventos críticos de segurança não são registrados ou credenciais são salvas nos logs.
- **Análise no Sistema**:
  - Trilha de auditoria persistida no banco via [`Auditoria`](file:///home/dd/sistema-fidelizacao-arduino/backend/app/models/auditoria.py).
  - Eventos registrados: logins, tentativas falhas, alteração de status de contas, ajustes manuais de pontos, compras, resgates e cadastros.
  - Mecanismo de sanitização automática (`sanitizar_detalhes`) expurga chaves de senhas, hashes, segredos e tokens antes de gravar no log.
- **Status**: **PROTEGIDO / VALIDADO EM TESTES**

---

### A10:2021 — Server-Side Request Forgery (SSRF)
- **Cenário**: O servidor busca recursos de URLs controladas pelo usuário, expondo a rede interna ou metadados de nuvem.
- **Análise no Sistema**:
  - A aplicação não aceita nem processa parâmetros de URL para busca externa ou webhooks abertos.
  - Não há requisições HTTP de saída disparadas dinamicamente com base em dados do cliente.
- **Status**: **NÃO APLICÁVEL / SEGURO POR DESIGN**
