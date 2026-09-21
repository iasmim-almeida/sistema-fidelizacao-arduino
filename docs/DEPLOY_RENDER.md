# Manual Completo de Deploy no Render & Integração PostgreSQL Neon

Este manual descreve a arquitetura, configuração, comandos e boas práticas para implantação do **IT Clube** no **Render Web Service** conectado ao **PostgreSQL Neon**.

---

## 1. Arquitetura de Nuvem

```text
       Usuário / Balcão PDV / ESP8266
                     │
                     ▼
           [ Render Edge HTTPS ]
             (TLS 1.3 / SSL Termination)
                     │
                     ▼
             [ Proxy Reverso ]
        (X-Forwarded-Proto / Port Routing)
                     │
                     ▼
           [ Web Service Linux ]
       Gunicorn (3 Workers / 2 Threads)
                     │
                     ▼
        [ Flask Application Factory ]
              (ProxyFix Ativo)
                     │
                     ▼
             [ SQLAlchemy ORM ]
                     │
                     ▼ (Conexão Segura TLS/SSL)
         [ PostgreSQL Neon Cloud ]
         (Tabelas unificadas & Ledger)
```

---

## 2. Parâmetros de Execução do Serviço Web no Render

- **Runtime:** `Python 3`
- **Region:** `Ohio (US East)` ou mais próxima do seu banco Neon.
- **Plan:** `Starter` (mínimo recomendado para suporte a concorrência).
- **Health Check Path:** `/health`
- **Build Command:**
  ```bash
  pip install --upgrade pip && pip install -r backend/requirements.txt && flask db upgrade
  ```
  > [!IMPORTANT]
  > Executar `flask db upgrade` no **Build Command** é uma decisão de engenharia intencional: garante que as migrações rodem **uma única vez** antes que os múltiplos workers do Gunicorn subam, eliminando qualquer risco de race condition ou locks DDL no PostgreSQL Neon.

- **Start Command:**
  ```bash
  gunicorn --bind 0.0.0.0:$PORT --workers 3 --threads 2 --timeout 60 --no-control-socket run:app
  ```

---

## 3. Matriz de Variáveis de Ambiente no Painel do Render

| Nome da Variável | Obrigatoriedade | Ambiente | Descrição |
| :--- | :---: | :---: | :--- |
| **`FLASK_ENV`** | **Obrigatória** | Produção | Deve ser fixada em `production`. Ativa ProxyFix, travas de segurança e desativa debug. |
| **`PYTHONPATH`** | **Obrigatória** | Produção | Deve ser fixada em `backend` para permitir importação modular da pasta `app`. |
| **`SECRET_KEY`** | **Obrigatória** | Produção | Chave criptográfica forte (mínimo 64 caracteres hexadecimais). Pode ser gerada via botão `Generate` do Render. |
| **`DATABASE_URL`** | **Obrigatória** | Produção | String de conexão PostgreSQL Neon com SSL obrigatório (`sslmode=require`). |
| **`IOT_DEVICE_KEY`** | **Obrigatória** | Produção | Chave secreta pré-compartilhada (PSK) com os terminais físicos ESP8266 NodeMCU. |
| **`TIMEZONE`** | Opcional | Produção | Fuso horário operacional da loja (`America/Sao_Paulo`). |
| **`SESSION_COOKIE_SECURE`**| Opcional | Produção | Padrão `True`. Garante que cookies de autenticação só trafeguem via HTTPS. |
| **`REMEMBER_COOKIE_SECURE`**| Opcional | Produção | Padrão `True`. |

---

## 4. Integração Segura com PostgreSQL Neon

1. No console do **Neon** ([console.neon.tech](https://console.neon.tech)):
   - Copie a string de conexão na aba *Connection Details*.
   - Selecione a opção **Pooled connection** para operações transacionais ou conexão direta para migrações volumosas.
   - Certifique-se de que o parâmetro `?sslmode=require` esteja presente na URL.
2. No painel do **Render**:
   - Adicione a variável `DATABASE_URL` no menu *Environment*.
   - Caso a URL comece com `postgres://`, o sistema a normaliza automaticamente para `postgresql://` na camada de configuração do Flask.
   - Nunca compartilhe nem exponha essa URL em commits ou logs públicos.

---

## 5. Passo a Passo: Primeiro Deploy em Produção

1. **Vincular Repositório no Render:**
   - Crie um novo **Web Service** conectado ao repositório GitHub `sistema-fidelizacao-arduino`.
   - Selecione a branch `main` ou `feat/banco-nuvem`.
2. **Definir Variáveis:**
   - Preencha as variáveis listadas na seção 3.
3. **Disparar Build & Deploy:**
   - O Render executará o `buildCommand`, instalando as bibliotecas e aplicando as migrações `0001` até `0006`.
4. **Verificar Health Check:**
   - Após o boot, o Render testará o endpoint `/health`. Quando retornar `HTTP 200`, o tráfego será liberado.
5. **Bootstrap da Proprietária:**
   - Abra a aba **Shell** no painel do Render e execute:
     ```bash
     flask create-owner --nome "Dona Oficial" --login "admin_loja" --email "contato@loja.com"
     ```
   - Digite a senha mestra. A conta com acesso total está pronta para uso!

---

## 6. Segregação de Ambientes: Staging vs Produção

Recomenda-se manter duas instâncias no Render:
- **`itclube-staging`:**
  - Branch: `develop` ou `staging`.
  - Neon: Branch de banco de dados segregada (*Neon Database Branch*). Permite testar migrações destrutivas sem impactar a loja.
- **`itclube-production`:**
  - Branch: `main`.
  - Neon: Branch primária (`main`) do Neon com backups automáticos habilitados.

---

## 7. Troubleshooting de Problemas Comuns

### Sintoma: `Application failed to start` / `Port binding error`
- **Causa Provável:** Porta fixa configurada em vez de `$PORT`.
- **Validação:** Checar se o comando de inicialização contém `--bind 0.0.0.0:$PORT`.
- **Solução:** Ajustar o *Start Command* para usar a variável `$PORT` injetada pelo Render.

### Sintoma: `ModuleNotFoundError: No module named 'app'`
- **Causa Provável:** Falta da variável `PYTHONPATH=backend`.
- **Solução:** Configurar a variável `PYTHONPATH` com o valor `backend` nas variáveis de ambiente do Render.

### Sintoma: `OperationalError: SSL connection has been closed unexpectedly`
- **Causa Provável:** Neon encerrou conexões inativas (scale-to-zero) ou pool esgotado.
- **Solução:** O SQLAlchemy reconecta automaticamente com pool pre-ping ativo. Se persistir, valide se a string do Neon contém `?sslmode=require`.

### Sintoma: `Control server error: Read-only file system: '/home/dd/.gunicorn'`
- **Causa Provável:** Gunicorn 26+ tentando criar socket de controle em diretório sem permissão de escrita.
- **Solução:** Adicionar a flag `--no-control-socket` no Start Command.
