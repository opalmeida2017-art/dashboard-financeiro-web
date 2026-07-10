"""Helper para URL do painel (multi-tenant Debian)."""
from __future__ import annotations

from urllib.parse import parse_qsl, urlencode

from flask import session, url_for

# Datas amplas (ex. 2025–2026) recarregam todo o SATI e deixam "Voltar ao painel" lento.
_QS_IGNORAR_VOLTAR = frozenset({"start_date", "end_date"})


def _filtrar_qs_voltar_painel(query_string: str) -> str:
    pairs = [
        (k, v)
        for k, v in parse_qsl(query_string.lstrip("?"), keep_blank_values=True)
        if k not in _QS_IGNORAR_VOLTAR
    ]
    return urlencode(pairs, doseq=True)


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
        qs = _filtrar_qs_voltar_painel(query_string)
        if not qs:
            return base
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}{qs}"
    return base
