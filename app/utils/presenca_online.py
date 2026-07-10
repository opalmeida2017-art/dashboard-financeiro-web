"""Presença online por link/tenant — sessões ativas via Redis (heartbeat)."""

from __future__ import annotations

import json
import os
from typing import Any

_PREFIX = "biweb:online"
_TTL = int(os.getenv("BIWEB_PRESENCE_TTL", "120"))


def _redis():
    try:
        import redis

        url = os.getenv("REDIS_URL", "redis://localhost:6379").strip()
        if not url:
            return None
        return redis.from_url(url, decode_responses=True)
    except Exception:
        return None


def registrar_presenca(
    slug: str,
    session_id: str,
    usuario_nome: str = "",
    user_agent: str = "",
) -> bool:
    """Marca sessão ativa (TTL renovado a cada heartbeat)."""
    slug_norm = (slug or "").strip().lower()
    sid = (session_id or "").strip()
    if not slug_norm or not sid:
        return False
    r = _redis()
    if r is None:
        return False
    key = f"{_PREFIX}:{slug_norm}:{sid}"
    payload = json.dumps(
        {
            "usuario": (usuario_nome or "—")[:120],
            "ua": (user_agent or "")[:240],
        },
        ensure_ascii=False,
    )
    r.setex(key, _TTL, payload)
    return True


def listar_presenca(slug: str) -> dict[str, Any]:
    """Retorna total e lista de sessões ativas do slug."""
    slug_norm = (slug or "").strip().lower()
    if not slug_norm:
        return {"total": 0, "sessoes": []}
    r = _redis()
    if r is None:
        return {"total": 0, "sessoes": []}
    prefix = f"{_PREFIX}:{slug_norm}:"
    sessoes: list[dict[str, str]] = []
    try:
        for key in r.scan_iter(match=f"{prefix}*", count=500):
            raw = r.get(key)
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                data = {}
            sessoes.append(
                {
                    "usuario": str(data.get("usuario") or "—"),
                    "ua": str(data.get("ua") or ""),
                }
            )
    except Exception:
        return {"total": 0, "sessoes": []}
    return {"total": len(sessoes), "sessoes": sessoes}
