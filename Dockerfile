# Usa uma imagem base oficial do Python
FROM python:3.11-slim

# Define o diretório de trabalho dentro do container
WORKDIR /app

# --- CORREÇÃO: Instala dependências do sistema, Chrome e ChromeDriver ---

# 1. Instala utilitários necessários (wget para baixar, unzip para extrair)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# 2. Baixa e instala a versão estável mais recente do Google Chrome
RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
RUN dpkg -i google-chrome-stable_current_amd64.deb || apt-get install -fy

# 3. Baixa e instala o ChromeDriver correspondente
# NOTA: Verifique a versão mais recente do Chrome/ChromeDriver se necessário.
# Este link é para uma versão recente e estável.
RUN wget https://storage.googleapis.com/chrome-for-testing-public/128.0.6600.0/linux64/chromedriver-linux64.zip
RUN unzip chromedriver-linux64.zip
RUN mv -f chromedriver-linux64/chromedriver /usr/local/bin/chromedriver
RUN chmod +x /usr/local/bin/chromedriver

# --- FIM DA CORREÇÃO ---

# Copia o ficheiro de dependências
COPY requirements.txt .

# Instala as dependências do Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o código da aplicação para o diretório de trabalho
COPY . .

# Se você usa um script de inicialização, mantenha estas linhas
COPY startup.sh .
RUN chmod +x ./startup.sh
CMD ["./startup.sh"]