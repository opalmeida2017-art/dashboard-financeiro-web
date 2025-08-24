# Usa uma imagem base oficial do Python
FROM python:3.11-slim

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Instala as dependências do sistema, incluindo as do Chrome
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    wget \
    unzip \
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
    && rm -rf /var/lib/apt/lists/*

# Baixa e instala a versão estável mais recente do Google Chrome
RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
RUN dpkg -i google-chrome-stable_current_amd64.deb || apt-get install -fy --fix-broken

# --- CORREÇÃO: Atualiza a URL do ChromeDriver para a versão 139 ---
RUN wget https://storage.googleapis.com/chrome-for-testing-public/139.0.7258.138/linux64/chromedriver-linux64.zip
# --- FIM DA CORREÇÃO ---
RUN unzip chromedriver-linux64.zip
RUN mv -f chromedriver-linux64/chromedriver /usr/local/bin/chromedriver
RUN chmod +x /usr/local/bin/chromedriver

# O resto do arquivo continua igual...
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY startup.sh .
RUN chmod +x ./startup.sh
CMD ["./startup.sh"]