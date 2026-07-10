"""Metas configuráveis do painel BI (margem % e R$/km)."""
from __future__ import annotations

CHAVE_MARGEM = "BI_META_MARGEM_PCT"
CHAVE_R_KM = "BI_META_R_KM"


def _parse_float(valor, default: float | None = None) -> float | None:
    if valor is None or valor == "":
        return default
    try:
        raw = str(valor).strip().replace("%", "").replace("R$", "").replace(" ", "")
        if "," in raw and "." in raw:
            # 1.234,56 → 1234.56
            raw = raw.replace(".", "").replace(",", ".")
        elif "," in raw:
            raw = raw.replace(",", ".")
        return float(raw)
    except (TypeError, ValueError):
        return default


def obter_metas_bi(apartamento_id: int) -> dict:
    """Lê metas do configuracoes_robo; defaults sensatos se vazio."""
    try:
        from app.data.data_manager import ler_configuracoes_robo
    except ImportError:
        from data_manager import ler_configuracoes_robo  # type: ignore

    cfg = ler_configuracoes_robo(apartamento_id) or {}
    margem = _parse_float(cfg.get(CHAVE_MARGEM), 15.0)
    r_km = _parse_float(cfg.get(CHAVE_R_KM), 4.0)
    return {
        "meta_margem_pct": margem,
        "meta_r_km": r_km,
    }


def formatar_delta_pct(atual: float, anterior: float) -> dict:
    """Variação percentual MoM (atual vs período anterior de mesma duração)."""
    if anterior is None or abs(float(anterior)) < 1e-9:
        if atual and abs(float(atual)) > 1e-9:
            return {"pct": None, "label": "novo", "tone": "neutral"}
        return {"pct": 0.0, "label": "0%", "tone": "neutral"}
    pct = (float(atual) - float(anterior)) / abs(float(anterior)) * 100.0
    sinal = "+" if pct >= 0 else ""
    tone = "up" if pct > 0.05 else ("down" if pct < -0.05 else "neutral")
    return {"pct": round(pct, 1), "label": f"{sinal}{pct:.1f}%".replace(".", ","), "tone": tone}


def status_vs_meta(valor: float, meta: float | None, *, maior_melhor: bool = True) -> dict:
    if meta is None:
        return {"ok": None, "label": "", "tone": "neutral"}
    if maior_melhor:
        ok = float(valor) >= float(meta)
    else:
        ok = float(valor) <= float(meta)
    meta_txt = f"{meta:g}".replace(".", ",")
    return {
        "ok": ok,
        "label": f"meta {meta_txt}",
        "tone": "up" if ok else "down",
    }
