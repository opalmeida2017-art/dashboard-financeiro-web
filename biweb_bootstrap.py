"""Primeira execução: tabelas BIWEB no PostgreSQL local."""

from __future__ import annotations

import os
from pathlib import Path

from biweb_paths import resource_root
from embedded_pg import ensure_postgresql_running, psql_cmd, _run, _load_pg_env


def _sql_bootstrap_file() -> Path:
    p = resource_root() / "sql" / "criar_tabelas_biweb_apartamento.sql"
    if not p.exists():
        p = Path(__file__).resolve().parent / "sql" / "criar_tabelas_biweb_apartamento.sql"
    return p


def _bootstrap_postgres_url() -> None:
    """Cria tabelas BIWEB no PostgreSQL definido em DATABASE_URL."""
    from sqlalchemy import create_engine, text

    url = os.getenv("DATABASE_URL", "")
    if not url.startswith("postgresql"):
        return

    sql_file = _sql_bootstrap_file()
    if not sql_file.exists():
        return

    eng = create_engine(url)
    script = sql_file.read_text(encoding="utf-8")
    with eng.begin() as conn:
        for stmt in script.split(";"):
            s = stmt.strip()
            if s and not s.startswith("--"):
                try:
                    conn.execute(text(s))
                except Exception as e:
                    print(f"[bootstrap] aviso SQL: {e}")


def _bootstrap_sqlite() -> None:
    from sqlalchemy import create_engine, text

    from biweb_paths import resource_root

    url = os.getenv("DATABASE_URL", "")
    if not url.startswith("sqlite"):
        return

    sql_file = resource_root() / "sql" / "criar_tabelas_biweb_sqlite.sql"
    if not sql_file.exists():
        sql_file = Path(__file__).resolve().parent / "sql" / "criar_tabelas_biweb_sqlite.sql"
    if not sql_file.exists():
        return

    eng = create_engine(url)
    script = sql_file.read_text(encoding="utf-8")
    with eng.begin() as conn:
        for stmt in script.split(";"):
            s = stmt.strip()
            if s:
                conn.execute(text(s))


def bootstrap_database() -> None:
    from biweb_paths import data_root
    from biweb_env import get_db_mode

    flag = data_root() / ".schema_ok"
    if flag.exists():
        return

    mode = get_db_mode()

    if mode == "sqlite" or os.getenv("DATABASE_URL", "").startswith("sqlite"):
        try:
            _bootstrap_sqlite()
        except Exception as e:
            print(f"[bootstrap] sqlite: {e}")
        flag.write_text("ok", encoding="utf-8")
    elif mode == "embedded":
        try:
            ensure_postgresql_running()
        except FileNotFoundError:
            return

        sql_file = _sql_bootstrap_file()
        if not sql_file.exists():
            return

        user = os.getenv("BIWEB_PG_USER", "biweb")
        db = os.getenv("BIWEB_PG_DATABASE", "biweb_sati")
        port = os.getenv("BIWEB_PG_PORT", "5433")

        proc = _run(
            psql_cmd(
                "-h",
                "127.0.0.1",
                "-p",
                str(port),
                "-U",
                user,
                "-d",
                db,
                "-v",
                "ON_ERROR_STOP=0",
                "-f",
                str(sql_file),
            ),
            env=_load_pg_env(),
        )
        if proc.returncode not in (0, None):
            print(f"[bootstrap] aviso psql: {proc.stderr}")

        flag.write_text("ok", encoding="utf-8")
    elif mode == "installed":
        try:
            _bootstrap_postgres_url()
        except Exception as e:
            print(f"[bootstrap] installed: {e}")
        flag.write_text("ok", encoding="utf-8")
    else:
        if os.getenv("DATABASE_URL", "").startswith("sqlite"):
            try:
                _bootstrap_sqlite()
            except Exception as e:
                print(f"[bootstrap] sqlite: {e}")
        elif os.getenv("DATABASE_URL", "").startswith("postgresql"):
            try:
                _bootstrap_postgres_url()
            except Exception as e:
                print(f"[bootstrap] postgres: {e}")
        flag.write_text("ok", encoding="utf-8")

    try:
        from biweb_env import load_env

        load_env()
        from app import create_app
        from tenant import ensure_transportadora

        app = create_app()
        with app.app_context():
            ensure_transportadora()
    except Exception as e:
        print(f"[bootstrap] ensure_transportadora: {e}")
