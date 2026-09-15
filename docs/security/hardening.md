# Engenharia de Segurança & Hardening — IT Clube

Este documento detalha as medidas de segurança aplicadas no sistema **IT Clube**, cobrindo o endurecimento de código, mitigação de ameaças do **OWASP Top 10** e as vulnerabilidades corrigidas.

---

## 1. Matriz de Mitigação de Vulnerabilidades

| ID | Classificação | Descrição Original do Risco | Mitigação Implementada no IT Clube | Status |
| :--- | :--- | :--- | :--- | :---: |
| **VULN-01** | BOLA / IDOR (API) | Endpoints `/api/clientes/`, `/api/compras/`, `/api/resgates/` abertos sem autenticação. | Inclusão de `@login_required` e `@permissao_requerida` em todas as rotas de API. Clientes comuns só leem seu próprio ID. | **Resolvido** |
| **VULN-02** | Credenciais Hardcoded | Verificação de senha em `Cliente.verificar_senha()` continha fallback aceitando `"1234"`. | Remoção total do backdoor; verificação estrita exclusivamente via `check_password_hash` (PBKDF2-SHA256). | **Resolvido** |
| **VULN-03** | Falha de Autenticação IoT | Terminal ESP8266 enviava requisições diretas sem credencial ou assinatura. | Implementada autenticação mútua via cabeçalho `X-Device-Key` com chave pré-compartilhada (`IOT_DEVICE_KEY`). | **Resolvido** |
| **VULN-04** | Escalação Vertical de Privilégio | Deserialização de sessão em `load_user()` aceitava IDs puros, colidindo clientes com administradores. | Prefixação obrigatória de sessões (`u_<id>` para funcionários e `c_<id>` para clientes). IDs sem prefixo são rejeitados. | **Resolvido** |
| **VULN-05** | Ausência de Anti-CSRF | Formulários web vulneráveis a Cross-Site Request Forgery. | Ativação global de `Flask-WTF` com tokens CSRF em formulários HTML e cabeçalho `X-CSRFToken` em requisições AJAX. | **Resolvido** |
| **VULN-06** | Enumeração de Usuários | Mensagens de erro distintas para "telefone não encontrado" e "senha incorreta". | Respostas unificadas com código HTTP 401 e mensagens idênticas ("Telefone ou senha inválidos"), mitigando força bruta. | **Resolvido** |
| **VULN-07** | Debug Mode em Produção | Execução em desenvolvimento expunha console interativo Werkzeug e traceback de erros. | Configuração rigorosa no `config.py` com `DEBUG=False` mandatório em produção, desligando interceptadores. | **Resolvido** |

---

## 2. Fronteiras de Segurança do Cliente

1. **Imutabilidade de Pontos pelo Cliente:**
   - Clientes não possuem permissão para invocar `/api/clientes/<id>/pontos/ajuste`.
   - O payload de autoatendimento (`PUT /api/clientes/me`) ignora deliberadamente chaves como `pontos`, `pontos_acumulados` e `saldo`.

2. **Bloqueio de Auto-Resgate:**
   - O endpoint `POST /api/resgates/` valida `getattr(current_user, "is_vendedora", False)`.
   - Clientes finais que tentam forçar o resgate direto via API recebem `403 Forbidden`. O resgate deve ser operado pela equipe da loja no caixa físico.

3. **Proteção de Dados Sensíveis em Auditoria:**
   - O módulo de auditoria (`Auditoria`) sanitiza os dicionários de detalhes antes da persistência, garantindo que senhas, confirmações de senha e tokens jamais sejam gravados em disco ou banco.

4. **Política de Senhas:**
   - Mínimo de 8 caracteres.
   - Presença obrigatória de letras e números.
   - Hash gerado via PBKDF2-HMAC-SHA256 com sal automático por usuário.
