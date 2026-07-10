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


_SLUGS_BI_EXCLUIDOS = frozenset({"transportes-brasil-ltda"})


def list_active_bi_tenants(max_apartamento: int = 3) -> list[dict]:
    """Tenants BI ativos no painel com apartamento_id até max_apartamento (1–3)."""
    try:
        conn = _central_conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT slug, apartamento_id, pg_database
            FROM painel_bi_tenant
            WHERE ativo = TRUE
              AND apartamento_id IS NOT NULL
              AND apartamento_id <= %s
            ORDER BY apartamento_id, slug
            """,
            (int(max_apartamento),),
        )
        rows = cur.fetchall()
        conn.close()
        out: list[dict] = []
        for slug, apt_id, pg_db in rows:
            slug_norm = str(slug or "").strip().lower()
            if not slug_norm or slug_norm in _SLUGS_BI_EXCLUIDOS:
                continue
            out.append(
                {
                    "slug": slug_norm,
                    "apartamento_id": int(apt_id),
                    "pg_database": pg_db or db_name_for_slug(slug_norm),
                }
            )
        return out
    except Exception:
        return []


def tenant_slug_registrado(slug: str | None) -> bool:
    """Slug ativo no painel ou com tenant.env no servidor."""
    slug = (slug or "").strip().lower()
    if not slug or slug in _SLUGS_BI_EXCLUIDOS:
        return False
    reg = _lookup_registry(slug)
    if reg and reg.get("ativo", True):
        return True
    try:
        from infra.tenant_licensing.bi_tenant_runtime import _resolver_pasta_por_slug

        return _resolver_pasta_por_slug(slug) is not None
    except Exception:
        return False


def tenant_active(slug: str | None = None) -> bool:
    slug = (slug or get_slug() or "").strip().lower()
    if not slug:
        return False
    return tenant_slug_registrado(slug)


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
