#!/bin/bash

# Este script prepara e inicia a aplicação Flask em produção.
set -e

# Sincroniza o estado da base de dados com o Alembic
echo "A sincronizar o estado da base de dados com 'alembic stamp head'..."
python -m alembic stamp head

# Inicia o servidor Gunicorn com o worker 'gevent' para estabilidade
echo "A iniciar o servidor Gunicorn..."
exec gunicorn app:app \
    --bind 0.0.0.0:$PORT \
    --workers 3 \
    --worker-class gevent \
    --timeout 120 \
    --log-level=debug \
    --access-logfile=- \
    --error-logfile=-