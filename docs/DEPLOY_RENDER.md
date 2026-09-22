# Manual Completo de Deploy no Render & Integração PostgreSQL Neon

Este manual descreve a arquitetura, configuração, comandos exatos e procedimentos operacionais para implantação do sistema **IT Clube / FideliZa** no **Render Web Service** conectado ao **PostgreSQL Neon**.

---

## 1. Pré-requisitos

1. **Repositório GitHub**: Repositório sincronizado contendo a aplicação.
2. **Conta no Render** ([render.com](https://render.com)): Conta ativa para provisionamento do Web Service Linux.
3. **Conta no Neon** ([neon.tech](https://neon.tech)): Projeto PostgreSQL serverless provisionado.
4. **Branch de Produção**: Branch estável (`main` ou `feat/qa-security-troca-senha-primeiro-acesso`).
5. **Python 3.12+** instalado localmente para homologação prévia.

---

## 2. Preparação Local

Antes de submeter alterações para a branch de deploy:

```bash
# 1. Ativar o ambiente virtual local
source venv/bin/activate

# 2. Atualizar dependências locais
pip install --upgrade pip
pip install -r requirements.txt

# 3. Validar status do repositório Git
git status
git branch --show-current
```

---

## 3. Testes Locais

Execute as suítes automatizadas obrigatórias:

```bash
# Executar a suíte de testes unitários, integração e segurança
python3 -m unittest discover -s backend/tests

# Executar a suíte específica de auditoria de segurança (SAST / DAST local)
python3 test_security_audit.py
```

> **Critério de Aceite**: 100% dos testes devem passar com status `OK`.

---

## 4. Validação das Migrações

Valide se o Alembic consegue inspecionar o histórico e o estado atual do banco:

```bash
# Verificar revisão atual do banco
python3 -m flask --app wsgi:app db current

# Verificar se há pendências de migração
python3 -m flask --app wsgi:app db heads
```

---

## 5. Configuração do Banco PostgreSQL Neon

1. Acesse o console do Neon ([console.neon.tech](https://console.neon.tech)).
2. No seu projeto, navegue até **Dashboard** -> **Connection Details**.
3. Selecione a opção **Pooled connection** (recomendada para gerenciar conexões com workers concorrentes do Gunicorn).
4. Copie a string de conexão no formato:
   ```text
   postgresql://<usuario>:<senha>@<host-neon>/<nome-do-banco>?sslmode=require
   ```
   > [!IMPORTANT]
   > Certifique-se de que o parâmetro `?sslmode=require` esteja presente na URL. A aplicação converte automaticamente URLs com prefixo `postgres://` para `postgresql+psycopg2://`.

---

## 6. Configuração do Serviço Web no Render

1. No dashboard do Render ([dashboard.render.com](https://dashboard.render.com)), clique em **New +** -> **Web Service**.
2. Conecte o repositório GitHub do projeto.
3. Defina os seguintes parâmetros essenciais:
   - **Name**: `itclube-fidelizacao`
   - **Region**: `Ohio (US East)` (ou a região mais próxima da sua instância Neon).
   - **Branch**: Sua branch principal de produção.
   - **Runtime**: `Python 3`
   - **Instance Type**: `Starter` (ou `Free`, atentando-se para o spin-down em inatividade).
   - **Health Check Path**: `/health`

---

## 7. Build Command

O comando de build do Render executa a instalação de dependências e a aplicação segura das migrações antes de inicializar o servidor HTTP:

```bash
pip install --upgrade pip && pip install -r requirements.txt && flask --app wsgi:app db upgrade
```

> [!NOTE]
> Executar o `flask db upgrade` no **Build Command** garante que o schema do banco seja atualizado uma única vez antes que os múltiplos workers do Gunicorn inicializem, prevenindo concorrência de DDL (*Data Definition Language*) no PostgreSQL Neon.

---

## 8. Pre-Deploy / Migration Command

Caso você utilize o plano **Paid/Team** do Render com suporte nativo a **Pre-Deploy Command**, configure:

```bash
flask --app wsgi:app db upgrade
```

E simplifique o **Build Command** para:
```bash
pip install --upgrade pip && pip install -r requirements.txt
```

---

## 9. Start Command

O servidor de produção deve utilizar o **Gunicorn** como servidor WSGI de padrão industrial:

```bash
gunicorn --bind 0.0.0.0:$PORT --workers 3 --threads 2 --timeout 60 --no-control-socket wsgi:app
```

---

## 10. Matriz de Variáveis de Ambiente (Environment Variables)

Configure as seguintes variáveis na aba **Environment** do serviço no Render:

| Variável | DEV | STAGING | PRD | Sensível | Obrigatória | Função |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **`FLASK_ENV`** | `development` | `production` | `production` | Não | **Sim** | Define o perfil de execução, desativa debug e ativa travas de produção. |
| **`FLASK_APP`** | `wsgi:app` | `wsgi:app` | `wsgi:app` | Não | **Sim** | Informa ao Flask CLI o ponto de entrada da aplicação. |
| **`PYTHONPATH`** | `backend` | `backend` | `backend` | Não | **Sim** | Garante resolução de imports internos da pasta `backend/app`. |
| **`DATABASE_URL`** | `sqlite:///...` | `<URL_NEON_STG>` | `<URL_NEON_PRD>` | **Sim** | **Sim** | Connection string do PostgreSQL Neon com `sslmode=require`. |
| **`SECRET_KEY`** | `dev-secret-key` | `<SECRET_STG>` | `<GERAR_NO_RENDER>` | **Sim** | **Sim** | Chave criptográfica da sessão. Pode usar o botão `Generate` do Render. |
| **`INITIAL_SETUP_TOKEN`**| (Vazio) | `<TOKEN_STG>` | `<TOKEN_OPCIONAL>` | **Sim** | Não | Token de proteção para a tela `/auth/setup` no primeiro acesso. |
| **`IOT_DEVICE_KEY`** | `fideliza-key` | `<KEY_STG>` | `<GERAR_NO_RENDER>` | **Sim** | **Sim** | Chave de autenticação HMAC dos microcontroladores ESP8266. |
| **`TIMEZONE`** | `America/Sao_Paulo` | `America/Sao_Paulo` | `America/Sao_Paulo`| Não | Não | Fuso horário para log e transações da loja. |
| **`SESSION_COOKIE_SECURE`**| `False` | `True` | `True` | Não | Não | Força transporte de cookies de sessão estritamente via HTTPS. |
| **`REMEMBER_COOKIE_SECURE`**| `False` | `True` | `True` | Não | Não | Força transporte de cookies de remember estritamente via HTTPS. |

---

## 11. Primeiro Deploy

1. Clique em **Create Web Service** ou **Manual Deploy** -> **Deploy latest commit**.
2. Acompanhe a aba **Events** e **Logs** de compilação:
   - O Render instalará os pacotes Python;
   - O Alembic executará `flask db upgrade` e aplicará as migrações `0001` até `0006`;
   - O Gunicorn inicializará 3 workers escutando na porta designada;
   - O healthcheck em `/health` responderá `HTTP 200`.

---

## 12. Cadastro do Primeiro Administrador (`/auth/setup`)

Com o deploy concluído e o banco vazio de administradores:

1. Acesse o domínio gerado pelo Render: `https://seu-app.onrender.com/`.
2. Como ainda não existe administradora no banco, o sistema redireciona automaticamente para:
   ```text
   https://seu-app.onrender.com/auth/setup
   ```
   *(Caso você tenha configurado `INITIAL_SETUP_TOKEN`, acesse `https://seu-app.onrender.com/auth/setup?token=<SEU_TOKEN>` ou preencha o campo no formulário).*
3. Preencha os dados da primeira Vendedora / Gestora:
   - **Nome Completo**: Nome da administradora (mínimo 3 caracteres);
   - **Login de Acesso**: Identificador de login (ex: `vendedora_chefe`);
   - **E-mail Corporativo**: E-mail para contato e auditoria;
   - **Senha Forte**: Mínimo 8 caracteres com maiúscula, minúscula, número e caractere especial;
   - **Confirmar Senha**: Confirmação idêntica.
4. Clique em **Concluir Cadastro da Vendedora (Admin)**.
5. O sistema registra a administradora, grava o log de auditoria, realiza o login automático e redireciona para `/dashboard`.

---

## 13. Validar Bloqueio do Setup

Para confirmar que a trava de segurança está ativada:

1. Abra uma aba anônima no navegador (ou faça logout).
2. Tente acessar diretamente:
   ```text
   https://seu-app.onrender.com/auth/setup
   ```
3. **Resultado Esperado**:
   - O sistema detecta a existência de administradora cadastrada;
   - A requisição `GET` é imediatamente redirecionada para a tela de login (`/`), exibindo o aviso:
     > *"O cadastro inicial já foi realizado. Efetue login."*
   - Qualquer tentativa de requisição `POST` para `/auth/setup` é sumariamente rejeitada com **HTTP 403 Forbidden**.

---

## 14. Smoke Tests Pós-Deploy

Valide o funcionamento em produção:

- [ ] **Home & Login**: Acessar `https://seu-app.onrender.com/` e confirmar que a tela de login unificada (Vendedora / Cliente) é renderizada.
- [ ] **Autenticação**: Efetuar login com a conta criada no setup.
- [ ] **Dashboard**: Acessar `/dashboard` e validar carregamento de métricas.
- [ ] **Cadastro de Clientes**: Acessar `/clientes` e cadastrar um cliente de teste com telefone e senha provisória.
- [ ] **Pontuação**: Simular ou registrar compra em `/pontuar`.
- [ ] **Catálogo**: Acessar `/gestao-recompensas` e cadastrar/pausar recompensas.
- [ ] **Logout**: Clicar em "Sair" e confirmar destruição da sessão.

---

## 15. Localização e Interpretação de Logs no Render

1. No dashboard do Render, acesse seu serviço e clique na aba **Logs**.
2. **Logs Normais de Operação**:
   - `[INFO] Booting worker with pid: ...`
   - `GET /health HTTP/1.1 200`
   - `CADASTRO_INICIAL_VENDEDORA_ADMIN` registrado na tabela de auditoria.
3. **Logs Sanitizados**:
   - O sistema não imprime senhas, hashes, `SECRET_KEY` ou tokens nas saídas padrão do log.

---

## 16. Procedimento de Rollback

Em caso de falha crítica durante ou após o deploy:

1. **Rollback de Código no Render**:
   - No dashboard do Render, vá em **Events**;
   - Localize o último deploy funcional e clique em **Rollback to this deploy**.
2. **Rollback de Banco de Dados (Neon PITR)**:
   - Se uma migração incorreta corrompeu dados no PostgreSQL Neon, acesse o console do Neon ([console.neon.tech](https://console.neon.tech));
   - Utilize a funcionalidade de **Point-in-Time Recovery (PITR)** criando uma branch a partir do timestamp anterior ao incidente;
   - Aponte a variável `DATABASE_URL` no Render para a branch restaurada.

---

## 17. Guia de Troubleshooting

### Problema 1: `/auth/setup` redireciona para login no primeiro acesso sem permitir cadastro
- **Causa**: O banco PostgreSQL Neon já possui usuários cadastrados (por exemplo, de testes prévios com `seed.py` ou migrações antigas com `usuario_legado`).
- **Solução**: Conecte ao banco Neon via psql ou console SQL do Neon e verifique:
  ```sql
  SELECT id_usuario, login, nivel_acesso FROM usuario;
  ```
  Caso existam usuários de teste antigos que você deseja descartar para permitir o first-run setup, limpe a tabela:
  ```sql
  DELETE FROM usuario WHERE nivel_acesso != 'CLIENTE';
  ```

### Problema 2: Erro `NoSuchModuleError: Can't load plugin: sqlalchemy.dialects:postgres`
- **Causa**: `DATABASE_URL` informada começa com `postgres://` em vez de `postgresql://`.
- **Solução**: O arquivo `backend/app/config.py` já normaliza essa string automaticamente. Certifique-se de que a última versão do código está em execução no Render.

### Problema 3: Falha de CSRF ao submeter o formulário de setup
- **Causa**: `SECRET_KEY` ausente ou gerada de forma independente por múltiplos workers do Gunicorn.
- **Solução**: Defina a variável `SECRET_KEY` no painel do Render (clique em *Generate*). Isso garante que todos os workers compartilhem exatamente o mesmo segredo criptográfico.

### Problema 4: Queda intermitente de conexão ou erro 500 após inatividade
- **Causa**: A instância do Neon entrou em suspensão (*autosuspend*) e o proxy encerrou conexões inativas.
- **Solução**: O SQLAlchemy já possui `pool_pre_ping=True` e `pool_recycle=300` configurados em `ProductionConfig`. Certifique-se de usar a connection string com `?sslmode=require`.
