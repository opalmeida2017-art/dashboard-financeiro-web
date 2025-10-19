#!/bin/bash
# VERSÃO DE DEPURAÇÃO: Remove 'set -e' e adiciona mais logs.

echo "[startup.sh] --- INICIANDO SCRIPT DE ARRANQUE ---"

echo "[startup.sh] Tentando aplicar migrações Alembic..."
# Executa o upgrade, mas NÃO termina o script se falhar
python -m alembic upgrade head
EXIT_CODE=$? # Guarda o código de saída do Alembic
if [ $EXIT_CODE -ne 0 ]; then
    echo "[startup.sh] AVISO: 'alembic upgrade head' falhou com código $EXIT_CODE. Continuando..."
else
    echo "[startup.sh] Migrações Alembic aplicadas (ou já estavam atualizadas)."
fi

echo "[startup.sh] Iniciando Gunicorn AGORA..."
# O comando exec substitui o processo do script pelo Gunicorn
exec gunicorn app:app \
    --bind 0.0.0.0:8080 \
    --workers 4 \
    --log-level=debug \
    --access-logfile=- \
    --error-logfile=-