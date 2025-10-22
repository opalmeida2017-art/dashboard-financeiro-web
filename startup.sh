#!/bin/bash

# 1. ATIVA O LOG MAIS DETALHADO DO BASH
# 'set -x' imprime CADA comando que o script executa.
# 'set -e' faz o script sair imediatamente se um comando falhar.
set -ex

echo "[startup.sh] --- INICIANDO SCRIPT DE ARRANQUE (MODO DEBUG) ---"

# --- CORREÇÃO IMPORTANTE ---
# Ativa o ambiente virtual específico encontrado para este ambiente.
# Isso adiciona os executáveis instalados (como Gunicorn) ao PATH.
echo "[startup.sh] Ativando ambiente virtual..."
source /opt/jelastic-python311/lib/python3.11/venv/scripts/common/activate
echo "[startup.sh] Ambiente virtual ativado."
# -------------------------

# 2. APLICA AS MIGRAÇÕES (como no seu script original)
echo "[startup.sh] Tentando aplicar migrações Alembic..."
# Usar 'python -m alembic' é uma boa prática
python -m alembic upgrade head
EXIT_CODE=$?
# Checa se a migração falhou (não queremos parar o startup por isso, mas avisamos)
if [ $EXIT_CODE -ne 0 ]; then
    echo "[startup.sh] AVISO: 'alembic upgrade head' falhou com código $EXIT_CODE. O app pode ter problemas com o banco de dados."
    # Não usamos 'exit' aqui para permitir que o Gunicorn tente iniciar mesmo assim
else
    echo "[startup.sh] Migrações Alembic aplicadas (ou já estavam atualizadas)."
fi

# 3. INICIA O GUNICORN (A CORREÇÃO PRINCIPAL)
# A porta 80 é a porta padrão que o NGINX/Apache espera no SaveInCloud para encaminhar tráfego.
echo "[startup.sh] Iniciando Gunicorn na PORTA 80..."

# 'exec' substitui este script pelo processo do Gunicorn.
# O Gunicorn agora deve ser encontrado por causa do 'source activate' acima.
exec gunicorn app:app \
    --bind 0.0.0.0:80 \
    --workers 1 \
    --log-level=debug \
    --access-logfile=- \
    --error-logfile=-

# Esta linha nunca será executada se o 'exec' funcionar
echo "[startup.sh] ERRO CRÍTICO: O Gunicorn falhou ao iniciar após o comando exec!"
exit 1

