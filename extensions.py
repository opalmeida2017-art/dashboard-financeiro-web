# extensions.py
from functools import wraps

from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from sqlalchemy import text

# Import the User model and the database engine
from models import User
from db_connection import engine

bcrypt = Bcrypt()
login_manager = LoginManager()


def instalacao_login_required(view_func):
    """Instalação única: garante sessão local, sem bloquear rotas."""

    @wraps(view_func)
    def wrapped(*args, **kwargs):
        from tenant import try_auto_login

        try_auto_login()
        return view_func(*args, **kwargs)

    return wrapped


# Alias para substituir flask_login.login_required em toda a app
login_required = instalacao_login_required

@login_manager.user_loader
def load_user(user_id):
    """ This function is now the single source for loading a user. """
    with engine.connect() as conn:
        query = text("SELECT id, email, nome, apartamento_id, role FROM usuarios WHERE id = :user_id")
        user_data = conn.execute(query, {"user_id": int(user_id)}).mappings().first()
    if user_data:
        # The **user_data syntax automatically maps dictionary keys to class arguments
        return User(**user_data)
    return None