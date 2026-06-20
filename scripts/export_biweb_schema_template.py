#!/usr/bin/env python3
"""Exporta schema BIWEB (sem dados) do PostgreSQL Windows para sql/biweb_app_schema_template.sql."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_SQL = ROOT / "sql" / "biweb_app_schema_template.sql"
OUT_DUMP = ROOT / "sql" / "biweb_app_schema_template.dump"


def load_dotenv():
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def parse_pg_url(url: str) -> dict:
    from urllib.parse import unquote, urlparse

    u = urlparse(url)
    return {
        "host": u.hostname or "localhost",
        "port": str(u.port or 5432),
        "user": unquote(u.username or "postgres"),
        "password": unquote(u.password or ""),
        "database": (u.path or "/").lstrip("/") or "postgres",
    }


def main() -> int:
    load_dotenv()
    url = os.getenv("DATABASE_URL", "").strip()
    if not url.startswith("postgresql"):
        print("DATABASE_URL PostgreSQL não configurada no .env", file=sys.stderr)
        return 1

    pg = parse_pg_url(url)
    env = os.environ.copy()
    if pg["password"]:
        env["PGPASSWORD"] = pg["password"]

    tables = (
        "apartamentos",
        "usuarios",
        "static_expense_groups",
        "configuracoes_robo",
        "notificacoes",
        "tb_logs_robo",
        "tb_user_activity",
        "despesas_viagem_associadas",
        "despesas_viagem_excluidas",
    )
    table_args = []
    for t in tables:
        table_args.extend(["-t", t])

    dump = subprocess.run(
        [
            "pg_dump",
            "-h",
            pg["host"],
            "-p",
            pg["port"],
            "-U",
            pg["user"],
            "-d",
            pg["database"],
            "-s",
            "--no-owner",
            "--no-privileges",
            *table_args,
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if dump.returncode != 0:
        print(dump.stderr[:800], file=sys.stderr)
        return dump.returncode

    header = (
        "-- Exportado de "
        f"{pg['database']}@{pg['host']}:{pg['port']} (schema only, sem dados)\n"
    )
    OUT_SQL.write_text(header + dump.stdout, encoding="utf-8")
    print(f"SQL: {OUT_SQL}")

    custom = subprocess.run(
        [
            "pg_dump",
            "-h",
            pg["host"],
            "-p",
            pg["port"],
            "-U",
            pg["user"],
            "-d",
            pg["database"],
            "-Fc",
            "-s",
            "--no-owner",
            "--no-privileges",
            *table_args,
            "-f",
            str(OUT_DUMP),
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if custom.returncode == 0:
        print(f"DUMP: {OUT_DUMP}")
    else:
        print(f"Aviso dump custom: {custom.stderr[:300]}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
