# Roteiro de Testes e Validação Pós-Deploy no Render — IT Clube

Este documento orienta a realização do **Smoke Test** e da homologação funcional do sistema **IT Clube** implantado no **Render**.

---

## 1. Roteiro de Smoke Test (Validação Imediata)

Execute os passos a seguir sequencialmente no ambiente implantado (`https://<sua-app>.onrender.com`):

### Passo 1: Health Check da Infraestrutura
Abra no terminal ou navegador:
```bash
curl -i https://<sua-app>.onrender.com/health
```
- **Resultado Esperado:**
  - Código HTTP `200 OK`
  - Resposta: `{"status":"ok"}`
  - Cabeçalho presente: `Strict-Transport-Security: max-age=31536000; includeSubDomains`

### Passo 2: Página Inicial e Redirecionamento Seguro
Acesse `https://<sua-app>.onrender.com/`.
- **Resultado Esperado:** Renderização limpa da página de login com seletor de perfil (Vendedora / Cliente) sem erros no console JavaScript.

### Passo 3: Cadastro Público de Cliente
Acesse a rota `/auth/cadastro`.
- Preencha os campos com um cliente fictício de testes (`Nome Teste Render`, telefone `11988880001`, senha `TesteForte2026!`).
- Envie o formulário.
- **Resultado Esperado:** Redirecionamento com mensagem de sucesso informando que a conta foi criada.

### Passo 4: Login do Cliente & Autoatendimento
- Faça login utilizando o telefone cadastrado no Passo 3.
- Acesse `/meuspontos`, `/historico`, `/recompensas` e `/perfil`.
- **Resultado Esperado:**
  - Saldo inicial exibido: **0 pontos**.
  - Extrato limpo sem transações.
  - Catálogo de prêmios com botões desabilitados (*"Pontos insuficientes"*).
  - Tentativa de alteração de nome em `/perfil` funciona perfeitamente.

### Passo 5: Teste de Bloqueio de Auto-Resgate (Segurança do Cliente)
Com o cliente logado no navegador, abra o Console de Desenvolvedor (F12) e tente efetuar um resgate diretamente via API:
```javascript
fetch('/api/resgates/', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({id_recompensa: 1})
}).then(r => console.log(r.status));
```
- **Resultado Esperado:** Código HTTP `403 Forbidden` (bloqueado pelo backend).

### Passo 6: Logout do Cliente
- Clique em **Sair** no menu superior.
- **Resultado Esperado:** Sessão encerrada e redirecionamento para o login.

### Passo 7: Login Operacional da Loja
- Faça login com as credenciais da proprietária criada no bootstrap (`admin_loja`).
- Acesse o **Dashboard da Loja** (`/dashboard`).
- **Resultado Esperado:** Métricas de retenção e clientes carregadas com sucesso.

### Passo 8: Registro de Compra no PDV (Regra +1 Ponto)
- No painel da loja, acesse a funcionalidade de pontuar compra no balcão.
- Busque o cliente pelo telefone `11988880001`.
- Registre uma compra no valor de **R$ 250,00**.
- **Resultado Esperado:** Mensagem de sucesso confirmando exatamente **+1 ponto** creditado.

### Passo 9: Reconciliação no Extrato do Cliente
- Em aba anônima, faça login novamente com o cliente `11988880001`.
- Acesse `/meuspontos`.
- **Resultado Esperado:** Saldo atualizado exatamente para **1 ponto**. O extrato exibe a compra registrada.

### Passo 10: Validação de Resgate Presencial no Balcão
*(Supondo saldo suficiente em homologação)*
- A vendedora seleciona a recompensa e valida o resgate para o cliente.
- **Resultado Esperado:** Saldo debitado, estoque decrementado no catálogo e registro imutável persistido no ledger `historico`.

---

## 2. Testes de Autorização e RBAC no Render

| Teste | Perfil | Ação / URL | Resultado Esperado |
| :--- | :--- | :--- | :--- |
| **Acesso a Clientes** | Cliente | `GET /api/clientes/` | `401 Unauthorized` ou `403 Forbidden` |
| **Acesso a Auditoria**| Cliente | `GET /api/auditoria/`| `401 Unauthorized` ou `403 Forbidden` |
| **Acesso a Funcionários**| Vendedora | `GET /api/funcionarios/` | `403 Forbidden` |
| **Acesso a Auditoria**| Vendedora | `GET /api/auditoria/`| `403 Forbidden` |
| **Acesso Total** | Proprietária | Todas as rotas | `200 OK` |

---

## 3. Monitoramento de Logs no Render

1. No painel do Render, selecione o serviço e clique na aba **Logs**.
2. O que verificar nos logs:
   - Presença da mensagem de boot do Gunicorn: `[INFO] Listening at: http://0.0.0.0:10000`.
   - Ausência de mensagens de erro como `OperationalError` ou `RuntimeError`.
   - **Garantia de Privacidade:** Certifique-se de que nenhuma senha, hash ou URL contendo a senha do banco de dados apareça nas linhas de log.
