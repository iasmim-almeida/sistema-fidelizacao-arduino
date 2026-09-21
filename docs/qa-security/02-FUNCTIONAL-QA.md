# 02 — QA Funcional: Casos de Teste e Validações

Este documento detalha o plano de testes e os resultados dos testes funcionais executados na aplicação, englobando **Caminho Feliz (Happy Path)**, **Caminhos Negativos (Negative Path)** e **Casos Extremos (Edge Cases)**.

---

## 1. Módulo: Autenticação & Sessão

### 1.1 Login de Vendedora / Administradora (`/auth/login`)
- **Happy Path**: Vendedora ativa informa e-mail/login e senha corretos. Retorno HTTP 200 com token de sessão, `tipo: "vendedora"` e redirect para `/dashboard`.
- **Negative Path**:
  - Senha incorreta: Retorna HTTP 401 com erro genérico e registro em auditoria (`LOGIN_FALHA`).
  - Vendedora com conta desativada (`ativo=False`): Retorna HTTP 401 informando conta inativa.
  - Credenciais de cliente enviadas no endpoint de vendedora: Retorna HTTP 401 ("Credenciais de vendedora invalidas"), impedindo vazamento de perfil.
- **Edge Cases**:
  - E-mail em maiúsculas / minúsculas: Normalizado com sucesso via `.lower()`.
  - Espaços antes ou após o login: Removidos via `.strip()`.
  - Rate limiting: Acima de 10 tentativas por minuto, o cliente recebe HTTP 429 Too Many Requests.

### 1.2 Login de Cliente (`/auth/cliente/login`)
- **Happy Path**: Cliente informa telefone (com ou sem pontuação) e senha correta. Retorno HTTP 200, `tipo: "cliente"`, dados do cliente e redirect para `/bemvindo`.
- **Negative Path**:
  - Telefone inexistente ou senha errada: Retorno HTTP 401 uniforme ("Telefone ou senha invalidos."), prevenindo enumeração de usuários (CWE-204).
  - Conta desativada: Retorno HTTP 401 ("Conta desativada. Entre em contato com a loja.").
  - Credenciais de vendedora enviadas no endpoint de cliente: Bloqueado com HTTP 401 ("Telefone ou senha invalidos."), prevenindo login cruzado.
- **Edge Cases**:
  - Primeiro acesso com senha cadastrada pela loja (`precisa_trocar_senha=True`): Retorno indica `precisa_trocar_senha: True` e redireciona para `/cliente/trocar-senha`. Navegação em `/bemvindo` ou extrato fica bloqueada até a conclusão da troca.

---

## 2. Módulo: Gestão de Clientes

### 2.1 Cadastro de Cliente no Balcão (`POST /api/clientes/`)
- **Happy Path**: Vendedora autenticada envia `nome`, `telefone` válido, `email` opcional, `endereco` e `senha` inicial. Cliente criado no banco com status ativo, `pontos_acumulados: 0` e `precisa_trocar_senha: True`.
- **Negative Path**:
  - Nome com menos de 3 caracteres (ex: `"Oi"`): Rejeitado com HTTP 400.
  - Nome com mais de 120 caracteres: Rejeitado com HTTP 400.
  - Telefone inválido (ex: `"12345"` ou `"abc"`): Rejeitado com HTTP 400.
  - Telefone já cadastrado: Rejeitado com HTTP 409 Conflict.
  - E-mail com formato inválido (ex: `"usuario@semdominio"`): Rejeitado com HTTP 400.
  - Senha menor que 8 caracteres ou sem letras e números: Rejeitada com HTTP 400.
- **Edge Cases**:
  - Caracteres especiais, acentuação e emojis no nome: Preservados e tratados sem corrupção no UTF-8.
  - Telefone enviado formatado `(11) 98888-7777` vs puro `11988887777`: Normalizado para dígitos puros no banco de dados.

### 2.2 Troca de Senha Obrigatória no Primeiro Acesso (`/api/clientes/me/alterar-senha`)
- **Happy Path**: Cliente autenticado informa a senha temporária atual e define sua nova senha cumprindo a política. Retorna HTTP 200, atualiza `senha_hash`, define `precisa_trocar_senha = False` e libera acesso total ao sistema.
- **Negative Path**:
  - Senha atual incorreta: Retorna HTTP 400.
  - Nova senha igual à senha atual: Retorna HTTP 400 ("A nova senha deve ser diferente da senha atual.").
  - Confirmação não confere: Retorna HTTP 400.
  - Nova senha muito curta (< 8 caracteres) ou sem letras/dígitos: Rejeitada com HTTP 400.
