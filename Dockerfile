# syntax=docker/dockerfile:1

# Usa imagem base (full é mais seguro contra problemas de cache/libs faltando)
FROM python:3.11-bullseye # Ou a versão python que preferir, ex: 3.11

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

RUN pip install --upgrade pip

# Instala dependências do sistema (gcc/libpq-dev para psycopg2)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Cache buster (opcional, mas útil para forçar reinstalação)
ARG CACHE_BUSTER=1

COPY requirements.txt /app/
# Instala dependências Python (sem cache para garantir versões corretas)
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

# --- CORREÇÃO: Expõe a porta que Gunicorn usará ---
EXPOSE 8000

RUN chmod +x /app/startup.sh

# Define o script de startup como ponto de entrada
ENTRYPOINT ["/app/startup.sh"]