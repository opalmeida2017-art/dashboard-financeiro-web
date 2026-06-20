# Utilitários das rotas Flask (sem importar flask no nível do módulo — evita ciclo com flask/cli.py).

from __future__ import annotations

import os
from datetime import datetime
from functools import wraps


def get_debug_flag() -> bool:
    """Usado pelo Flask CLI (flask/cli.py do venv aponta para este módulo)."""
    val = os.environ.get("FLASK_DEBUG")
    if val is not None:
        return val.lower() in ("1", "true", "yes", "on")
    return os.environ.get("FLASK_ENV", "production").lower() == "development"


def get_load_dotenv(default: bool = True) -> bool:
    val = os.environ.get("FLASK_SKIP_DOTENV")
    if val is not None:
        return val.lower() not in ("1", "true", "yes", "on")
    return default


def get_target_apartment_id():
    """Compatibilidade: retorna o ID da transportadora desta instalação."""
    from app.data.tenant import get_transportadora_id

    return get_transportadora_id()


def is_admin_in_context():
    from flask_login import current_user

    from app.data.tenant import try_auto_login

    try_auto_login()
    if current_user.is_authenticated:
        return current_user.role == "admin"
    return True


def admin_required(f):
    """Instalação única: todas as rotas administrativas ficam liberadas."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        return f(*args, **kwargs)

    return decorated_function


super_admin_required = admin_required


def parse_filters(args):
    filters = {
        "placa": args.getlist("placa") if args.getlist("placa") else ["Todos"],
        "filial": args.getlist("filial"),
        "unidade_embarque": args.getlist("unidade_embarque"),
        "embarcador": (args.get("embarcador") or "Todos").strip(),
        "start_date_str": args.get("start_date", ""),
        "end_date_str": args.get("end_date", ""),
        "tipo_negocio": args.get("tipo_negocio", "Todos"),
    }
    try:
        filters["start_date_obj"] = (
            datetime.strptime(filters["start_date_str"], "%Y-%m-%d")
            if filters["start_date_str"]
            else None
        )
        filters["end_date_obj"] = (
            datetime.strptime(filters["end_date_str"], "%Y-%m-%d").replace(
                hour=23, minute=59, second=59
            )
            if filters["end_date_str"]
            else None
        )
    except ValueError:
        filters["start_date_obj"] = None
        filters["end_date_obj"] = None
    return filters


def normalize_placa_filter(placa_val):
    """Converte filtro de placa (str ou list do parse_filters) em string única."""
    if isinstance(placa_val, list):
        if not placa_val or placa_val == ["Todos"] or "Todos" in placa_val:
            return "Todos"
        return str(placa_val[0]).strip().upper()
    if placa_val is None:
        return "Todos"
    return str(placa_val).strip().upper() or "Todos"
