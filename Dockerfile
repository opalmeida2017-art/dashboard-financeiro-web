# Dockerfile

# Passo 1: Começar com uma imagem base oficial e leve do Python.
# 'slim' é uma versão mais pequena, ideal para produção.
FROM python:3.10-slim

# Passo 2: Definir o diretório de trabalho dentro do contentor.
# Todos os comandos subsequentes serão executados a partir deste diretório.
WORKDIR /app

# Passo 3: Copiar o ficheiro de dependências PRIMEIRO.
# O Docker armazena em cache as camadas. Se requirements.txt não mudar,
# esta camada não será reconstruída, acelerando futuras builds.
COPY requirements.txt.

# Passo 4: Instalar as dependências do Python.
# --no-cache-dir reduz o tamanho da imagem final.
RUN pip install --no-cache-dir -r requirements.txt

# Passo 5: Copiar o resto do código da aplicação para o contentor.
COPY..

# Passo 6: Expor a porta que a aplicação irá ouvir.
# A Render irá ligar-se a esta porta. 10000 é uma porta comum não privilegiada.
EXPOSE 10000

# Passo 7: O comando para iniciar a aplicação.
# Usa-se Gunicorn, um servidor web de produção WSGI, em vez do servidor de desenvolvimento do Flask.
# --bind 0.0.0.0:10000 faz o servidor ouvir em todas as interfaces de rede na porta 10000.
# app:app refere-se ao objeto 'app' dentro do ficheiro 'app.py'.
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "app:app"]