# ==============================================================================
# Dockerfile - IT Clube (Backend & Aplicação Web)
# Imagem segura em conformidade com práticas de hardening e usuário não-root
# ==============================================================================

FROM python:3.12-slim

LABEL maintainer="Equipe de Engenharia IT Clube"
LABEL description="Serviço Web & API do Programa de Fidelização IT Clube"

# Parâmetros de segurança e execução Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/backend \
    PORT=5000

WORKDIR /app

# Instalação de dependências do sistema operacional
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Criação de grupo e usuário de aplicação sem privilégios de superusuário
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/sh -d /app appuser

# Instalação prévia de dependências Python para aproveitar cache de camadas
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Cópia das camadas da aplicação
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/
COPY database/ /app/database/
COPY run.py /app/run.py

# Ajuste seguro de permissões
RUN chown -R appuser:appgroup /app

# Execução como usuário não-root
USER appuser

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

CMD gunicorn --bind 0.0.0.0:${PORT:-5000} --workers 3 --timeout 60 run:app
