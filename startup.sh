#!/bin/bash
# Este script prepara e inicia a aplicação Flask em produção.
set -e

echo "--- Iniciando startup.sh ---"

# Tenta aplicar as migrações do Alembic, mas não falha o script se der erro
echo "Tentando aplicar as migrações do Alembic (upgrade head)..."
python -m alembic upgrade head || echo "AVISO: Falha no 'alembic upgrade head', mas continuando..."

# --- Inicia o Gunicorn ---
echo "Iniciando o servidor Gunicorn..."
# Usamos exec para que o Gunicorn substitua o processo do script
exec gunicorn app:app \
    --bind 0.0.0.0:8080 \
    --workers 4 \
    --log-level=info \
    --access-logfile=- \
    --error-logfile=-