# syntax=docker/dockerfile:1
# 1. Usa a imagem base oficial do Python
FROM python:3.11-slim-bookworm

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

# 6. Copia e instala as dependências do Python
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# 7. Copia o resto do código da aplicação
COPY . /app

# 8. Expõe a porta que o Gunicorn vai usar
EXPOSE 5000

# --- CORREÇÃO APLICADA ---

# 9. COMENTA O ENTRYPOINT ANTIGO E INCORRETO
# ENTRYPOINT ["/app/entrypoint.sh"]

# 10. Garante que o script de startup correto (usado pelo Render) seja executável
RUN chmod +x /app/startup.sh

# 11. Define o script de startup CORRETO como o ponto de entrada
ENTRYPOINT ["/app/startup.sh"]