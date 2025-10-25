# /var/www/webroot/ROOT/wsgi.py

import sys
import os

# Adiciona o diretório 'ROOT' ao path do Python
project_home = '/var/www/webroot/ROOT'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

try:
    from app import app as application

    # Log para sabermos que o WSGI carregou o app (opcional, mas útil)
    # Você verá isso no seu log de erro se a aplicação iniciar com sucesso
    print("--- WSGI: 'app' importado como 'application' com SUCESSO. ---")

except ImportError as e:
    # Se o app.py falhar na importação, veremos isso no log
    print(f"--- WSGI: FALHA ao importar 'app' do app.py ---")
    print(f"Erro: {e}")
    # Re-levanta a exceção para que o mod_wsgi saiba que falhou
    raise