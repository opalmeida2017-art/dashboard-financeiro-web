"""Filtro opcional por codProprietario — configurado no painel de licenças BI."""
from __future__ import annotations

CHAVE_CONFIG = "BI_COD_PROPRIETARIO"


def normalizar_cod_proprietario(valor) -> int | None:
    """Vazio ou inválido = sem filtro (BI completo da transportadora)."""
    if valor is None:
        return None
    s = str(valor).strip().lower()
    if s in ("", "0", "none", "null", "todos", "todos os"):
        return None
    try:
        n = int(float(s))
        return n if n > 0 else None
    except (ValueError, TypeError):
        return None
