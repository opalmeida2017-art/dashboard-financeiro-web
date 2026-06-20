"""Helper para URL do painel (multi-tenant Debian)."""
from __future__ import annotations

from flask import session, url_for


def painel_home_url(query_string: str | None = None) -> str:
    """Raiz do painel: /biweb/<slug>/ no Debian ou url_for('main.index') local."""
    slug = (session.get("bi_tenant_slug") or "").strip().lower()
    try:
        from infra.tenant_licensing.bi_tenant_runtime import _biweb_multi_tenant_ativo

        multi = _biweb_multi_tenant_ativo()
    except Exception:
        multi = False
    if slug and multi:
        base = f"/biweb/{slug}/"
    else:
        base = url_for("main.index")
    if query_string:
        qs = query_string.lstrip("?")
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}{qs}"
    return base
