# Dockerfile (versão final, simplificada e robusta)

# Usa uma imagem base do Python mais recente (Bullseye)
FROM python:3.11-slim-bullseye

# Define o diretório de trabalho
WORKDIR /app

# Define o ambiente como não-interativo para evitar prompts
ENV DEBIAN_FRONTEND=noninteractive

# --- Instala o Chromium e o Driver (Método Simplificado) ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Copia e instala as dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o resto do seu projeto
COPY . .

# Comando para iniciar a aplicação web (Gunicorn)
CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "--workers", "3", "app:app"]