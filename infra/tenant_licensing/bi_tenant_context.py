"""Contexto do tenant BI — banco dedicado por slug (painel de licenças)."""
from __future__ import annotations

import os
from contextvars import ContextVar
from functools import lru_cache

_current_slug: ContextVar[str | None] = ContextVar("bi_tenant_slug", default=None)
_current_db: ContextVar[str | None] = ContextVar("bi_pg_database", default=None)

CENTRAL_DB = os.getenv("NFE_PAINEL_DATABASE", os.getenv("PG_DATABASE", "nfe_web"))


def _central_conn():
    import re
    from urllib.parse import unquote

    import psycopg2

    url = os.getenv("DATABASE_URL", "").strip()
    m = re.match(
        r"postgresql(?:\+psycopg2)?://([^:]+):([^@]+)@([^:/]+)(?::(\d+))?/([^?]+)",
        url,
    )
    if not m:
        raise RuntimeError("DATABASE_URL inválida para lookup do painel")
    user, password, host, port, _db = m.groups()
    dbname = os.getenv("NFE_PAINEL_DATABASE", os.getenv("PG_DATABASE", "nfe_web"))
    return psycopg2.connect(
        host=host,
        port=int(port or 5432),
        user=unquote(user),
        password=unquote(password),
        dbname=dbname,
    )


@lru_cache(maxsize=64)
def _lookup_registry(slug: str) -> dict | None:
    slug = (slug or "").strip().lower()
    if not slug:
        return None
    try:
        conn = _central_conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT slug, razao_social, pg_database, ativo
            FROM painel_bi_tenant WHERE LOWER(slug)=%s LIMIT 1
            """,
            (slug,),
        )
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        return {
            "slug": row[0],
            "razao_social": row[1],
            "pg_database": row[2],
            "ativo": bool(row[3]),
        }
    except Exception:
        return None


def db_name_for_slug(slug: str) -> str:
    import re

    base = re.sub(r"[^a-z0-9_]", "_", str(slug or "").lower().strip())
    return f"bi_{base}"[:63]


def set_tenant(slug: str | None, pg_database: str | None = None) -> None:
    slug = (slug or "").strip().lower() or None
    _current_slug.set(slug)
    if pg_database:
        _current_db.set(pg_database)
    elif slug:
        reg = _lookup_registry(slug)
        _current_db.set((reg or {}).get("pg_database") or db_name_for_slug(slug))
    else:
        _current_db.set(None)


def get_slug() -> str | None:
    return _current_slug.get()


def get_pg_database() -> str:
    db = _current_db.get()
    if db:
        return db
    return os.getenv("BI_PG_DATABASE", "dashboard_db")


def tenant_active(slug: str | None = None) -> bool:
    slug = (slug or get_slug() or "").strip().lower()
    if not slug:
        return False
    reg = _lookup_registry(slug)
    return bool(reg and reg.get("ativo", True))


def tenant_downloads_dir(slug: str | None = None) -> str:
    tenant_path = os.getenv("BI_TENANT_DIR", "").strip()
    if tenant_path:
        return os.path.join(tenant_path, "downloads")
    try:
        from infra.tenant_licensing.bi_tenant_runtime import tenant_dir as resolve_tenant_dir

        slug = (slug or get_slug() or "default").strip().lower()
        return str(resolve_tenant_dir(slug) / "downloads")
    except Exception:
        slug = (slug or get_slug() or "default").strip().lower()
        root = os.getenv("BI_TENANTS_ROOT", "/opt/biweb/tenants")
        return os.path.join(root, slug, "downloads")
