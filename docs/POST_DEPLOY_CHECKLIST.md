# Checklist Pós-Deploy — FideliZa / IT Clube

> **Checklist histórico e não executável:** referencia módulos e revisões removidos. Consulte `DEPLOY_RENDER.md`.

Este documento estabelece o protocolo operacional de validação obrigatória imediatamente após a conclusão do deploy na infraestrutura Render conectada ao banco PostgreSQL Neon.

---

## 1. Verificação de Infraestrutura e Status do Serviço

- [ ] **Status do Web Service no Dashboard Render**: O serviço deve constar como `Live` (ícone verde).
- [ ] **Build & Deploy Logs**:
  - Verificar se a etapa `buildCommand` executou sem erros:
    - Instalação de dependências: `pip install -r requirements.txt` (sucesso).
    - Execução de migrações: `flask db upgrade` (migrações aplicadas até a revisão `0006`).
  - Verificar se a etapa `startCommand` iniciou os workers Gunicorn:
    - `[INFO] Starting gunicorn 23.x / 26.x`
    - `[INFO] Listening at: http://0.0.0.0:10000` (ou porta `$PORT`)
    - 4 workers e 2 threads inicializados com sucesso.
    - Ausência de avisos de erro de socket (`--no-control-socket` ativo).
- [ ] **Consumo de Recursos (CPU / RAM)**:
  - Verificar no dashboard do Render se a memória RAM está estável (< 256 MB em repouso) e sem leaks de conexões.

---

## 2. Healthcheck e Conectividade HTTPS

- [ ] **Endpoint `/health`**:
  - Executar requisição HTTP GET:
    ```bash
    curl -i https://fideliza.onrender.com/health
    ```
  - Resposta esperada:
    - Status HTTP: `200 OK`
    - Payload JSON: `{"status": "ok", "database": "connected"}` (ou similar)
- [ ] **Certificado SSL / TLS**:
  - Verificar se a URL responde via HTTPS com certificado válido emitido pelo Let's Encrypt / Render.
  - Testar redirecionamento automático de HTTP para HTTPS:
    ```bash
    curl -I http://fideliza.onrender.com/health
    ```
    - Deve retornar `301 Moved Permanently` ou `308 Permanent Redirect` para `https://...`.

---

## 3. Inspeção de Cabeçalhos de Segurança (OWASP ASVS)

Executar no terminal:
```bash
curl -I https://fideliza.onrender.com/
```

Validar a presença obrigatória dos seguintes headers de resposta:
- [ ] `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`
- [ ] `X-Content-Type-Options: nosniff`
- [ ] `X-Frame-Options: SAMEORIGIN` (ou `DENY`)
- [ ] `Content-Security-Policy: default-src 'self'; ...`
- [ ] `X-XSS-Protection: 1; mode=block` (ou `0` com CSP moderno)

---

## 4. Inspeção de Cookies de Sessão

Ao realizar login ou carregar a página inicial:
- [ ] Flag `Secure` presente (cookie transmitido apenas por TLS).
- [ ] Flag `HttpOnly` presente (impede acesso via JavaScript / XSS).
- [ ] Atributo `SameSite=Lax` configurado (proteção contra CSRF cross-origin).

---

## 5. Conectividade com Banco de Dados Neon

- [ ] **Pool de Conexões**:
  - Pool SQLAlchemy configurado com `pool_size=10`, `max_overflow=5`, `pool_pre_ping=True`, `pool_recycle=300`.
  - Nenhuma ocorrência de `OperationalError: SSL connection has been closed unexpectedly` nos logs.
- [ ] **Autosuspend do Neon**:
  - Realizar uma requisição após 10 minutos de inatividade do banco para certificar que o `pool_pre_ping` reativa a conexão transparente e sem erro 500 para o usuário final.
- [ ] **Estado das Migrações**:
  - Acessar o Render Shell (ou log do build) e confirmar que a tabela `alembic_version` contém o hash correspondente à migração `0006_unified_schema_consolidation`.

---

## 6. Criação e Autenticação de Usuário Administrador (Owner)

