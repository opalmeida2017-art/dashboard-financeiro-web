"""Cria banco PostgreSQL + pasta /opt/biweb/tenants/{slug} para uma transportadora."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import unquote, urlparse, urlunparse

TENANTS_ROOT = Path(os.getenv("BI_TENANTS_ROOT", "/opt/biweb/tenants"))
BRASIL_SLUG = "transportes-brasil-ltda"


def slugify(texto: str) -> str:
    t = unicodedata.normalize("NFKD", str(texto or ""))
    t = t.encode("ascii", "ignore").decode("ascii")
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t.lower()).strip("-")
    return (t[:40] or "empresa").strip("-")


def db_name_for_slug(slug: str) -> str:
    base = re.sub(r"[^a-z0-9_]", "_", str(slug or "").lower().strip())
    return f"bi_{base}"[:63]


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL não definida.")
    return url


def _url_com_banco(url: str, dbname: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(path=f"/{dbname}"))


def _pg_connect(dbname: str = "postgres"):
    import psycopg2

    parsed = urlparse(_database_url())
    return psycopg2.connect(
        host=parsed.hostname or "127.0.0.1",
        port=int(parsed.port or 5432),
        user=unquote(parsed.username or "postgres"),
        password=unquote(parsed.password or ""),
        dbname=dbname,
    )


def _criar_banco(pg_database: str) -> None:
    conn = _pg_connect("postgres")
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (pg_database,))
    if not cur.fetchone():
        cur.execute(f'CREATE DATABASE "{pg_database}"')
    cur.close()
    conn.close()


def _drop_banco(pg_database: str) -> None:
    protegidos = {"postgres", "template0", "template1", "dashboard_db", "nfe_web"}
    if pg_database in protegidos:
        raise ValueError(f"Não é permitido remover o banco {pg_database}.")
    conn = _pg_connect("postgres")
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        "WHERE datname = %s AND pid <> pg_backend_pid()",
        (pg_database,),
    )
    cur.execute(f'DROP DATABASE IF EXISTS "{pg_database}"')
    cur.close()
    conn.close()


def _clonar_schema(pg_database: str, template_db: str = "dashboard_db") -> None:
    parsed = urlparse(_database_url())
    host = parsed.hostname or "127.0.0.1"
    port = str(parsed.port or 5432)
    user = unquote(parsed.username or "postgres")
    password = unquote(parsed.password or "")
    env = os.environ.copy()
    env["PGPASSWORD"] = password
    dump = subprocess.run(
        [
            "pg_dump",
            "-h",
            host,
            "-p",
            port,
            "-U",
            user,
            "-s",
            "--no-owner",
            "--no-privileges",
            template_db,
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if dump.returncode != 0:
        raise RuntimeError(f"pg_dump falhou: {(dump.stderr or '')[:500]}")
    restore = subprocess.run(
        [
            "psql",
            "-h",
            host,
            "-p",
            port,
            "-U",
            user,
            "-d",
            pg_database,
            "-v",
            "ON_ERROR_STOP=1",
        ],
        input=dump.stdout,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if restore.returncode != 0:
        raise RuntimeError(f"psql schema falhou: {(restore.stderr or '')[:500]}")


def _tenant_dir(slug: str) -> Path:
    return TENANTS_ROOT / slugify(slug)


def _criar_pasta_tenant(slug: str, razao: str, pg_database: str) -> Path:
    pasta = _tenant_dir(slug)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "downloads").mkdir(exist_ok=True)
    (pasta / "logs").mkdir(exist_ok=True)
    db_url = _url_com_banco(_database_url(), pg_database)
    cfg = pasta / "tenant.env"
    cfg.write_text(
        (
            f"BI_TENANT_SLUG={slug}\n"
            f"BI_PG_DATABASE={pg_database}\n"
            f"RAZAO_SOCIAL={razao}\n"
            f"DATABASE_URL={db_url}\n"
            "BIWEB_SKIP_LOGIN=true\n"
        ),
        encoding="utf-8",
    )
    return pasta


def _inicializar_empresa(pg_database: str, razao_social: str, slug: str) -> int | None:
    razao = str(razao_social or "").strip()
    venc = (datetime.now() + timedelta(days=3650)).strftime("%Y-%m-%d")
    conn = _pg_connect(pg_database)
    try:
        conn.autocommit = False
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name='apartamentos'"
        )
        if not cur.fetchone():
            conn.commit()
            return None
        cur.execute("SELECT id FROM apartamentos ORDER BY id LIMIT 1")
        row = cur.fetchone()
        if row:
            cur.execute(
                "UPDATE apartamentos SET nome_empresa=%s, slug=%s, status='ativo' WHERE id=%s",
                (razao, slug, row[0]),
            )
            apt_id = row[0]
        else:
            cur.execute(
                """
                INSERT INTO apartamentos (nome_empresa, slug, status, data_criacao, data_vencimento)
                VALUES (%s, %s, 'ativo', NOW(), %s) RETURNING id
                """,
                (razao, slug, venc),
            )
            apt_id = cur.fetchone()[0]
        conn.commit()
        return apt_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _public_url(slug: str) -> str:
    host = os.getenv("BI_PUBLIC_HOST", "").strip() or "192.168.100.15"
    return f"http://{host}/biweb/{slug}/"


def _external_url(slug: str) -> str:
    ext = (
        os.getenv("BI_PUBLIC_EXTERNAL_URL", "").strip()
        or os.getenv("NFE_PUBLIC_EXTERNAL_URL", "").strip()
        or "https://dadosfrete.duckdns.org"
    ).rstrip("/")
    return f"{ext}/biweb/{slug}/"


def criar_instancia(razao_social: str, slug: str | None = None) -> dict:
    razao = str(razao_social or "").strip()
    if not razao:
        raise ValueError("Informe o nome da transportadora.")
    slug_norm = slugify(slug or razao)
    pg_db = db_name_for_slug(slug_norm)
    pasta = _tenant_dir(slug_norm)
    if (pasta / "tenant.env").is_file():
        raise ValueError(f"Já existe instância BI com slug '{slug_norm}'.")

    _criar_banco(pg_db)
    try:
        _clonar_schema(pg_db)
    except Exception:
        pass
    _criar_pasta_tenant(slug_norm, razao, pg_db)
    apt_id = None
    try:
        apt_id = _inicializar_empresa(pg_db, razao, slug_norm)
    except Exception:
        pass

    return {
        "slug": slug_norm,
        "razao_social": razao,
        "pg_database": pg_db,
        "apartamento_id": apt_id,
        "url": _public_url(slug_norm),
        "url_externa": _external_url(slug_norm),
        "tenant_dir": str(pasta),
        "ativo": True,
        "biweb_path": slug_norm,
    }


def remover_instancia(slug: str, drop_database: bool = True) -> dict:
    slug_norm = slugify(slug)
    if slug_norm == BRASIL_SLUG:
        raise ValueError("Transportes Brasil é a instância de referência e não pode ser removida.")
    pasta = _tenant_dir(slug_norm)
    if not pasta.is_dir() and not (pasta / "tenant.env").is_file():
        raise ValueError(f"Instância BI '{slug_norm}' não encontrada.")
    pg_db = db_name_for_slug(slug_norm)
    env_file = pasta / "tenant.env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("BI_PG_DATABASE="):
                pg_db = line.split("=", 1)[1].strip()
    if drop_database and pg_db:
        try:
            _drop_banco(pg_db)
        except Exception:
            pass
    if pasta.is_dir():
        shutil.rmtree(pasta, ignore_errors=True)
    return {"slug": slug_norm, "pg_database": pg_db}
