# Catálogo de Endpoints da API REST — IT Clube

Todas as rotas de API residem sob o prefixo `/api/` ou `/auth/` e exigem autenticação prévia (sessão autenticada ou cabeçalho IoT).

---

## 1. Autenticação & Cadastro (`/auth/`)

### `POST /auth/login`
- **Público:** Vendedoras, Gerentes e Proprietárias.
- **Payload:** `{"identificador": "admin@loja.com", "senha": "..."}`
- **Resposta:** `200 OK` + Cookie de Sessão assinado (`u_<id>`).

### `POST /auth/cliente/login`
- **Público:** Clientes do programa.
- **Payload:** `{"telefone": "11999991111", "senha": "..."}`
- **Resposta:** `200 OK` + Cookie de Sessão assinado (`c_<id>`).

### `POST /auth/cadastro` (Web)
- **Público:** Novos clientes.
- **Form Data:** `nome`, `telefone`, `email`, `senha`, `confirmar_senha`, `csrf_token`.
- **Resposta:** `302 Redirect` para login com mensagem flash de sucesso.

### `POST /auth/logout`
- **Público:** Todos os usuários autenticados.
- **Resposta:** `200 OK` (limpa sessão do servidor e cookie).

---

## 2. Autoatendimento do Cliente (`/api/clientes/me`)

### `GET /api/clientes/me`
- **Permissão:** Exclusivo do cliente autenticado.
- **Resposta:** Dados cadastrais (`id_cliente`, `nome`, `telefone`, `email`, `pontos_acumulados`).

### `PUT /api/clientes/me`
- **Permissão:** Exclusivo do cliente autenticado.
- **Payload:**
  ```json
  {
    "nome": "Maria Silva Atualizada",
    "telefone": "11988887777",
    "email": "maria.nova@exemplo.com"
  }
  ```
- **Regra de Segurança:** Tentativas de enviar campos como `pontos` ou `saldo` são ignoradas. Unicidade de telefone e e-mail é validada.
- **Resposta:** `200 OK` + dados atualizados.

### `POST /api/clientes/me/alterar-senha`
- **Permissão:** Exclusivo do cliente autenticado.
- **Payload:**
  ```json
  {
    "senha_atual": "SenhaAntiga123!",
    "nova_senha": "NovaSenhaSegura2026!",
    "confirmar_senha": "NovaSenhaSegura2026!"
  }
  ```
- **Resposta:** `200 OK` (auditoria registrada sem exibir a senha).

---

## 3. Operação de Caixa & PDV (`/api/`)

### `POST /api/compras/`
- **Permissão:** Vendedora autenticada OU dispositivo IoT via cabeçalho `X-Device-Key`.
- **Payload:**
  ```json
  {
    "telefone": "11999991111",
    "valor": 75.50
  }
  ```
- **Regra de Negócio IT Clube:** Cada requisição confirmada adiciona **1 ponto** à conta do cliente, independente do valor.
- **Resposta:** `201 Created`
  ```json
  {
    "status": "sucesso",
    "pontos_adicionados": 1,
    "saldo_atualizado": 281,
    "compra": { "id_compra": 10, "pontos_gerados": 1, "valor": 75.50 }
  }
  ```

### `POST /api/resgates/`
- **Permissão:** Vendedora, Gerente ou Proprietária (clientes finais recebem `403 Forbidden`).
- **Payload:**
  ```json
  {
    "id_cliente": 1,
    "id_recompensa": 2
  }
  ```
- **Regra de Negócio:** Valida saldo e estoque de forma atômica no banco, debitando os pontos e decrementando o estoque disponível.
- **Resposta:** `201 Created`.

### `GET /api/recompensas/`
- **Permissão:** Qualquer usuário autenticado (vendedora ou cliente).
- **Resposta:** Lista de recompensas com `custo_pontos`, `tipo`, `validade`, `pode_resgatar` e `pontos_faltantes`.

---

## 4. Diagnóstico do Sistema

### `GET /health`
- **Público:** Orquestradores (Docker, Kubernetes) e balanceadores de carga.
- **Resposta:** `{"status": "ok"}` (`200 OK`).
