# Dentro de alembic/env.py
# Dentro de alembic/env.py

import os
from logging.config import fileConfig
from dotenv import load_dotenv # <-- ADICIONE ESTA LINHA

load_dotenv() # <-- ADICIONE ESTA LINHA TAMBÉM

from sqlalchemy import engine_from_config

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Adicione estas importações no topo do seu env.py
import sys
from sqlalchemy import create_engine
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '..')))
import database # O nome do seu ficheiro database.py

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = None

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # A variável `connectable` deve ser a URL, não uma conexão já aberta.
    connectable = os.environ.get('DATABASE_URL')
    
    if connectable is None:
        # Se a variável de ambiente não estiver definida, use a URL local.
        # Isto é apenas um fallback para o ambiente local.
        print("DATABASE_URL não encontrada, usando conexão local...")
        connectable = "sqlite:///financeiro.db"
    
    # A partir daqui, o Alembic usa a URL (string) para criar a conexão
    # Ele sabe como lidar com a string 'postgres://...' ou 'sqlite://...'
    with create_engine(connectable).connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
