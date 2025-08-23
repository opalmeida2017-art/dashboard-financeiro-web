# Usa uma imagem base oficial do Python
[cite_start]FROM python:3.11-slim [cite: 1]

# Define o diretório de trabalho dentro do container
[cite_start]WORKDIR /app [cite: 1]

# Instala as dependências do sistema necessárias para o Chrome rodar
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    wget \
    unzip \
    libglib2.0-0 \
    libnss3 \
    libfontconfig1 \
    && rm -rf /var/lib/apt/lists/*

# Baixa e instala a versão estável mais recente do Google Chrome
RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
# O '|| apt-get install -fy' força a instalação das dependências do Chrome
RUN dpkg -i google-chrome-stable_current_amd64.deb || apt-get install -fy

# Baixa e instala o ChromeDriver correspondente
RUN wget https://storage.googleapis.com/chrome-for-testing-public/128.0.6600.0/linux64/chromedriver-linux64.zip
RUN unzip chromedriver-linux64.zip
RUN mv -f chromedriver-linux64/chromedriver /usr/local/bin/chromedriver
RUN chmod +x /usr/local/bin/chromedriver

# Copia o ficheiro de dependências
[cite_start]COPY requirements.txt . [cite: 1]

# Instala as dependências do Python
[cite_start]RUN pip install --no-cache-dir -r requirements.txt [cite: 2]

# Copia todo o código da aplicação para o diretório de trabalho
COPY . [cite_start]. [cite: 2, 3]

# Copia o script de arranque para dentro do contentor
[cite_start]COPY startup.sh . [cite: 3]
# Torna o script de arranque executável
[cite_start]RUN chmod +x ./startup.sh [cite: 4]

# Define o script de arranque como o ponto de entrada do contentor
[cite_start]CMD ["./startup.sh"] [cite: 4]