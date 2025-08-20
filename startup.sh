#!/bin/bash

# Este script prepara e inicia a aplicação Flask em produção.

# Termina o script imediatamente se qualquer comando falhar
set -e

# --- DIAGNÓSTICO DO ALEMBIC ---
# Estes comandos ajudam-nos a perceber o estado da base de dados
# antes de tentarmos fazer o upgrade.
echo "--- A verificar o estado do Alembic ---"
echo "A executar 'alembic current':"
python -m alembic current

echo "A executar 'alembic history':"
python -m alembic history
echo "------------------------------------"


# 1. Executa as migrações da base de dados
#    Usar 'python -m alembic' é mais fiável em alguns ambientes.
echo "A executar as migrações da base de dados..."
python -m alembic upgrade head

# 2. Inicia o servidor Gunicorn
echo "A iniciar o servidor Gunicorn..."
exec gunicorn app:app \
    --bind 0.0.0.0:$PORT \
    --workers 3 \
    --log-level=debug \
    --access-logfile=- \
    --error-logfile=-
