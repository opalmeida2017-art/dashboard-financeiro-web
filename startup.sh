#!/bin/bash

# Este script prepara e inicia a aplicação Flask em produção.

# Termina o script imediatamente se qualquer comando falhar
set -e

# --- CORREÇÃO DEFINITIVA ---
# O comando 'stamp' força o Alembic a definir a versão da base de dados
# para a mais recente ('head') sem executar nenhuma migração.
# Isto sincroniza o Alembic com uma base de dados que já tem tabelas.
echo "A sincronizar o estado da base de dados com 'alembic stamp head'..."
python -m alembic stamp head

# 2. Inicia o servidor Gunicorn
#    Agora que a base de dados está 'carimbada', podemos iniciar a aplicação com segurança.
echo "A iniciar o servidor Gunicorn..."
exec gunicorn app:app \
    --bind 0.0.0.0:$PORT \
    --workers 3 \
    --log-level=debug \
    --access-logfile=- \
    --error-logfile=-