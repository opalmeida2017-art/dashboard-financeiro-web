"""Caminhos da aplicação (desenvolvimento vs executável PyInstaller)."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def app_root() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def resource_root() -> Path:
    """Recursos empacotados (templates, static, sql, runtime)."""
    if is_frozen() and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return app_root()


def data_root() -> Path:
    """Dados graváveis do usuário (fora de Program Files quando instalado)."""
    override = os.getenv("BIWEB_DATA_DIR", "").strip()
    if override:
        return Path(override)
    if is_frozen():
        base = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or str(Path.home())
        return Path(base) / "BIWEB"
    return app_root()


def env_file() -> Path:
    return data_root() / ".env"


def pg_data_dir() -> Path:
    return data_root() / "pgdata"


def pg_log_file() -> Path:
    return data_root() / "postgresql.log"


def downloads_dir(transportadora_id: int = 1) -> Path:
    d = data_root() / "downloads" / str(transportadora_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def runtime_postgresql_dir() -> Path:
    custom = os.getenv("BIWEB_PG_HOME", "").strip()
    if custom:
        return Path(custom)
    return app_root() / "runtime" / "postgresql"


def ensure_data_dirs() -> None:
    data_root().mkdir(parents=True, exist_ok=True)
    (data_root() / "downloads").mkdir(parents=True, exist_ok=True)
