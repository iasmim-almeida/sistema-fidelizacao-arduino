# 05 — Matriz de Controle de Acesso e Permissões (RBAC)

Esta matriz detalha o comportamento do sistema para cada perfil de usuário ao tentar interagir com os endpoints da aplicação.

---

## 1. Perfis de Usuário no Sistema

1. **Visitante (Anônimo)**: Usuário sem sessão ativa.
2. **Cliente Regular**: Consumidor final autenticado com cadastro ativo e senha definitiva.
3. **Cliente (1º Acesso)**: Consumidor final cadastrado pela vendedora que ainda precisa redefinir sua senha inicial (`precisa_trocar_senha = True`).
4. **Vendedora (Admin)**: Colaboradora interna com privilégios de operação de caixa e administração da loja.
5. **Terminal IoT (Hardware)**: Dispositivo físico ESP8266 com chave criptográfica HMAC pré-compartilhada.

---

## 2. Matriz de Acesso por Endpoint

| Endpoint | Método | Visitante | Cliente Regular | Cliente (1º Acesso) | Vendedora (Admin) | Terminal IoT |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `/` | `GET` | 200 (Login) | 302 (`/bemvindo`) | 302 (`/cliente/trocar-senha`) | 302 (`/dashboard`) | 200 |
| `/health` | `GET` | 200 | 200 | 200 | 200 | 200 |
| `/setup` | `GET/POST` | 200 / 302* | 302 (Index) | 302 (Index) | 302 (Index) | 403 |
| `/auth/login` | `POST` | 200 (Auth) | 401 (Negado) | 401 (Negado) | 200 (Auth) | 401 |
| `/auth/cliente/login` | `POST` | 200 (Auth) | 200 (Auth) | 200 (Troca obrigatória) | 401 (Negado) | 401 |
| `/auth/logout` | `GET/POST` | 302 (Index) | 200 / 302 | 200 / 302 | 200 / 302 | 401 |
| `/auth/me` | `GET` | 401 | 200 (Dados) | 200 (Dados) | 200 (Dados) | 401 |
| `/dashboard` | `GET` | 302 (Index) | 403 / 302 | 403 / 302 | 200 (Painel) | 401 |
| `/api/dashboard/estatisticas` | `GET` | 401 | 403 | 403 | 200 (JSON) | 401 |
| `/clientes` | `GET` | 302 (Index) | 403 / 302 | 403 / 302 | 200 (Painel) | 401 |
| `/api/clientes/` | `GET` | 401 | 200 (Próprio) | 403 / 302 | 200 (Lista geral) | 401 |
| `/api/clientes/` | `POST` | 401 | 403 | 403 | 201 (Cria cliente) | 401 |
| `/api/clientes/me` | `GET/PUT` | 401 | 200 (Próprio) | 403 / 302 | 403 (Uso vendedora) | 401 |
| `/api/clientes/me/alterar-senha` | `POST` | 401 | 200 | 200 (Desbloqueia) | 403 | 401 |
| `/api/clientes/<id>` | `GET` | 401 | 200 (Se id=meu) / 403 | 403 / 302 | 200 (Detalhes) | 401 |
| `/api/clientes/<id>` | `PUT` | 401 | 403 | 403 | 200 (Edita) | 401 |
| `/api/clientes/<id>/status` | `POST` | 401 | 403 | 403 | 200 (Ativa/Desativa) | 401 |
| `/api/clientes/<id>/pontos/ajuste` | `POST` | 401 | 403 | 403 | 200 (Crédito/Débito) | 401 |
| `/api/clientes/<id>/extrato` | `GET` | 401 | 200 (Se id=meu) / 403 | 403 / 302 | 200 (Extrato) | 401 |
| `/bemvindo` | `GET` | 302 (Index) | 200 (Área cliente) | 302 (`/trocar-senha`) | 302 (`/dashboard`) | 401 |
| `/meuspontos` | `GET` | 302 (Index) | 200 (Extrato) | 302 (`/trocar-senha`) | 302 (`/dashboard`) | 401 |
| `/recompensas` | `GET` | 302 (Index) | 200 (Catálogo) | 302 (`/trocar-senha`) | 302 (`/dashboard`) | 401 |
| `/historico` | `GET` | 302 (Index) | 200 (Compras) | 302 (`/trocar-senha`) | 302 (`/dashboard`) | 401 |
| `/perfil` | `GET` | 302 (Index) | 200 (Perfil) | 302 (`/trocar-senha`) | 302 (`/dashboard`) | 401 |
| `/cliente/trocar-senha` | `GET` | 302 (Index) | 200 (Troca) | 200 (Troca) | 302 (`/alterar-senha`)| 401 |
| `/api/compras/` | `GET` | 401 | 200 (Minhas compras) | 403 / 302 | 200 (Todas compras) | 401 |
| `/api/compras/` | `POST` | 401 | 403 | 403 | 201 (Pontua cliente) | 201 (Via X-Device-Key) |
| `/api/resgates/` | `GET` | 401 | 200 (Meus resgates) | 403 / 302 | 200 (Todos resgates) | 401 |
| `/api/resgates/` | `POST` | 401 | 403 | 403 | 201 (Valida resgate) | 401 |
| `/api/recompensas/` | `GET` | 401 | 200 (Válidas) | 403 / 302 | 200 (Todas) | 401 |
| `/api/recompensas/` | `POST` | 401 | 403 | 403 | 201 (Cria recompensa) | 401 |
| `/api/recompensas/<id>` | `GET` | 401 | 200 | 403 / 302 | 200 | 401 |
| `/api/recompensas/<id>` | `PATCH` | 401 | 403 | 403 | 200 (Edita catálogo) | 401 |
| `/funcionarios` | `GET` | 302 (Index) | 403 / 302 | 403 / 302 | 200 (Gestão equipe) | 401 |
| `/api/funcionarios/` | `GET/POST` | 401 | 403 | 403 | 200 / 201 | 401 |
| `/api/funcionarios/<id>` | `GET/PUT` | 401 | 403 | 403 | 200 | 401 |
| `/api/funcionarios/<id>/status` | `POST` | 401 | 403 | 403 | 200 | 401 |
| `/api/funcionarios/<id>/reset-senha` | `POST` | 401 | 403 | 403 | 200 | 401 |
| `/api/auditoria/` | `GET` | 401 | 403 | 403 | 200 (Consulta logs) | 401 |

*\* O endpoint `/setup` só é acessível quando não existe nenhuma vendedora/administradora cadastrada no sistema. Após o provisionamento inicial, fecha-se permanentemente e redireciona ao login com HTTP 403/302.*

---

## 3. Garantias de Proteção contra IDOR e Escalação de Privilégios

1. **Acesso Horizontal (Cliente A tentando acessar Cliente B)**:
   - Toda consulta por ID valida no backend se o `id_cliente` coincide com o usuário da sessão (`current_user.id_cliente == id`). Em caso de divergência, retorna **HTTP 403 Forbidden**.
2. **Acesso Vertical (Cliente tentando acessar Administração)**:
   - As rotas administrativas utilizam o decorator `@vendedora_required` e `@permissao_requerida`. Se um cliente requisitar qualquer API ou rota de funcionário, catálogo ou relatórios, a requisição é rejeitada no nível do roteador.
3. **Escalação de Privilégios via Atualização Cadastral**:
   - As rotas de atualização do cliente (`PUT /api/clientes/me` e `PUT /api/clientes/<id>`) ignoram qualquer campo de privilégio, status ativo ou saldo de pontos, aceitando exclusivamente dados de contato.
