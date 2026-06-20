"""Carrega variáveis de ambiente do .env do projeto."""

from __future__ import annotations

from dotenv import load_dotenv

from app.utils.paths import ensure_data_dirs, env_file, project_root
from app.utils.runtime import apply_runtime_defaults


def load_env() -> None:
    ensure_data_dirs()
    if env_file().exists():
        load_dotenv(env_file(), override=True)
    proj_env = project_root() / ".env"
    if proj_env.exists():
        load_dotenv(proj_env, override=False)
    apply_runtime_defaults()
