# Usa uma imagem base oficial do Python
FROM python:3.11-slim

# Define o diretório de trabalho dentro do container
WORKDIR /app

# --- CORREÇÃO: Adiciona as bibliotecas de sistema necessárias para o Chrome rodar ---
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    wget \
    unzip \
    # --- DEPENDÊNCIAS ESSENCIAIS PARA O CHROME ---
    libglib2.0-0 \
    libnss3 \
    libgconf-2-4 \
    libfontconfig1 \
    # --- FIM DA ADIÇÃO ---
    && rm -rf /var/lib/apt/lists/*

# Baixa e instala a versão estável mais recente do Google Chrome
RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
# O '|| apt-get install -fy' força a instalação das dependências do Chrome
RUN dpkg -i google-chrome-stable_current_amd64.deb || apt-get install -fy

# Baixa e instala o ChromeDriver correspondente
# NOTA: Esta versão do ChromeDriver é compatível com a versão estável do Chrome.
RUN wget https://storage.googleapis.com/chrome-for-testing-public/128.0.6600.0/linux64/chromedriver-linux64.zip
RUN unzip chromedriver-linux64.zip
RUN mv -f chromedriver-linux64/chromedriver /usr/local/bin/chromedriver
RUN chmod +x /usr/local/bin/chromedriver

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