# Arquivo: Dockerfile

# --- STAGE 1: Build & Instalação de Sistema (Robôs/PDF) ---
# Usamos a base python:3.11-slim, conforme o requisito do runtime.txt
FROM python:3.11-slim as builder

WORKDIR /app

# Instala as dependências de sistema para WeasyPrint e Chrome/Chromium
# NOTA: Adicionado 'gnupg' e 'unzip' para os passos seguintes.
RUN apt-get update && apt-get install -y \
    wget gnupg unzip \
    libxml2-dev libxslt-dev libjpeg-dev zlib1g-dev \
    libcairo2 libpango-1.0-0 libpangocairo-1.0-0 \
    libgomp1 libsqlite3-0 \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# --- CORREÇÃO CRÍTICA: Instalação do Google Chrome (Removendo apt-key) ---
# Cria a pasta de chaves e adiciona a chave GPG do Google Chrome de forma moderna (gnupg).
RUN mkdir -p /etc/apt/keyrings && \
    wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor | tee /etc/apt/keyrings/google-chrome.gpg > /dev/null && \
    echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list && \
    chmod a+r /etc/apt/keyrings/google-chrome.gpg

# Instala o Chrome Stable e as dependências Python
RUN apt-get update && apt-get install -y \
    google-chrome-stable \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Instala o ChromeDriver compatível (usando o método chrome-for-testing)
RUN CHROME_DRIVER_VERSION=$(wget -qO- https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_STABLE) && \
    wget -q --continue -P /tmp https://storage.googleapis.com/chrome-for-testing-public/${CHROME_DRIVER_VERSION}/linux64/chromedriver-linux64.zip && \
    unzip /tmp/chromedriver-linux64.zip -d /usr/local/bin/ && \
    rm -rf /var/lib/apt/lists/* /tmp/* && \
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

# Copia todo o código-fonte
COPY . /app

# Define a variável de ambiente para que o Selenium encontre o driver
ENV PATH="/usr/local/bin:${PATH}"

# Porta da aplicação Flask/API
EXPOSE 8000 

ENTRYPOINT ["/bin/bash", "-c"]