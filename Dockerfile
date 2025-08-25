# Usa uma imagem base oficial do Python
FROM python:3.11-slim

# --- CORREÇÃO: Apenas instala as dependências de sistema essenciais ---
RUN apt-get update && apt-get install -y \
    # Dependências do seu projeto
    build-essential \
    libpq-dev \
    # Dependências para o Selenium Manager funcionar
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Define o diretório de trabalho
WORKDIR /app

# Copia os ficheiros de requisitos e código
COPY requirements.txt .
COPY . .

# Instala as dependências do Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia e torna o script de arranque executável
COPY startup.sh .
RUN chmod +x ./startup.sh

# Define o comando de entrada
CMD ["./startup.sh"]