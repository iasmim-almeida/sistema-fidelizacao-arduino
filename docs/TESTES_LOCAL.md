# Guia Completo de Execução & Testes Locais — IT Clube

Este documento contém todas as instruções práticas para clonar, configurar, executar e testar o projeto **IT Clube** localmente a partir do zero.

---

## 1. Pré-requisitos

- **Python 3.12+** instalado
- **Git**
- **pip** e **virtualenv**
- Opcional: **PostgreSQL 16+** (SQLite é suportado nativamente para desenvolvimento local)

---

## 2. Preparação do Ambiente Virtual

### 2.1. Clonagem e Acesso ao Projeto
```bash
git clone <URL_DO_REPOSITORIO>
cd sistema-fidelizacao-arduino
```

### 2.2. Criação do Ambiente Virtual
```bash
python -m venv venv
```

### 2.3. Ativação do Ambiente Virtual
- **Linux / macOS / WSL:**
  ```bash
  source venv/bin/activate
  ```
- **Windows (PowerShell):**
  ```powershell
  .\venv\Scripts\Activate.ps1
  ```
- **Windows (Prompt de Comando - CMD):**
  ```cmd
  .\venv\Scripts\activate.bat
  ```

---

## 3. Instalação de Dependências

```bash
pip install --upgrade pip
pip install -r backend/requirements.txt
```

---

## 4. Configuração de Variáveis de Ambiente (`.env`)

Copie o template de exemplo:
```bash
cp .env.example .env
```

Edite o arquivo `.env` para desenvolvimento local:
```env
FLASK_ENV=development
SECRET_KEY=sua-chave-secreta-forte-local-de-pelo-menos-32-caracteres
DATABASE_URL=sqlite:///fidelizacao.db
TIMEZONE=America/Sao_Paulo
IOT_DEVICE_KEY=fideliza-iot-key-padrao
HOST=127.0.0.1
PORT=5000
```

> [!NOTE]
> Nunca adicione senhas de produção ou credenciais reais do Neon no arquivo `.env` local.

---

## 5. Banco de Dados Local & Migrações

Execute as migrações estruturais do Alembic para criar o schema completo:
```bash
flask db upgrade
```

### 5.1. Carga de Dados Inicial (Seeds de Demonstração)
Para popular o banco com dados de teste (admin e cliente Ana Silva):
```bash
python database/seeds/seed.py
```

### 5.2. Bootstrap da Conta Proprietária
Para criar a conta oficial da dona da loja via terminal:
```bash
flask create-owner --nome "Dona da Loja" --login "proprietaria" --email "dona@loja.com"
```
*(O comando solicitará a senha forte de forma oculta e segura).*

---

## 6. Inicialização do Servidor Local

```bash
python run.py
```
Acesse a aplicação em seu navegador: **`http://127.0.0.1:5000`**.

---

## 7. Execução dos Testes Automatizados

### 7.1. Suíte Completa de Testes Unitários e Integração (100 testes)
```bash
python -m unittest discover backend/tests
```

### 7.2. Suíte de Auditoria de Segurança (SAST / DAST Local)
```bash
python test_security_audit.py
```

### 7.3. Testes Específicos por Módulo
- **Regras IT Clube (1 Compra = 1 Ponto & Autoatendimento):**
  ```bash
  python -m unittest backend.tests.test_itclube_regras
  ```
- **Ledger de Pontos & Concorrência:**
  ```bash
  python -m unittest backend.tests.test_pontos_ledger
  ```
- **Controle de Acesso RBAC:**
  ```bash
  python -m unittest backend.tests.test_rbac
  ```
- **Hardening de Produção & Cookies:**
  ```bash
  python -m unittest backend.tests.test_production_hardening
  ```

---

## 8. Teste Local em Modo Produção (Production-Like Local Test)

Antes de abrir um PR ou publicar no Render, simule o ambiente estrito de produção com Gunicorn e `DEBUG=False`:

```bash
FLASK_ENV=production \
SECRET_KEY="sua-chave-super-segura-e-aleatoria-para-simulacao-local" \
gunicorn --bind 127.0.0.1:5000 --workers 2 --threads 2 --timeout 30 --no-control-socket run:app
```

Em outro terminal, valide o health check e os cabeçalhos de segurança:
```bash
curl -i http://127.0.0.1:5000/health
```
Resposta esperada:
```http
HTTP/1.1 200 OK
Content-Type: application/json
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Content-Type-Options: nosniff
X-Frame-Options: SAMEORIGIN

{"status":"ok"}
```
