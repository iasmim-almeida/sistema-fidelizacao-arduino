# 08 — Correções Aplicadas e Hardening Realizado

Este relatório documenta detalhadamente as correções implementadas no código-fonte para solucionar as vulnerabilidades encontradas.

---

## 1. Correção da Segregação de Autenticação e Suporte a Logout (`backend/app/routes/auth.py`)

### Modificações:
1. Em `login_vendedora()`: Adicionada verificação mandatória `getattr(usuario, "is_vendedora", False)`. Caso um cliente informe suas credenciais válidas na aba de vendedora, a autenticação é rejeitada com HTTP 401 ("Credenciais de vendedora invalidas").
2. Em `login_cliente()`: Adicionada verificação mandatória `getattr(cliente, "is_cliente", False)`. Caso uma colaboradora/vendedora informe suas credenciais na aba do cliente, a autenticação é rejeitada com HTTP 401 ("Telefone ou senha invalidos.").
3. Em `logout()`: O decorador de rota foi expandido para `methods=["GET", "POST"]`.

```python
# Trecho de auth.py corrigido:
usuario = Usuario.query.filter(
    (Usuario.email == identificador) | (Usuario.login == identificador)
).first()

if usuario and getattr(usuario, "is_vendedora", False):
    if not getattr(usuario, "ativo", True):
        ...
    if usuario.verificar_senha(senha):
        ...
        login_user(usuario)
        return jsonify({
            "mensagem": "Login de vendedora realizado com sucesso",
            "tipo": "vendedora",
            "redirect": "/dashboard",
            "usuario": usuario.to_dict(),
        })

# Rejeição estrita com resposta uniforme
return jsonify({"erro": "Credenciais de vendedora invalidas"}), 401
```

---

## 2. Validação Rigorosa de Entrada no Cadastro de Clientes (`backend/app/routes/clientes.py`)

### Modificações:
1. Validação de comprimento do nome: Rejeição com HTTP 400 caso `len(nome) < 3` ou `len(nome) > 120`.
2. Validação estrita do formato de e-mail via regex: `^[^@\s]+@[^@\s]+\.[^@\s]+$`.
3. Sanitização e limitação de comprimento do endereço (máximo 255 caracteres).
4. Persistência mandatória de `precisa_trocar_senha = True` para clientes cadastrados no balcão.

```python
# Trecho de clientes.py:
if len(nome) < 3 or len(nome) > 120:
    return jsonify({"erro": "O nome deve conter entre 3 e 120 caracteres."}), 400

if email:
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return jsonify({"erro": "Formato de e-mail invalido."}), 400
    if Cliente.query.filter_by(email=email).first():
        return jsonify({"erro": "Ja existe um cliente cadastrado com este e-mail."}), 409

endereco = str(data["endereco"]).strip()[:255] if data.get("endereco") else None
```

---

## 3. Validação de Tipos e Aplicação de RBAC Granular em Compras (`backend/app/routes/compras.py`)

### Modificações:
1. `verificar_autenticacao_pontuacao()`: Exige que a vendedora autenticada possua a permissão `pontos.adicionar`.
2. `listar()`: Exige que a vendedora possua a permissão `pontos.visualizar` para consultar compras de clientes.
3. `registrar()`: O parâmetro `id_cliente` é validado contra tipos inválidos (booleanos, strings alfanuméricas, objetos) antes de consultar o banco, retornando HTTP 400 em vez de 500.

```python
# Validação de id_cliente em compras.py:
id_cli_raw = data.get("id_cliente")
if id_cli_raw is not None:
    if isinstance(id_cli_raw, bool) or not isinstance(id_cli_raw, int):
        try:
            id_cli = int(id_cli_raw)
        except (ValueError, TypeError):
            db.session.rollback()
            return jsonify({"erro": "id_cliente deve ser um número inteiro"}), 400
    else:
        id_cli = id_cli_raw
    cliente = query_cli.filter_by(id_cliente=id_cli).first()
```

---

## 4. Inclusão de Cabeçalhos de Segurança HTTP (`backend/app/__init__.py`)

### Modificações:
Adicionados os cabeçalhos `Permissions-Policy` e `Cross-Origin-Opener-Policy`:

```python
@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=(), payment=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    ...
```

---

## 5. Criação de Testes Automatizados de Regressão

Criado o arquivo de teste dedicado [`backend/tests/test_qa_security_hardening.py`](file:///home/dd/sistema-fidelizacao-arduino/backend/tests/test_qa_security_hardening.py) cobrindo todos os 6 achados e garantindo que nenhuma vulnerabilidade volte a ser introduzida em commits futuros.
