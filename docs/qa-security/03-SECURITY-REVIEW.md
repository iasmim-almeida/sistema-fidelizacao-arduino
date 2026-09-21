# 03 — Revisão de Código e Arquitetura de Segurança

Esta revisão de segurança examina a fundo os mecanismos de defesa em profundidade implementados na aplicação.

---

## 1. Armazenamento e Criptografia de Senhas (OWASP A02)

- **Algoritmo de Derivação de Chave**: Werkzeug `generate_password_hash` utilizando **PBKDF2 com HMAC-SHA256** e salt criptográfico individual por conta.
- **Armazenamento**: O campo `senha_hash` possui tamanho `VARCHAR(255)`. Senhas em texto puro **nunca** são persistidas no banco ou escritas em logs.
- **Políticas de Complexidade**:
  - **Administração/Vendedoras**: Mínimo 8 caracteres (máximo 128), contendo letra minúscula, maiúscula, número e caractere especial, além de checagem contra blacklist de senhas comuns (`SENHAS_COMUNS_BLACKLIST`).
  - **Clientes**: Mínimo 8 caracteres (máximo 64), exigindo letras e números e rejeitando senhas fracas.
- **Proteção contra ReDoS / Hash DoS**: Limite rígido no tamanho das senhas recebidas para evitar consumo excessivo de CPU.

---

## 2. Gerenciamento de Sessão e Cookies (OWASP A07)

- **Identificadores de Sessão**:
  - Sessões gerenciadas pelo Flask-Login com identificadores seguros com prefixos tipados: `u_<id>` para operadores e `c_<id>` para clientes, eliminando qualquer colisão ou escalação de privilégios via ID numérico simples.
- **Flags de Segurança dos Cookies**:
  - `SESSION_COOKIE_HTTPONLY = True`: Impede que scripts JavaScript (via XSS) acessem o cookie de sessão.
  - `SESSION_COOKIE_SAMESITE = "Lax"`: Mitiga requisições forjadas entre sites (CSRF).
  - `SESSION_COOKIE_SECURE`: Ativado em produção para tráfego exclusivamente via HTTPS/TLS.
  - `REMEMBER_COOKIE_HTTPONLY = True` e `REMEMBER_COOKIE_SAMESITE = "Lax"`.
- **Invalidação de Sessão**:
  - O endpoint `/auth/logout` executa `logout_user()` e `session.clear()`, invalidando o cookie no servidor e registrando o evento de encerramento na auditoria.

---

## 3. Controle de Acesso e RBAC (OWASP A01)

- **Mecanismo de Permissões**: O módulo [`app.services.rbac`](file:///home/dd/sistema-fidelizacao-arduino/backend/app/services/rbac.py) define um sistema centralizado de controle de acesso baseado em papéis (RBAC).
- **Decorators de Rota**:
  - `@vendedora_required`: Bloqueia clientes e anônimos de acessar áreas de gestão da loja.
  - `@cliente_required`: Bloqueia operadores e anônimos de acessar áreas do cliente final, e intercepta clientes que ainda precisam redefinir a senha provisória (`precisa_trocar_senha`).
  - `@permissao_requerida(permissao)`: Valida permissões granulares por ação (ex: `clientes.criar`, `pontos.adicionar`, `resgates.validar`, `funcionarios.desativar`).
- **Segregação de Portais**:
  - Os endpoints `/auth/login` e `/auth/cliente/login` rejeitam ativamente perfis incompatíveis no momento da autenticação.

---

## 4. Integridade Concorrente do Saldo (Ledger Imutável) (OWASP A04)

- **Controle Pessimista**:
  - Toda movimentação de pontos (`compras.py`, `resgates.py` e `clientes.py:ajustar_pontos`) utiliza a cláusula `with_for_update()` no PostgreSQL, gerando bloqueio a nível de linha (*Row-Level Lock*) durante a transação.
- **Regras Matemáticas Invioláveis**:
  - Débitos condicionais no SQLite e PostgreSQL com cláusula `WHERE pontos_acumulados >= custo` impedem saldos negativos mesmo sob requisições paralelas.
  - O histórico unificado na tabela `historico` registra `saldo_anterior` e `saldo_posterior` em cada transação, permitindo auditoria contábil retroativa.

---

## 5. Proteção contra Injeção e Manipulação de Dados (OWASP A03 & Mass Assignment)

- **SQL Injection**: Ausência completa de concatenação direta de strings em comandos SQL. Todas as consultas utilizam SQLAlchemy ORM ou expressões Core com bind parameters nativos.
- **Mass Assignment**:
  - No resgate: O dicionário de entrada é estritamente filtrado por `CHAVES_PERMITIDAS = {"id_cliente", "telefone", "id_recompensa"}`. Atributos como `custo_pontos`, `descricao` ou `saldo_posterior` são rejeitados se enviados pelo cliente.
  - No catálogo de recompensas: O conjunto `CAMPO_PROTEGIDOS` impede alteração manual de IDs, proprietário ou datas de auditoria.

---

## 6. Proteção CSRF e Rate Limiting (OWASP A05 & A07)

- **Flask-WTF CSRF**: Ativo em toda a aplicação. Formulários Jinja2 incluem `<input type="hidden" name="csrf_token">` e chamadas assíncronas via `fetch()` utilizam o header `X-CSRFToken` obtido via meta tag.
- **Isenção Específica IoT**: Apenas o blueprint `/api/compras` possui isenção de CSRF, pois o terminal ESP8266 se autentica através de assinatura criptográfica HMAC no header `X-Device-Key`.
- **Rate Limiting**: Aplicado via Flask-Limiter nos endpoints sensíveis a força bruta:
  - `/auth/login`: 10/minuto;
  - `/auth/cliente/login`: 10/minuto;
  - `/auth/cadastro`: 5/minuto;
  - `/auth/alterar-senha`: 5/minuto.

---

## 7. Cabeçalhos de Segurança HTTP (Defense-in-Depth)

Implementados no interceptor `after_request` em [`app/__init__.py`](file:///home/dd/sistema-fidelizacao-arduino/backend/app/__init__.py):

```http
X-Content-Type-Options: nosniff
X-Frame-Options: SAMEORIGIN
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), camera=(), microphone=(), payment=()
Cross-Origin-Opener-Policy: same-origin
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com; font-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.gstatic.com data:; img-src 'self' data:; connect-src 'self'; frame-ancestors 'self';
Strict-Transport-Security: max-age=31536000; includeSubDomains (quando em canal TLS)
```

---

## 8. Tratamento de Erros e Prevenção de Vazamento de Dados (OWASP A09)

- Handlers customizados para status `400`, `401`, `403`, `404` e `500` asseguram que **nenhum stack trace ou mensagem interna de exceção** do banco de dados seja retornado aos usuários finais.
- A função `sanitizar_detalhes()` do serviço de auditoria remove chaves como `senha`, `senha_hash`, `token` e `secret` antes de persistir registros de auditoria em banco de dados.
