# Usa uma imagem base oficial do Python
FROM python:3.11-slim

# Define o diretório de trabalho dentro do container
WORKDIR /app

# --- CORREÇÃO DEFINITIVA: Instala o Chrome a partir do repositório oficial ---

# 1. Instala utilitários básicos e o curl para adicionar a chave do repositório
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    wget \
    curl \
    gnupg \
    unzip \
    # Dependências da WeasyPrint
    libpango-1.0-0 \
    libcairo2 \
     libgdk-pixbuf-xlib-2.0-0 \ 
    && rm -rf /var/lib/apt/lists/*

# 2. Adiciona o repositório oficial do Google Chrome
RUN curl -sS -o - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor | tee /usr/share/keyrings/google-chrome-keyring.gpg >/dev/null
RUN echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list

# 3. Instala o Google Chrome (e as suas dependências) a partir do repositório
RUN apt-get update && apt-get install -y \
    google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# --- FIM DA CORREÇÃO ---

# Copia o ficheiro de dependências
COPY requirements.txt .

# Instala as dependências do Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o código da aplicação para o diretório de trabalho
COPY . .

# Copia o script de arranque para dentro do contentor
COPY startup.sh .
# Torna o script de arranque executável
RUN chmod +x ./startup.sh

# Define o script de arranque como o ponto de entrada do contentor
CMD ["./startup.sh"]