- **Edge Cases**:
  - Tentativa do cliente de navegar diretamente para `/bemvindo`, `/meuspontos` ou `/historico` sem alterar a senha: O decorator `cliente_required` intercepta e redireciona imediatamente para `/cliente/trocar-senha`.

---

## 3. Módulo: Pontuação e Compras (PDV & IoT)

### 3.1 Pontuação de Compra (`POST /api/compras/`)
- **Happy Path**:
  - Vendedora logada informa `id_cliente` ou `telefone` e `valor`: Adiciona 1 ponto atômico no ledger de histórico com `tipo_movimentacao="COMPRA"`.
  - Terminal IoT envia payload com header `X-Device-Key` criptograficamente válido: Pontuação processada com sucesso via hardware.
- **Negative Path**:
  - Valor negativo (`valor: -50.00`): Rejeitado com HTTP 400 ("valor nao pode ser negativo").
  - Valor acima do teto (`valor: 9999999.00`): Rejeitado com HTTP 400 ("valor excede o limite maximo por transacao").
  - `id_cliente` de tipo inválido (ex: booleano ou texto não numérico): Rejeitado com HTTP 400 ("id_cliente deve ser um número inteiro").
  - Cliente inativo: Rejeitado com HTTP 400 ("Cliente está inativo. Pontuação não permitida.").
  - Requisição IoT sem chave ou com chave incorreta: Rejeitada com HTTP 401 ("Acesso nao autorizado para pontuacao.").
- **Edge Cases**:
  - Valor vazio ou nulo: Assumido `0.00` com crédito correto de 1 ponto (regra IT Clube: 1 compra = 1 ponto).
  - Concorrência de múltiplos caixas simultâneos para o mesmo cliente: Bloqueio pessimista `with_for_update()` enfileira e consolida os pontos sem perda de transação.

---

## 4. Módulo: Catálogo de Recompensas e Resgates

### 4.1 Validação e Baixa de Resgates (`POST /api/resgates/`)
- **Happy Path**: Vendedora valida o resgate no PDV informando o cliente e o `id_recompensa`. O sistema valida saldo >= custo, debita o saldo atômico do cliente, debita 1 unidade do estoque disponível, e gera o registro de resgate no ledger.
- **Negative Path**:
  - Cliente tentando resgatar diretamente pela API sem passar pela vendedora: Rejeitado com HTTP 403.
  - Saldo de pontos insuficiente: Rejeitado com HTTP 400 ("Pontos insuficientes").
  - Recompensa pausada ou esgotada: Rejeitado com HTTP 409 ("Recompensa temporariamente indisponível" / "Recompensa esgotada").
  - Recompensa com data de validade no passado: Rejeitado com HTTP 409 ("Recompensa expirada").
  - Tentativa de envio de campos extras (Mass Assignment, ex: `custo_pontos: 0`): Rejeitado com HTTP 400.
- **Edge Cases**:
  - Último item em estoque com 2 requisições simultâneas: Condicional SQL `quantidade_disponivel > 0` assegura que exatamente 1 requisição ganhe o item e a outra receba HTTP 409 (estoque nunca fica negativo).

---

## 5. Módulo: Gestão de Colaboradores / Funcionários

### 5.1 CRUD de Funcionários (`/api/funcionarios/`)
- **Happy Path**: Vendedora gestora cria nova colaboradora com nome, login único e senha forte. Retorna HTTP 201.
- **Negative Path**:
  - Login duplicado ou e-mail duplicado: Retorna HTTP 409 Conflict.
  - Senha que não cumpre a política administrativa (sem maiúscula, sem número ou sem caractere especial): Rejeitada com HTTP 400.
  - Desativação da própria conta logada: Rejeitada com HTTP 400 ("Você não pode desativar sua própria conta.").
  - Tentativa de desativar a única vendedora ativa no sistema: Rejeitada com HTTP 400 para prevenir bloqueio permanente da loja.
