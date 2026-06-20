"""Carrega .env do tenant Debian (banco exclusivo app + SATI)."""

from __future__ import annotations

import os
import re
from pathlib import Path

TENANTS_ROOT = Path(os.getenv("BI_TENANTS_ROOT", "/opt/biweb/tenants"))

_TENANT_ENV_KEYS = (
    "BI_TENANT_SLUG",
    "BI_TENANT_DIR",
    "BI_PG_DATABASE",
    "RAZAO_SOCIAL",
    "DATABASE_URL",
    "SATI_DATABASE_URL",
    "USE_SATI_SOURCE",
    "SATI_SCHEMA",
    "BIWEB_SKIP_LOGIN",
    "SATI_RESTORE_USE_SUDO_POSTGRES",
    "BIWEB_TRANSPORTADORA_ID",
)


def _parse_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        out[key.strip()] = val.strip().strip('"').strip("'")
    return out


def _resolver_pasta_por_slug(slug: str) -> Path | None:
    slug = str(slug or "").strip().lower()
    if not slug:
        return None
    direto = TENANTS_ROOT / slug
    if (direto / "tenant.env").is_file():
        return direto
    if not TENANTS_ROOT.is_dir():
        return None
    for child in TENANTS_ROOT.iterdir():
        if not child.is_dir():
            continue
        env = _parse_env_file(child / "tenant.env")
        if env.get("BI_TENANT_SLUG", "").strip().lower() == slug:
            return child
    return None


def tenant_dir(slug: str) -> Path:
    found = _resolver_pasta_por_slug(slug)
    if found:
        return found
    return TENANTS_ROOT / str(slug or "").strip().lower()


def load_tenant_env(slug: str) -> dict[str, str]:
    base = tenant_dir(slug)
    merged: dict[str, str] = {}
    merged.update(_parse_env_file(base / "tenant.env"))
    merged.update(_parse_env_file(base / ".env"))
    return merged


def apply_tenant_env(slug: str | None) -> bool:
    slug = (slug or "").strip().lower()
    if not slug:
        return False
    env = load_tenant_env(slug)
    if not env.get("DATABASE_URL"):
        return False
    for key in _TENANT_ENV_KEYS:
        if key in env:
            os.environ[key] = env[key]
    os.environ["BI_TENANT_SLUG"] = slug
    os.environ["BI_PG_DATABASE"] = env.get("BI_PG_DATABASE", f"bi_{slug.replace('-', '_')}")
    tenant_path = env.get("BI_TENANT_DIR") or str(tenant_dir(slug))
    os.environ["BI_TENANT_DIR"] = tenant_path
    return True


def slug_from_uri(uri: str) -> str | None:
    """Extrai slug de URLs /acesso/w-carlos ou /biweb/w-carlos."""
    if not uri:
        return None
    m = re.search(r"/(?:biweb|acesso)/([a-z0-9][a-z0-9_-]*)", uri, re.I)
    return m.group(1).lower() if m else None


def prepare_robot_context(
    tenant_slug: str | None = None, apartamento_id: int | None = None
) -> bool:
    """Aplica tenant.env antes do robô (worker RQ / fila assíncrona)."""
    slug = (tenant_slug or os.getenv("BI_TENANT_SLUG") or "").strip().lower()

    if not slug:
        try:
            from flask import has_request_context, session

            if has_request_context():
                slug = (session.get("bi_tenant_slug") or "").strip().lower()
        except Exception:
            pass

    if not slug and apartamento_id:
        try:
            from sqlalchemy import text

            from app.data.db_connection import engine

            with engine.connect() as conn:
                row = conn.execute(
                    text("SELECT slug FROM apartamentos WHERE id = :id LIMIT 1"),
                    {"id": apartamento_id},
                ).first()
            if row and row[0]:
                slug = str(row[0]).strip().lower()
        except Exception:
            pass

    if not slug:
        return False
    from infra.tenant_licensing.bi_tenant_context import set_tenant

    set_tenant(slug)
    if not apply_tenant_env(slug):
        return False
    from app.data.database import switch_engine_for_request

    switch_engine_for_request()
    return True


def resolve_tenant_slug_from_request(request) -> str | None:
    header = (request.headers.get("X-BI-Tenant-Slug") or "").strip().lower()
    if header:
        return header

    for key in ("HTTP_X_FORWARDED_URI", "HTTP_X_ORIGINAL_URI", "REQUEST_URI", "RAW_URI"):
        found = slug_from_uri(request.environ.get(key) or "")
        if found:
            return found

    referer = request.headers.get("Referer") or ""
    found = slug_from_uri(referer)
    if found:
        return found

    script = (request.environ.get("SCRIPT_NAME") or "").strip("/")
    if script:
        parts = [p for p in script.split("/") if p]
        if len(parts) >= 2 and parts[0] in ("biweb", "acesso"):
            return parts[1].lower()
        if parts and parts[0] not in ("static", "api"):
            return parts[-1].lower()

    path = (request.path or "").strip("/")
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 2 and parts[0] in ("biweb", "acesso"):
        return parts[1].lower()
    return None


def _biweb_multi_tenant_ativo() -> bool:
    """Debian: exige link /acesso/<slug> ou /biweb/<slug>."""
    if os.getenv("BIWEB_DESKTOP", "").strip():
        return False
    flag = os.getenv("BIWEB_REQUIRE_TENANT_LINK", "").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return False
    if flag in ("1", "true", "yes", "on"):
        return True
    return TENANTS_ROOT.is_dir()


def _request_tem_contexto_tenant(request) -> bool:
    """Só libera com slug na URL, header ou referer — sessão sozinha não abre o painel."""
    return bool(resolve_tenant_slug_from_request(request))


def _path_entrada_tenant(request) -> bool:
    path = (request.path or "").strip("/")
    parts = [p for p in path.split("/") if p]
    return len(parts) >= 2 and parts[0].lower() in ("acesso", "biweb")


def _path_e_raiz_dominio(request) -> bool:
    """Raiz do servidor sem prefixo /biweb|/acesso (ex.: / ou vazio)."""
    return not (request.path or "").strip("/")


def tenant_sessao_libera_rota_interna(request, session) -> bool:
    """
    Após entrar pelo link da transportadora, libera rotas internas (/visao_comercial, /api, / …).
    """
    slug = (session.get("bi_tenant_slug") or "").strip().lower()
    return bool(slug)
