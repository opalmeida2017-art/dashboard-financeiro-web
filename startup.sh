#!/bin/bash

# 1. ATIVA O LOG MAIS DETALHADO DO BASH
# 'set -x' imprime CADA comando que o script executa.
# Isso é o MÁXIMO de log que você pode ter.
set -x

echo "[startup.sh] --- INICIANDO SCRIPT DE ARRANQUE (MODO DEBUG) ---"

# 2. APLICA AS MIGRAÇÕES (como no seu script original)
echo "[startup.sh] Tentando aplicar migrações Alembic..."
# Usar 'python -m alembic' é uma boa prática
python -m alembic upgrade head
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo "[startup.sh] AVISO: 'alembic upgrade head' falhou com código $EXIT_CODE. O app pode não funcionar."
else
    echo "[startup.sh] Migrações Alembic aplicadas (ou já estavam atualizadas)."
fi

# 3. INICIA O GUNICORN (A CORREÇÃO PRINCIPAL)
# Mudamos a porta para 80, que é a porta padrão que o NGINX procura.
echo "[startup.sh] Iniciando Gunicorn na PORTA 80 (para o NGINX)..."

# 'exec' substitui este script pelo processo do gunicorn (correto para Docker)
exec gunicorn app:app \
    --bind 0.0.0.0:80 \
    --workers 4 \
    --log-level=debug \
    --access-logfile=- \
    --error-logfile=-

# Esta linha nunca será executada se o 'exec' funcionar
echo "[startup.sh] ERRO: O Gunicorn falhou ao iniciar!"
exit 1