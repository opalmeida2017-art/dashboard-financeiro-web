# Dockerfile (versão final, limpa e organizada)

# Usa uma imagem base do Python mais recente (Bullseye)
FROM python:3.11-slim-bullseye

# Define o diretório de trabalho
WORKDIR /app

# Define o ambiente como não-interativo para evitar prompts durante a instalação
ENV DEBIAN_FRONTEND=noninteractive

# --- Instala o Google Chrome e o ChromeDriver (Método Moderno e Robusto) ---
# Usamos BASH para garantir a compatibilidade dos comandos
SHELL ["/bin/bash", "-c"]
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gnupg \
    unzip \
    wget \
    && curl -sS -o - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome-keyring.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y --no-install-recommends \
    google-chrome-stable \
    # Baixa e instala o ChromeDriver
    && CHROME_VERSION=$(google-chrome --version | cut -f 3 -d ' ' | cut -d '.' -f 1-3) \
    && DRIVER_VERSION=$(curl -sS https://googlechromelabs.github.io/chrome-for-testing/latest-patch-versions-per-build.json | grep -A1 "${CHROME_VERSION}" | grep '"version":' | head -n1 | cut -d '"' -f 4) \
    && wget -q "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${DRIVER_VERSION}/linux64/chromedriver-linux64.zip" \
    && unzip chromedriver-linux64.zip \
    && mv chromedriver-linux64/chromedriver /usr/bin/chromedriver \
    && rm chromedriver-linux64.zip \
    && rm -rf /var/lib/apt/lists/*

# Copia e instale as dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o resto do seu projeto
COPY . .

# Comando para iniciar a aplicação web (Gunicorn)
CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "--workers", "3", "app:app"]
