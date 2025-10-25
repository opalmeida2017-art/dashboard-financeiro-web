#!/bin/bash
set -ex # Habilita debug e saída em erro

echo "[startup.sh] --- INICIANDO SCRIPT DE ARRANQUE ---"

# 1. Aplica as migrações Alembic
# (Assume que 'alembic' está no PATH após 'pip install')
echo "[startup.sh] Tentando aplicar migrações Alembic..."
alembic upgrade head
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo "[startup.sh] AVISO: 'alembic upgrade head' falhou com código $EXIT_CODE."
else
    echo "[startup.sh] Migrações Alembic aplicadas (ou já estavam atualizadas)."
fi

# 2. Inicia o Gunicorn
# (Assume que 'gunicorn' está no PATH)
# --- CORREÇÃO: Usa porta 8000 ---
echo "[startup.sh] Iniciando Gunicorn na PORTA 8000..."
exec gunicorn app:app \
    --bind 0.0.0.0:8000 \
    --workers 1 \
    --log-level=debug \
    --access-logfile=- \
    --error-logfile=-

echo "[startup.sh] ERRO CRÍTICO: O Gunicorn falhou ao iniciar!"
exit 1