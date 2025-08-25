# Usa uma imagem base oficial do Python
FROM python:3.11-slim

# Define o diretório de trabalho dentro do container
WORKDIR /app

# --- CORREÇÃO FINAL: Instala TODAS as dependências de sistema para o Chrome ---
RUN apt-get update && apt-get install -y \
    # Dependências do seu projeto que já tínhamos
    build-essential \
    libpq-dev \
    wget \
    unzip \
    # Lista completa de dependências para o Chrome Headless no Debian
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libc6 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libexpat1 \
    libfontconfig1 \
    libgbm1 \
    libgcc1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libstdc++6 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    lsb-release \
    xdg-utils \
    # Fim da lista de dependências
    && rm -rf /var/lib/apt/lists/*

# Baixa e instala a versão estável mais recente do Google Chrome
RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
# O '|| apt-get install -fy' força a instalação de quaisquer outras dependências que o Chrome precise
RUN dpkg -i google-chrome-stable_current_amd64.deb || apt-get install -fy --fix-broken

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