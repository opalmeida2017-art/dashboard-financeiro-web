# Dentro de alembic/env.py

import os
from logging.config import fileConfig

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
    """Run migrations in 'online' mode.

    """
    # --- INÍCIO DO CÓDIGO CORRIGIDO ---
    
    # Tenta obter a URL da base de dados diretamente da variável de ambiente
    db_url = os.getenv('DATABASE_URL')

    # Se a variável não estiver definida (ambiente local), usa a conexão SQLite
    if not db_url:
        print("DATABASE_URL não encontrada, usando a conexão local com financeiro.db...")
        connectable = database.get_db_connection()
    else:
        # Se a variável existir (ambiente de produção da Render), cria a conexão
        print(f"Conectando à base de dados de produção via DATABASE_URL...")
        connectable = create_engine(db_url)

    with connectable.connect() as connection:
        # O target_metadata fica como None porque não estamos a usar autogenerate
        context.configure(
            connection=connection, target_metadata=None
        )

        with context.begin_transaction():
            context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Pega a URL do banco de dados do alembic.ini
    # O Alembic substitui %(DB_URL)s pela variável de ambiente DATABASE_URL
    alembic_config = config.get_section(config.config_ini_section)
    db_url = alembic_config.get('DB_URL')

    # Se a URL não foi definida via variável de ambiente, usa a conexão local
    if not db_url:
        print("DATABASE_URL não encontrada, usando conexão local com financeiro.db")
        connectable = database.get_db_connection()
    else:
        print(f"Conectando à base de dados via DATABASE_URL...")
        connectable = create_engine(db_url)

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata = None
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
