# syntax=docker/dockerfile:1

# 1. [CORREÇÃO] Usa uma tag de imagem MAIS ESPECÍFICA para forçar um novo download
# Isso evita usar o cache corrompido do SaveinCloud.
FROM python:3.11.9-slim-bookworm

# 2. Define variáveis de ambiente
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 3. Define o diretório de trabalho
WORKDIR /app

# 4. Atualiza o pip
RUN pip install --upgrade pip

# 5. Instala dependências do sistema
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# 6. [CACHE BUSTER] Força o Docker a não usar o cache para os passos seguintes
ARG CACHE_BUSTER=1

# 7. Copia e instala as dependências do Python
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# 8. Copia o resto do código da aplicação
COPY . /app

# 9. Expõe a porta 80, que o Gunicorn agora usa
EXPOSE 80

# 10. Garante que o script de startup correto seja executável
RUN chmod +x /app/startup.sh

# 11. Define o script de startup CORRETO como o ponto de entrada
ENTRYPOINT ["/app/startup.sh"]