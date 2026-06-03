"""Carrega/cria .env da instalação desktop."""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

from biweb_paths import app_root, data_root, ensure_data_dirs, env_file, is_frozen

# embedded  = PostgreSQL portátil junto do .exe (pasta runtime/postgresql)
# installed = PostgreSQL já instalado no Windows (Program Files) — recomendado em dev
# external/sqlite = legado (não usar com SAT só na web/AWS)
DB_MODES = frozenset({"embedded", "installed", "external", "sqlite"})


def get_db_mode() -> str:
    load_env()
    mode = os.getenv("BIWEB_DB_MODE", "").strip().lower()
    if mode in DB_MODES:
        return mode
    if os.getenv("DATABASE_URL", "").strip().lower().startswith("sqlite:"):
        return "sqlite"
    if os.getenv("BIWEB_USE_EMBEDDED_PG", "").lower() in ("1", "true", "yes"):
        return "embedded"
    if os.getenv("BIWEB_DESKTOP", "").strip():
        return "embedded"
    return "installed"


def load_env() -> None:
    ensure_data_dirs()
    if env_file().exists():
        load_dotenv(env_file(), override=True)
    proj_env = app_root() / ".env"
    if proj_env.exists():
        load_dotenv(proj_env, override=False)


def _default_pg_password() -> str:
    return secrets.token_urlsafe(12)


def write_default_env(
    *,
    pg_password: str | None = None,
    transportadora_nome: str = "Minha Transportadora",
    pg_port: int = 5433,
) -> Path:
    pwd = pg_password or _default_pg_password()
    db = "biweb_sati"
    user = "biweb"
    host = "127.0.0.1"
    url = f"postgresql://{user}:{quote_plus(pwd)}@{host}:{pg_port}/{db}"

    lines = [
        "# Gerado automaticamente pelo BIWEB Desktop",
        "# SAT na web (AWS): o robô baixa o ZIP e restaura neste PostgreSQL LOCAL.",
        "BIWEB_DB_MODE=embedded",
        f"DATABASE_URL={url}",
        f"SATI_DATABASE_URL={url}",
        "USE_SATI_SOURCE=true",
        "SATI_SCHEMA=c3332",
        f"BIWEB_PG_PORT={pg_port}",
        f"BIWEB_PG_PASSWORD={pwd}",
        f"BIWEB_PG_USER={user}",
        f"BIWEB_PG_DATABASE={db}",
        "EXECUTION_MODE=sync",
        "BIWEB_SKIP_LOGIN=true",
        "FLASK_ENV=production",
        f"SECRET_KEY={secrets.token_hex(32)}",
        f"BIWEB_TRANSPORTADORA_NOME={transportadora_nome}",
        "BIWEB_TRANSPORTADORA_ID=1",
        "BIWEB_SETUP_DONE=false",
        "ROBO_HEADLESS=true",
    ]
    try:
        from embedded_pg import pg_restore_path

        lines.append(f"SATI_PG_RESTORE={pg_restore_path()}")
    except Exception:
        pass
    ensure_data_dirs()
    env_file().write_text("\n".join(lines) + "\n", encoding="utf-8")
    load_dotenv(env_file(), override=True)
    return env_file()


def write_default_env_installed(
    transportadora_nome: str = "Minha Transportadora",
    pg_url: str | None = None,
) -> Path:
    """PostgreSQL normal instalado no Windows (sem motor portátil do BIWEB)."""
    url = (pg_url or os.getenv("SATI_DATABASE_URL") or os.getenv("DATABASE_URL", "")).strip()
    if not url:
        url = "postgresql://postgres:SUA_SENHA@localhost:5433/biweb_sati"

    lines = [
        "# BIWEB — PostgreSQL instalado no Windows (cópia local dos dados do SAT web)",
        "BIWEB_DB_MODE=installed",
        f"DATABASE_URL={url}",
        f"SATI_DATABASE_URL={url}",
        "USE_SATI_SOURCE=true",
        "SATI_SCHEMA=c3332",
        "EXECUTION_MODE=sync",
        "BIWEB_SKIP_LOGIN=true",
        "FLASK_ENV=production",
        f"SECRET_KEY={secrets.token_hex(32)}",
        f"BIWEB_TRANSPORTADORA_NOME={transportadora_nome}",
        "BIWEB_TRANSPORTADORA_ID=1",
        "BIWEB_SETUP_DONE=false",
        "ROBO_HEADLESS=true",
    ]
    pg_restore = os.getenv("SATI_PG_RESTORE", "").strip()
    if pg_restore:
        lines.append(f"SATI_PG_RESTORE={pg_restore}")
    else:
        for ver in ("17", "16", "15", "14", "13"):
            win = Path(f"C:/Program Files/PostgreSQL/{ver}/bin/pg_restore.exe")
            if win.exists():
                lines.append(f"SATI_PG_RESTORE={win}")
                break

    ensure_data_dirs()
    env_file().write_text("\n".join(lines) + "\n", encoding="utf-8")
    load_dotenv(env_file(), override=True)
    return env_file()


