# Guia de Desenvolvimento & Execução — IT Clube

Este guia orienta a configuração do ambiente de desenvolvimento local, execução de testes e implantação conteinerizada do **IT Clube**.

---

## 1. Pré-requisitos

- **Python 3.12+** instalado
- **Git**
- **Docker** e **Docker Compose** (opcional, para execução conteinerizada)
- **PostgreSQL 16+** (opcional, para ambiente de produção; SQLite é suportado localmente)

---

## 2. Configuração do Ambiente Local (Sem Docker)

### 2.1. Clonar o Repositório e Criar Ambiente Virtual
```bash
git clone <url-do-repositorio>
cd sistema-fidelizacao-integrado

# Criação e ativação do ambiente virtual
python -m venv venv

# No Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# No Linux/macOS:
source venv/bin/activate
```

### 2.2. Instalação das Dependências
```bash
pip install --upgrade pip
pip install -r backend/requirements.txt
```

### 2.3. Configuração de Variáveis de Ambiente
Copie o arquivo `.env.example` para `.env` e preencha com suas configurações:
```bash
cp .env.example .env
```
Exemplo de configuração mínima para desenvolvimento local:
```env
SECRET_KEY=uma-chave-secreta-forte-e-aleatoria-de-pelo-menos-32-caracteres
DATABASE_URL=sqlite:///fidelizacao.db
FLASK_ENV=development
TIMEZONE=America/Sao_Paulo
IOT_DEVICE_KEY=itclube-iot-device-key-secreta
HOST=127.0.0.1
PORT=5000
```

### 2.4. Inicialização do Banco de Dados & Seeds
```bash
# Executa migrações estruturais
flask db upgrade

# Popula usuários de demonstração e clientes de teste
python database/seeds/seed.py
```

### 2.5. Inicialização da Aplicação
```bash
python run.py
```
Acesse a aplicação em `http://127.0.0.1:5000`.

---

## 3. Execução dos Testes Automatizados

### Suíte Completa de Testes Unitários e de Integração
```bash
python -m unittest discover backend/tests
```

### Suíte de Auditoria de Segurança & Hardening
```bash
python test_security_audit.py
```

---

## 4. Execução com Docker & Docker Compose

Para rodar a aplicação em contêineres com banco de dados PostgreSQL:

```bash
# 1. Construir e inicializar os containers em segundo plano
docker compose up --build -d

# 2. Acompanhar os logs do backend
docker compose logs -f backend

# 3. Executar migrações dentro do container
docker compose exec backend flask db upgrade

# 4. Parar os containers
docker compose down
```
O serviço estará acessível em `http://localhost:5000`.
