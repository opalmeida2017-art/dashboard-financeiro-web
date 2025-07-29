# Use uma imagem base do Python
FROM python:3.10-slim

# Defina o diretório de trabalho dentro do container
WORKDIR /app

# Copie o arquivo de dependências primeiro para aproveitar o cache do Docker
COPY requirements.txt .

# Instale as dependências
RUN pip install --no-cache-dir -r requirements.txt

# Copie todo o resto do seu projeto para o diretório de trabalho
COPY . .

# Comando para iniciar a aplicação em produção usando Gunicorn
# - Render define a variável de ambiente $PORT (que geralmente é 10000)
# - '--bind 0.0.0.0:$PORT' faz o app ficar acessível externamente na porta correta
# - '--workers 3' inicia 3 processos para lidar com múltiplas requisições
# - 'app:app' diz ao Gunicorn para procurar no arquivo "app.py" a variável "app"
CMD gunicorn --bind 0.0.0.0:$PORT --workers 3 app:app