- [ ] **Bootstrap do Proprietário Inicial**:
  - No Render Shell:
    ```bash
    flask create-owner --nome "Administrador Geral" --email "admin@itclube.com.br" --telefone "11999999999" --cpf "12345678901" --password "SenhaForteGerada123!"
    ```
  - Confirmar sucesso: `Usuário PROPRIETÁRIO admin@itclube.com.br criado com sucesso!`
- [ ] **Login do Proprietário**:
  - Acessar a tela `/login` e autenticar com as credenciais criadas.
  - Verificar redirecionamento correto para o dashboard administrativo (`/dashboard` ou `/perfil`).
  - Verificar registro da ação de login na tabela `auditoria`.

---

## 7. Validação de Regras de Negócio em Produção

### 7.1 Cadastro Público de Cliente (`/auth/cadastro`)
- [ ] Cadastrar novo cliente via formulário web.
- [ ] Inspecionar o banco/perfil:
  - `nivel_acesso` DEVE ser `CLIENTE`.
  - `cargo` DEVE ser `cliente` (mitigação de injeção de privilégios validada).
  - Saldo inicial deve ser `0` pontos.

### 7.2 Lançamento de Compra no PDV (Regra: 1 Compra = +1 Ponto)
- [ ] Autenticar como vendedora/proprietário no PDV.
- [ ] Registrar compra para o cliente recém-cadastrado no valor de R$ 150,00.
- [ ] Verificar saldo do cliente:
  - O saldo DEVE ter sido incrementado em exatamente **+1 ponto** (e NÃO 150 pontos).
- [ ] Testar tentativa de manipulação de payload via Postman/curl enviando `{"pontos": 50}`:
  - O backend DEVE forçar estritamente `pontos = 1`.

### 7.3 Bloqueio de Auto-Resgate por Cliente
- [ ] Autenticar com a sessão do cliente.
- [ ] Tentar enviar requisição `POST /api/resgates/` informando `id_recompensa`:
  - O backend DEVE responder com **HTTP 403 Forbidden** (`Apenas funcionários autorizados podem validar resgates no balcão`).

### 7.4 Resgate Autorizado no Balcão
- [ ] Com funcionário/proprietário autenticado:
  - Cliente possui 1 ponto. Recompensa selecionada custa 1 ponto e tem estoque = 1 unidade.
  - Executar resgate no balcão:
    - Retorno esperado: HTTP 201 Created.
    - Saldo do cliente: 0 pontos.
    - Estoque da recompensa: 0 unidades.
- [ ] Tentativa subsequente de resgate da mesma recompensa com estoque esgotado:
  - Retorno esperado: HTTP 409 Conflict (`Estoque insuficiente`).
- [ ] Tentativa de resgate com saldo insuficiente:
  - Retorno esperado: HTTP 400 Bad Request (`Saldo insuficiente`).

---

## 8. Auditoria e Higiene de Logs

- [ ] **Auditoria**:
  - Verificar que todas as operações (cadastro, compra, resgate, login) geraram registros na tabela `auditoria` com:
    - `id_usuario`, `acao`, `ip_address`, `user_agent`, `timestamp`.
- [ ] **Higiene de Logs (Log Sanitization)**:
  - Inspecionar as últimas 200 linhas de log no Render Dashboard:
    - [ ] NENHUMA senha em texto claro.
    - [ ] NENHUM token JWT ou de recuperação de senha.
    - [ ] NENHUMA connection string contendo a senha do banco PostgreSQL Neon (`postgres://...:***@...`).
    - [ ] NENHUM dado sensível de cartão de crédito ou CPF desnecessariamente exposto.
- [ ] **Rate Limiting**:
  - Testar envio de 15 requisições de login inválidas em sequência:
    - Retorno esperado: HTTP 429 Too Many Requests.

---

## 9. Aprovação Final do Checklist

| Papel | Nome | Status | Data |
| :--- | :--- | :--- | :--- |
| **Tech Lead** | Equipe FideliZa | [ ] Aprovado | ___/___/______ |
| **DevSecOps** | Engenharia Cloud | [ ] Aprovado | ___/___/______ |
| **Product Owner**| Gestão IT Clube | [ ] Aprovado | ___/___/______ |
