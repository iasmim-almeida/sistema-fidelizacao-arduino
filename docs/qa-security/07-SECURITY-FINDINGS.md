# 07 — Vulnerabilidades e Achados de Segurança (Security Findings)

> **Relatório histórico:** estados de correção devem ser confirmados no código atual.

Este documento cataloga todos os achados identificados durante a auditoria de segurança e code review, estruturados conforme o padrão corporativo de AppSec.

---

### Finding ID: SEC-FIND-01
- **Título**: Falha de Segregação de Autenticação entre Portais Administrativo e do Cliente
- **Severidade**: HIGH
- **Categoria**: OWASP A07:2021 — Identification and Authentication Failures / CWE-287
- **Arquivo**: [`backend/app/routes/auth.py`](file:///home/dd/sistema-fidelizacao-arduino/backend/app/routes/auth.py)
- **Endpoint**: `POST /auth/login` e `POST /auth/cliente/login`
- **Descrição**: O endpoint `/auth/login` (login da vendedora) verificava apenas se o usuário existia e se a senha conferia, sem checar se a conta pertencia de fato ao perfil `vendedora`/`ADMIN`. Da mesma forma, `/auth/cliente/login` verificava e-mail ou telefone sem validar se o usuário possuía o perfil `CLIENTE`.
- **Impacto**: Clientes podiam obter sessões com `tipo: "vendedora"` no portal administrativo, poluindo logs de auditoria e gerando inconsistências de sessão. Administradoras podiam autenticar no portal de cliente com comportamentos inesperados.
- **Cenário de Reprodução**:
  1. Enviar requisição `POST /auth/login` com as credenciais válidas de um cliente comum.
  2. Observar resposta HTTP 200 OK com payload `tipo: "vendedora"` e redirect para `/dashboard`.
- **Evidência**:
  ```python
  # Trecho vulnerável anterior em auth.py:
  usuario = Usuario.query.filter((Usuario.email == identificador) | (Usuario.login == identificador)).first()
  if usuario: # Não validava se usuario.is_vendedora
      if usuario.verificar_senha(senha):
          login_user(usuario)
  ```
- **Causa Raiz**: Ausência de cláusula de validação do atributo de papel/perfil (`is_vendedora` e `is_cliente`) antes de concluir o `login_user()`.
- **Correção**:
  - Em `/auth/login`: Exigir estritamente `if usuario and getattr(usuario, "is_vendedora", False):`. Se não for vendedora, retornar HTTP 401 ("Credenciais de vendedora invalidas").
  - Em `/auth/cliente/login`: Exigir `if not cliente or not getattr(cliente, "is_cliente", False): return 401`.
- **Status**: **CORRIGIDO**
- **Teste de Regressão**: `QASecurityHardeningTestCase.test_cliente_bloqueado_no_login_vendedora` e `test_vendedora_bloqueada_no_login_cliente` em [`test_qa_security_hardening.py`](file:///home/dd/sistema-fidelizacao-arduino/backend/tests/test_qa_security_hardening.py).

---

### Finding ID: SEC-FIND-02
- **Título**: Validação Incompleta de Entrada no Cadastro de Clientes pelo Balcão
- **Severidade**: MEDIUM
- **Categoria**: OWASP A03:2021 — Injection / OWASP A04:2021 — Insecure Design / CWE-20
- **Arquivo**: [`backend/app/routes/clientes.py`](file:///home/dd/sistema-fidelizacao-arduino/backend/app/routes/clientes.py)
- **Endpoint**: `POST /api/clientes/`
- **Descrição**: Ao cadastrar clientes no balcão pela vendedora, o campo `nome` não possuía verificação de tamanho mínimo (`len < 3`) nem máximo (`len > 120`), o e-mail não era validado contra expressão regular de formato, e o campo `endereco` não possuía limitação de caracteres.
- **Impacto**: Possibilidade de inserção de dados inconsistentes, poluindo o banco com nomes monocaracteres (ex: `"A"`) ou textos excessivamente longos que poderiam degradar a renderização do frontend e causar estouro de campos.
- **Cenário de Reprodução**:
  1. Autenticar como vendedora.
  2. Enviar `POST /api/clientes/` com `{"nome": "X", "telefone": "11999990000", "senha": "SenhaValida1"}`.
  3. A requisição era aceita gerando cliente com nome inválido de 1 caractere.
- **Causa Raiz**: Validação de negócio presente na rota de edição (`PUT /api/clientes/<id>`), mas omitida na rota de criação (`POST /api/clientes/`).
- **Correção**:
  - Implementada validação de tamanho de nome: `if len(nome) < 3 or len(nome) > 120: return 400`.
  - Implementada validação de regex de e-mail: `re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email)`.
  - Truncamento e sanitização de endereço: `str(data["endereco"]).strip()[:255]`.
- **Status**: **CORRIGIDO**
- **Teste de Regressão**: `test_cadastrar_cliente_nome_curto_rejeitado`, `test_cadastrar_cliente_nome_muito_longo_rejeitado` e `test_cadastrar_cliente_formato_email_invalido_rejeitado` em [`test_qa_security_hardening.py`](file:///home/dd/sistema-fidelizacao-arduino/backend/tests/test_qa_security_hardening.py).

---

### Finding ID: SEC-FIND-03
- **Título**: Tratamento Inseguro de Tipos Não Inteiros no Parâmetro `id_cliente` em Compras
- **Severidade**: MEDIUM
- **Categoria**: OWASP A04:2021 — Insecure Design / CWE-1287
- **Arquivo**: [`backend/app/routes/compras.py`](file:///home/dd/sistema-fidelizacao-arduino/backend/app/routes/compras.py)
- **Endpoint**: `POST /api/compras/`
- **Descrição**: O endpoint recebia `data["id_cliente"]` diretamente na query do SQLAlchemy sem validação prévia de tipo. O envio de strings alfanuméricas, booleanos ou objetos causava falha interna do driver do banco, resultando em erro 500 (Internal Server Error) não tratado.
- **Impacto**: Exposição de falhas de servidor não tratadas (500) que degradam a confiabilidade e facilitam ataques de negação de serviço em consultas.
- **Cenário de Reprodução**:
  1. Enviar requisição `POST /api/compras/` com `{"id_cliente": "texto_invalido", "valor": "25.00"}`.
  2. O servidor retornava 500 em vez de 400 Bad Request.
- **Causa Raiz**: Falta de coerção segura de tipo com bloco `try/except (ValueError, TypeError)` antes da consulta SQL.
- **Correção**: Adicionada validação de tipo estrita retornando HTTP 400 ("id_cliente deve ser um número inteiro") para qualquer tipo não numérico.
- **Status**: **CORRIGIDO**
- **Teste de Regressão**: `QASecurityHardeningTestCase.test_compras_rejeita_id_cliente_tipo_invalido` em [`test_qa_security_hardening.py`](file:///home/dd/sistema-fidelizacao-arduino/backend/tests/test_qa_security_hardening.py).

---

### Finding ID: SEC-FIND-04
- **Título**: Checagem de Permissão Específica Granular Omitida em Endpoints de Compras
- **Severidade**: MEDIUM
- **Categoria**: OWASP A01:2021 — Broken Access Control / CWE-285
- **Arquivo**: [`backend/app/routes/compras.py`](file:///home/dd/sistema-fidelizacao-arduino/backend/app/routes/compras.py)
- **Endpoint**: `GET /api/compras/` e `POST /api/compras/`
- **Descrição**: As rotas de compras verificavam apenas a flag genérica `is_vendedora`, sem consultar as permissões específicas do RBAC (`pontos.visualizar` e `pontos.adicionar`), permitindo que colaboradoras sem essas permissões pontuassem ou vissem relatórios de compras.
- **Impacto**: Violação do princípio do menor privilégio (*Least Privilege*).
- **Causa Raiz**: Omissão das chamadas `current_user.tem_permissao(...)` no validador de sessão de pontuação e na listagem de compras.
- **Correção**: Implementada checagem explícita de `pontos.adicionar` no registro e `pontos.visualizar` na listagem de compras.
- **Status**: **CORRIGIDO**
- **Teste de Regressão**: `QASecurityHardeningTestCase.test_compras_listar_segrega_por_perfil_e_bloqueia_cliente_em_outro_id`.

---

### Finding ID: SEC-FIND-05
- **Título**: Ausência de Cabeçalhos de Segurança Modernos (`Permissions-Policy` e `Cross-Origin-Opener-Policy`)
- **Severidade**: LOW
- **Categoria**: OWASP A05:2021 — Security Misconfiguration / CWE-16
- **Arquivo**: [`backend/app/__init__.py`](file:///home/dd/sistema-fidelizacao-arduino/backend/app/__init__.py)
- **Endpoint**: Global (todas as respostas HTTP)
- **Descrição**: A aplicação configurava `X-Content-Type-Options`, `X-Frame-Options` e `CSP`, mas não especificava `Permissions-Policy` (para desabilitar o acesso indevido a recursos de hardware do navegador como geolocalização e câmera) nem `Cross-Origin-Opener-Policy` (COOP).
- **Impacto**: Vetores potenciais de ataques cross-origin ou abuso de APIs do navegador por scripts de terceiros.
- **Causa Raiz**: Omissão de headers de proteção nos interceptores de resposta.
- **Correção**: Cabeçalhos adicionados no handler `set_security_headers`:
  - `Permissions-Policy: geolocation=(), camera=(), microphone=(), payment=()`
  - `Cross-Origin-Opener-Policy: same-origin`
- **Status**: **CORRIGIDO**
- **Teste de Regressão**: `QASecurityHardeningTestCase.test_security_headers_presentes`.

---

### Finding ID: SEC-FIND-06
- **Título**: Método HTTP Inflexível no Endpoint de Logout (`/auth/logout`)
- **Severidade**: INFORMATIONAL
- **Categoria**: Usabilidade / Proteção de Sessão
- **Arquivo**: [`backend/app/routes/auth.py`](file:///home/dd/sistema-fidelizacao-arduino/backend/app/routes/auth.py)
- **Endpoint**: `/auth/logout`
- **Descrição**: O endpoint de logout aceitava exclusivamente requisições com o método `POST`. Caso o navegador fizesse um redirect via `GET` ou o usuário acessasse a URL diretamente, recebia HTTP 405 Method Not Allowed em vez de encerrar a sessão.
- **Impacto**: Experiência de uso degradada em encerramentos de sessão em caso de links diretos.
- **Correção**: O endpoint foi atualizado para aceitar `methods=["GET", "POST"]`, mantendo a destruição segura da sessão e auditoria.
- **Status**: **CORRIGIDO**
- **Teste de Regressão**: `QASecurityHardeningTestCase.test_logout_suporta_get_e_post`.
