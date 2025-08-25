# Usa uma imagem base oficial do Python
FROM python:3.11-slim

# --- CORREÇÃO: Apenas instala as dependências de sistema essenciais ---
# Instala as bibliotecas que o seu projeto Python precisa (como psycopg2)
# e as que o Selenium Manager precisa para descarregar o navegador (wget, unzip).
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Define o diretório de trabalho
WORKDIR /app

# Copia os ficheiros de requisitos e o código da aplicação
COPY requirements.txt .
COPY . .

# Instala as dependências do Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia e torna o script de arranque executável
COPY startup.sh .
RUN chmod +x ./startup.sh

# Define o comando de entrada
CMD ["./startup.sh"]