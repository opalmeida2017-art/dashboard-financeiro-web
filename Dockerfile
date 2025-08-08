# Dockerfile (versão para rodar o Selenium no Render)

# Use uma imagem base do Python que seja Debian-based
FROM python:3.11-slim-buster

# Defina o diretório de trabalho
WORKDIR /app

# --- NOVO: Instala o Google Chrome e suas dependências ---
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y \
    google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# --- NOVO: Baixa e instala o ChromeDriver correspondente ---
RUN CHROME_VERSION=$(google-chrome --version | cut -f 3 -d ' ' | cut -d '.' -f 1) && \
    DRIVER_VERSION=$(wget -qO- https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_${CHROME_VERSION}) && \
    wget -q https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${DRIVER_VERSION}/linux64/chromedriver-linux64.zip && \
    unzip chromedriver-linux64.zip && \
    mv chromedriver-linux64/chromedriver /usr/bin/chromedriver && \
    rm chromedriver-linux64.zip

# Copie e instale as dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie o resto do seu projeto
COPY . .

# Comando para iniciar a aplicação web (Gunicorn)
CMD gunicorn --bind 0.0.0.0:$PORT --workers 3 app:app