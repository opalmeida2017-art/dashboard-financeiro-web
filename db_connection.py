# db_connection.py

import os
from sqlalchemy import create_engine
from dotenv import load_dotenv

# Carrega as variáveis de ambiente (como DATABASE_URL)
load_dotenv()

db_url = os.getenv('DATABASE_URL')
if not db_url:
    raise ValueError("DATABASE_URL não definida. Verifique seu arquivo .env")

# Cria o objeto 'engine' que será compartilhado por toda a aplicação
engine = create_engine(db_url)