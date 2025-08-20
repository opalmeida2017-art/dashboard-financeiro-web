#!/bin/bash

# Este script prepara e inicia a aplicação Flask em produção.

# Termina o script imediatamente se qualquer comando falhar
set -e

# 1. Executa as migrações da base de dados
#    Isto garante que a base de dados está atualizada com o esquema mais recente.
echo "A executar as migrações da base de dados..."
alembic upgrade head

# 2. Inicia o servidor Gunicorn
#    'exec' substitui o processo do script pelo processo do Gunicorn,
#    o que é uma boa prática para a gestão de sinais no Docker.
echo "A iniciar o servidor Gunicorn..."
exec gunicorn app:app --bind 0.0.0.0:$PORT --workers 3