def write_default_env_external(
    transportadora_nome: str = "Minha Transportadora",
    sati_url: str | None = None,
) -> Path:
    """Modo leve: não instala PostgreSQL; aponta para o banco do SATI já existente."""
    sati = (sati_url or os.getenv("SATI_DATABASE_URL", "")).strip()
    if not sati:
        sati = "postgresql://postgres:SUA_SENHA@localhost:5433/sat1_sati_is"

    sqlite_path = (data_root() / "biweb_app.db").as_posix()
    app_url = f"sqlite:///{sqlite_path}"

    lines = [
        "# BIWEB — modo leve (sem PostgreSQL embutido)",
        "BIWEB_DB_MODE=sqlite",
        f"DATABASE_URL={app_url}",
        f"SATI_DATABASE_URL={sati}",
        "USE_SATI_SOURCE=true",
        "SATI_SCHEMA=c3332",
        "EXECUTION_MODE=sync",
        "BIWEB_SKIP_LOGIN=true",
        "FLASK_ENV=production",
        f"SECRET_KEY={secrets.token_hex(32)}",
        f"BIWEB_TRANSPORTADORA_NOME={transportadora_nome}",
        "BIWEB_TRANSPORTADORA_ID=1",
        "BIWEB_SETUP_DONE=false",
        "ROBO_HEADLESS=true",
    ]
    pg_restore = os.getenv("SATI_PG_RESTORE", "").strip()
    if pg_restore:
        lines.append(f"SATI_PG_RESTORE={pg_restore}")
    else:
        for ver in ("17", "16", "15", "14"):
            win = Path(f"C:/Program Files/PostgreSQL/{ver}/bin/pg_restore.exe")
            if win.exists():
                lines.append(f"SATI_PG_RESTORE={win}")
                break

    ensure_data_dirs()
    env_file().write_text("\n".join(lines) + "\n", encoding="utf-8")
    load_dotenv(env_file(), override=True)
    return env_file()


def ensure_env_exists() -> None:
    load_env()
    if os.getenv("DATABASE_URL", "").strip():
        return
    mode = os.getenv("BIWEB_DB_MODE", "embedded").strip().lower()
    if mode == "installed":
        write_default_env_installed()
    elif mode == "embedded":
        write_default_env()
    elif mode in ("sqlite", "external"):
        write_default_env_external()
    else:
        write_default_env()
    load_env()


def save_robo_credentials(url: str, usuario: str, senha: str) -> None:
    """Atualiza credenciais SAT no .env (complemento à tela Configurações)."""
    load_env()
    path = env_file()
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    updates = {
        "URL_LOGIN": url.strip(),
        "USUARIO_ROBO": usuario.strip(),
        "SENHA_ROBO": senha.strip(),
        "BIWEB_SETUP_DONE": "true",
    }
    for key, val in updates.items():
        line = f"{key}={val}"
        pattern = f"{key}="
        if pattern in text:
            out = []
            for ln in text.splitlines():
                if ln.startswith(pattern):
                    out.append(line)
                else:
                    out.append(ln)
            text = "\n".join(out)
        else:
            text = (text.rstrip() + "\n" + line) if text else line
    path.write_text(text.rstrip() + "\n", encoding="utf-8")
    load_dotenv(path, override=True)


def setup_completed() -> bool:
    load_env()
    if os.getenv("BIWEB_SETUP_DONE", "").lower() in ("1", "true", "yes"):
        return True
    return bool(
        os.getenv("URL_LOGIN", "").strip()
        and os.getenv("USUARIO_ROBO", "").strip()
        and os.getenv("SENHA_ROBO", "").strip()
    )


def init_desktop_environment() -> None:
    """Chamado pelo launcher antes de importar Flask."""
    if not is_frozen() and not os.getenv("BIWEB_DESKTOP", "").strip():
        load_env()
        return

    ensure_env_exists()
    mode = get_db_mode()

    if mode == "embedded":
        from embedded_pg import ensure_postgresql_running

        ensure_postgresql_running()
    # installed: PostgreSQL já está rodando no Windows — não sobe motor portátil

    from biweb_bootstrap import bootstrap_database

    bootstrap_database()
