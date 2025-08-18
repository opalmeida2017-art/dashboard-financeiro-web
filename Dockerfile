# Usa uma imagem base oficial do Python
FROM python:3.11-slim

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Copia o ficheiro de dependências
COPY requirements.txt .

# Instala as dependências do sistema necessárias para o psycopg2 e o Pandas
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Instala as dependências do Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o código da aplicação para o diretório de trabalho
COPY . .

# Expõe a porta que o Gunicorn irá usar
EXPOSE 10000

# --- COMANDO DE ARRANQUE PARA PRODUÇÃO ---
# 1. Executa as migrações da base de dados com o Alembic
# 2. Inicia a aplicação usando o servidor Gunicorn
CMD ["sh", "-c", "python3 -m alembic upgrade head && gunicorn --workers 3 --bind 0.0.0.0:10000 app:app"]