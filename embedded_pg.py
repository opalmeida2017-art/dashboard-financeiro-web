"""PostgreSQL portátil embutido (pasta runtime/postgresql)."""

from __future__ import annotations

import os
import socket
import subprocess
import time
from pathlib import Path

from biweb_paths import (
    app_root,
    ensure_data_dirs,
    pg_data_dir,
    pg_log_file,
    runtime_postgresql_dir,
)


def pg_bin(name: str) -> Path:
    base = runtime_postgresql_dir() / "bin"
    exe = name if name.endswith(".exe") else f"{name}.exe"
    path = base / exe
    if not path.exists():
        path = base / name
    if not path.exists():
        raise FileNotFoundError(
            f"Ferramenta PostgreSQL não encontrada: {path}\n"
            "Copie o PostgreSQL portátil para runtime/postgresql (veja runtime/postgresql/README.md)."
        )
    return path


def pg_port() -> int:
    try:
        return int(os.getenv("BIWEB_PG_PORT", "5433"))
    except ValueError:
        return 5433


def is_port_open(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def _run(cmd: list, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        **kwargs,
    )


def init_cluster_if_needed() -> None:
    data = pg_data_dir()
    if (data / "PG_VERSION").exists():
        return
    ensure_data_dirs()
    data.mkdir(parents=True, exist_ok=True)
    initdb = pg_bin("initdb")
    proc = _run(
        [
            str(initdb),
            "-D",
            str(data),
            "-U",
            "postgres",
            "--encoding=UTF8",
            "--locale=C",
        ],
        env={**os.environ, "PGTZ": "UTC"},
    )
    if proc.returncode != 0:
        raise RuntimeError(f"initdb falhou:\n{proc.stderr}\n{proc.stdout}")


def start_server() -> None:
    port = pg_port()
    if is_port_open(port):
        return
    init_cluster_if_needed()
    pg_ctl = pg_bin("pg_ctl")
    log = pg_log_file()
    log.parent.mkdir(parents=True, exist_ok=True)
    proc = _run(
        [
            str(pg_ctl),
            "start",
            "-D",
            str(pg_data_dir()),
            "-l",
            str(log),
            "-o",
            f"-p {port}",
        ],
        env={**os.environ},
    )
    if proc.returncode != 0 and "already running" not in (proc.stderr or "").lower():
        raise RuntimeError(f"pg_ctl start falhou:\n{proc.stderr}\n{proc.stdout}")
    for _ in range(40):
        if is_port_open(port):
            return
        time.sleep(0.25)
    raise TimeoutError(f"PostgreSQL não respondeu na porta {pg_port()}.")


def stop_server() -> None:
    if not (pg_data_dir() / "PG_VERSION").exists():
        return
    try:
        pg_ctl = pg_bin("pg_ctl")
        _run([str(pg_ctl), "stop", "-D", str(pg_data_dir()), "fast"])
    except FileNotFoundError:
        pass


def psql_cmd(*args: str) -> list[str]:
    return [str(pg_bin("psql")), *args]


def ensure_role_and_database() -> None:
    load = _load_pg_env()
    user = os.getenv("BIWEB_PG_USER", "biweb")
    pwd = os.getenv("BIWEB_PG_PASSWORD", "")
    db = os.getenv("BIWEB_PG_DATABASE", "biweb_sati")

    admin = psql_cmd(
        "-h",
        "127.0.0.1",
        "-p",
        str(pg_port()),
        "-U",
        "postgres",
        "-d",
        "postgres",
        "-v",
        "ON_ERROR_STOP=1",
        "-tAc",
        f"SELECT 1 FROM pg_roles WHERE rolname='{user}'",
    )
    proc = _run(admin, env=load)
    if proc.stdout.strip() != "1":
        _run(
            psql_cmd(
                "-h",
                "127.0.0.1",
                "-p",
                str(pg_port()),
                "-U",
                "postgres",
                "-d",
                "postgres",
                "-c",
                f"CREATE ROLE {user} WITH LOGIN PASSWORD '{pwd.replace(chr(39), chr(39)*2)}' CREATEDB;",
            ),
            env=load,
        )

    chk_db = _run(
        psql_cmd(
            "-h",
            "127.0.0.1",
            "-p",
            str(pg_port()),
            "-U",
            "postgres",
            "-d",
            "postgres",
            "-tAc",
            f"SELECT 1 FROM pg_database WHERE datname='{db}'",
        ),
        env=load,
    )
    if chk_db.stdout.strip() != "1":
        _run(
            psql_cmd(
                "-h",
                "127.0.0.1",
                "-p",
                str(pg_port()),
                "-U",
                "postgres",
                "-d",
                "postgres",
                "-c",
                f"CREATE DATABASE {db} OWNER {user} ENCODING 'UTF8';",
            ),
            env=load,
        )


def _load_pg_env() -> dict:
    env = {**os.environ}
    data = pg_data_dir()
    env["PGDATA"] = str(data)
    return env


def pg_restore_path() -> str:
    return str(pg_bin("pg_restore"))


def ensure_postgresql_running() -> None:
    if not (runtime_postgresql_dir() / "bin").exists():
        if os.getenv("SATI_DATABASE_URL", "").strip():
            return
        raise FileNotFoundError(
            f"Pasta PostgreSQL não encontrada em {runtime_postgresql_dir()}.\n"
            "Siga runtime/postgresql/README.md para instalar o motor antes de gerar o .exe."
        )
    start_server()
    ensure_role_and_database()
