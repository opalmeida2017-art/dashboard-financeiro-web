# db_connection.py

import os
from sqlalchemy import create_engine

from biweb_env import load_env

load_env()

db_url = os.getenv("DATABASE_URL")
if not db_url:
    raise ValueError(
        "DATABASE_URL não definida. No desktop, execute BIWEB.exe ou crie .env em "
        "%LOCALAPPDATA%\\BIWEB\\.env"
    )

engine = create_engine(db_url)