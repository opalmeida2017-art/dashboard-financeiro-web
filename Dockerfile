# Arquivo: Dockerfile

# --- STAGE 1: Build & Instalação de Sistema (Robôs/PDF) ---
# Usamos a base python:3.11-slim
FROM python:3.11-slim as builder

WORKDIR /app

# Instala as dependências de sistema para WeasyPrint e Chrome/Chromium
# NOTA: O pacote libgdk-pixbuf2.0-0 foi removido para evitar a falha de dependência.
RUN apt-get update && apt-get install -y \
    wget gnupg unzip \
    libxml2-dev libxslt-dev libjpeg-dev zlib1g-dev \
    libcairo2 libpango-1.0-0 libpangocairo-1.0-0 \
    libgomp1 libsqlite3-0 \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# --- CORREÇÃO: Instalação do Google Chrome (Método Moderno GPG) ---
RUN mkdir -p /etc/apt/keyrings && \
    wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor | tee /etc/apt/keyrings/google-chrome.gpg > /dev/null && \
    echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list && \
    chmod a+r /etc/apt/keyrings/google-chrome.gpg

# Instala o Chrome Stable
RUN apt-get update && apt-get install -y \
    google-chrome-stable \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# --- CORREÇÃO CRÍTICA: Instalação do ChromeDriver (Movimentação do Binário) ---
RUN CHROME_DRIVER_VERSION=$(wget -qO- https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_STABLE) && \
    wget -q --continue -P /tmp https://storage.googleapis.com/chrome-for-testing-public/${CHROME_DRIVER_VERSION}/linux64/chromedriver-linux64.zip && \
    unzip /tmp/chromedriver-linux64.zip -d /usr/local/bin/ && \
    # LINHA CORRIGIDA: Move o binário de dentro da subpasta para o local esperado
    mv /usr/local/bin/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver && \
    chmod +x /usr/local/bin/chromedriver && \
    rm -rf /var/lib/apt/lists/* /tmp/* /usr/local/bin/chromedriver-linux64

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

# Copia todo o código-fonte
COPY . /app

# Define a variável de ambiente para que o Selenium encontre o driver
ENV PATH="/usr/local/bin:${PATH}"

# Porta da aplicação Flask/API
EXPOSE 8000 

ENTRYPOINT ["/bin/bash", "-c"]