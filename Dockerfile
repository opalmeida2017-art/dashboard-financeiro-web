# Arquivo: Dockerfile

# --- STAGE 1: Build & Instalação de Sistema (Robôs/PDF) ---
# Usamos a base python:3.11-slim, conforme o requisito do runtime.txt
FROM python:3.11-slim as builder

WORKDIR /app

# Instala as dependências de sistema para WeasyPrint e Chrome/Chromium
# As libs de WeasyPrint (libcairo2, libpango-1.0-0, etc.) são necessárias para a geração de PDF.
RUN apt-get update && apt-get install -y \
    wget gnupg unzip \
    libxml2-dev libxslt-dev libjpeg-dev zlib1g-dev \
    libcairo2 libpango-1.0-0 libgdk-pixbuf2.0-0 libpangocairo-1.0-0 \
    libgomp1 libsqlite3-0 \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Instala o Google Chrome Stable, necessário para o Selenium
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && apt-get install -y \
    google-chrome-stable \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*
    
# Instala o ChromeDriver compatível
RUN CHROME_VERSION=$(google-chrome-stable --version | awk '{print $3}' | cut -d'.' -f1) && \
    CHROMEDRIVER_VERSION=$(wget -qO- "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_VERSION}" | tr -d '\n') && \
    wget -q "https://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_linux64.zip" -O /tmp/chromedriver.zip && \
    unzip /tmp/chromedriver.zip -d /usr/local/bin/ && \
    rm /tmp/chromedriver.zip && \
    chmod +x /usr/local/bin/chromedriver

# Configuração de ambiente Python
ENV PYTHONUNBUFFERED 1

# Copia e instala as dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- STAGE 2: Imagem Final de Execução ---
FROM builder as final

WORKDIR /app

# Cria a pasta de downloads que os robôs esperam.
RUN mkdir -p /app/downloads

# Copia todo o código-fonte (para que o hot-reload e o worker funcionem)
COPY . /app

# Define a variável de ambiente para que o Selenium encontre o driver
ENV PATH="/usr/local/bin:${PATH}"

# Porta da aplicação Flask/API
EXPOSE 8000 

ENTRYPOINT ["/bin/bash", "-c"]