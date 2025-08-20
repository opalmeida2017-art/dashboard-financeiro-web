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

# --- ALTERAÇÕES PARA USAR O SCRIPT DE ARRANQUE ---

# 1. Copia o script de arranque para dentro do contentor
COPY startup.sh .

# 2. Torna o script de arranque executável
RUN chmod +x ./startup.sh

# 3. Define o script de arranque como o ponto de entrada do contentor
CMD ["./startup.sh"]
