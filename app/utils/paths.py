"""Caminhos da aplicação web (SaaS / servidor)."""

from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def data_root() -> Path:
    override = os.getenv("BIWEB_DATA_DIR", "").strip()
    if override:
        return Path(override)
    return project_root()


def env_file() -> Path:
    return data_root() / ".env"


def downloads_dir(transportadora_id: int = 1) -> Path:
    tenant_path = os.getenv("BI_TENANT_DIR", "").strip()
    if tenant_path:
        try:
            from infra.tenant_licensing.bi_tenant_runtime import ensure_tenant_runtime_dirs

            slug = os.getenv("BI_TENANT_SLUG", "").strip().lower()
            if slug:
                tenant_path = str(ensure_tenant_runtime_dirs(slug, tenant_path))
                os.environ["BI_TENANT_DIR"] = tenant_path
        except Exception:
            pass
        d = Path(tenant_path) / "downloads" / str(transportadora_id)
        d.mkdir(parents=True, exist_ok=True)
        return d
    try:
        from infra.tenant_licensing.bi_tenant_context import get_slug
        from infra.tenant_licensing.bi_tenant_runtime import ensure_tenant_runtime_dirs

        slug = get_slug() or os.getenv("BI_TENANT_SLUG", "").strip().lower()
        if slug:
            tenant_path = ensure_tenant_runtime_dirs(slug)
            os.environ["BI_TENANT_DIR"] = str(tenant_path)
            d = tenant_path / "downloads" / str(transportadora_id)
            d.mkdir(parents=True, exist_ok=True)
            return d
    except Exception:
        pass
    d = data_root() / "downloads" / str(transportadora_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def ensure_data_dirs() -> None:
    data_root().mkdir(parents=True, exist_ok=True)
    (data_root() / "downloads").mkdir(parents=True, exist_ok=True)
