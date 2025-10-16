# Dockerfile

# 1. Imagem Base: Começamos com uma imagem Python 3.11-slim, que é leve e moderna.
FROM python:3.11-slim

# 2. Variáveis de Ambiente: Evita que instaladores peçam inputs interativos e garante que os logs do Python apareçam imediatamente.
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# 3. Instalação de Dependências do Sistema + Google Chrome + ChromeDriver + WeasyPrint
# Este é o passo crucial para que o Selenium e a geração de PDFs funcionem.
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    # Dependências do WeasyPrint (do seu Aptfile)
    libpango-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-xlib-2.0-0 \
    --no-install-recommends \
    # Adiciona o repositório oficial do Google Chrome
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    # Instala o Chrome
    && apt-get install -y google-chrome-stable \
    # Baixa e instala a versão do chromedriver correspondente à versão estável do Chrome
    && CHROME_DRIVER_VERSION=$(wget -qO- https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_STABLE) \
    && wget -q --continue -P /tmp https://storage.googleapis.com/chrome-for-testing-public/${CHROME_DRIVER_VERSION}/linux64/chromedriver-linux64.zip \
    && unzip /tmp/chromedriver-linux64.zip -d /usr/local/bin/ \
    # Limpeza para manter a imagem do contêiner o mais pequena possível
    && rm -rf /var/lib/apt/lists/* /tmp/*

# 4. Define o diretório de trabalho dentro do contêiner.
WORKDIR /app

# 5. Copia o ficheiro de dependências e instala todos os pacotes Python.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 6. Copia todo o código do seu projeto para dentro do contêiner.
COPY . .

# 7. Expõe a porta que o Gunicorn (o nosso servidor web de produção) irá usar.
EXPOSE 8000

# 8. Comando para iniciar a aplicação. O comando de migração do Alembic será executado separadamente.
# O Gunicorn é um servidor WSGI robusto para produção.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "app:app"]