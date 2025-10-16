#!/bin/bash
# Este script prepara e inicia a aplicação Flask em produção.
set -e

# Aplica as migrações do Alembic (cria e altera tabelas)
echo "A aplicar as migrações do Alembic com 'alembic upgrade head'..."
python -m alembic upgrade head

# --- CORREÇÃO: Inicia o Gunicorn com o worker 'gevent' para estabilidade ---
echo "A iniciar o servidor Gunicorn com worker gevent..."
exec gunicorn app:app \
    --bind 0.0.0.0:$PORT \
    --workers 2 \
    --worker-class gevent \
    --timeout 120 \
    --log-level=debug \
    --access-logfile=- \
    --error-logfile=-