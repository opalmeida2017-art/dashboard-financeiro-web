# syntax=docker/dockerfile:1

# Usa a versão python 3.11
FROM python:3.11 

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

RUN pip install --upgrade pip

# Instala dependências do banco de dados E do robô (Selenium)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    chromium \
    chromium-driver && \
    rm -rf /var/lib/apt/lists/*

# Cache buster (opcional, mas útil para forçar reinstalação)
ARG CACHE_BUSTER=1

COPY requirements.txt /app/
# Instala dependências Python (sem cache para garantir versões corretas)
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

# Expõe a porta que Gunicorn usará
EXPOSE 8000

RUN chmod +x /app/startup.sh

# Define o script de startup como ponto de entrada (CORRIGIDO: startup.sh)
ENTRYPOINT ["/app/startup.sh"]
