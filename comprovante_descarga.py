# -*- coding: utf-8 -*-
"""Comprovante de descarga: cache do Painel de Documentos e texto extraído do PDF."""
from __future__ import annotations

import os
import re


def extrair_texto_arquivo(caminho: str | None) -> str:
    if not caminho or not os.path.isfile(caminho):
        return ""
    low = caminho.lower()
    if low.endswith(".pdf"):
        try:
            from pypdf import PdfReader

            partes = []
            for page in PdfReader(caminho).pages:
                t = page.extract_text() or ""
                if t.strip():
                    partes.append(t)
            return "\n".join(partes).strip()
        except Exception:
            try:
                import PyPDF2

                partes = []
                with open(caminho, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        t = page.extract_text() or ""
                        if t.strip():
                            partes.append(t)
                return "\n".join(partes).strip()
            except Exception:
                return ""
    if low.endswith((".png", ".jpg", ".jpeg")):
        return ""
    return ""


def _normalizar_item(item: dict, apartamento_id: int) -> dict:
    numero = item.get("numero_conhecimento")
    arquivo = item.get("arquivo_local") or ""
    texto = (item.get("texto_extraido") or "").strip()
    if not texto and arquivo:
        texto = extrair_texto_arquivo(arquivo)
    url_arquivo = None
    if arquivo and os.path.isfile(arquivo) and numero is not None:
        url_arquivo = f"/api/comprovante_descarga/{int(numero)}/arquivo"
    return {
        "numero_conhecimento": numero,
        "nomearq": item.get("nomearq") or "",
        "arquivo_local": arquivo if arquivo and os.path.isfile(arquivo) else None,
        "texto_extraido": texto,
        "url_aberta": item.get("url_aberta"),
        "url_arquivo": url_arquivo,
        "tem_arquivo": bool(arquivo and os.path.isfile(arquivo)),
        "tem_texto": bool(texto),
    }


def mapa_cache_por_numero(apartamento_id: int) -> dict[int, dict]:
    from robos.coletor_painel_documentos import carregar_cache_comprovantes

    out: dict[int, dict] = {}
    for item in carregar_cache_comprovantes(apartamento_id).get("itens") or []:
        n = item.get("numero_conhecimento")
        if n is None:
            continue
        try:
            out[int(n)] = _normalizar_item(item, apartamento_id)
        except (TypeError, ValueError):
            pass
    return out


def itens_para_numeros(apartamento_id: int, numeros: list[int]) -> list[dict]:
    cache = mapa_cache_por_numero(apartamento_id)
    resultado = []
    for n in numeros:
        try:
            chave = int(n)
        except (TypeError, ValueError):
            continue
        if chave in cache:
            resultado.append(cache[chave])
    return resultado


def comprovante_completo_no_cache(item: dict | None) -> bool:
    """Completo = PDF/texto já baixado (só nome no cache ainda dispara nova coleta)."""
    if not item:
        return False
    return bool(item.get("tem_arquivo") or item.get("tem_texto"))


def _caminho_lock_coleta(apartamento_id: int) -> str:
    try:
        from biweb_paths import downloads_dir

        pasta = os.path.abspath(str(downloads_dir(apartamento_id)))
    except Exception:
        pasta = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "downloads",
            str(apartamento_id),
        )
    os.makedirs(pasta, exist_ok=True)
    return os.path.join(pasta, "comprovantes_coleta_lock.json")


def carregar_lock_coleta(apartamento_id: int) -> dict:
    path = _caminho_lock_coleta(apartamento_id)
    if not os.path.isfile(path):
        return {"em_fila": [], "atualizado_em": None}
    try:
        import json
        from datetime import datetime, timedelta

        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        expira = datetime.fromisoformat(data.get("expira_em") or "2000-01-01")
        if datetime.now() > expira:
            return {"em_fila": [], "atualizado_em": None}
        return data
    except Exception:
        return {"em_fila": [], "atualizado_em": None}


def liberar_coleta_da_fila(apartamento_id: int, numeros: list[int] | None = None) -> None:
    """Remove CT-es da fila após falha ou conclusão (permite nova tentativa)."""
    import json
    from datetime import datetime, timedelta

    path = _caminho_lock_coleta(apartamento_id)
    lock = carregar_lock_coleta(apartamento_id)
    fila = set(int(n) for n in lock.get("em_fila") or [])
    if numeros is not None:
        for n in numeros:
            fila.discard(int(n))
    else:
        fila.clear()
    payload = {
        "em_fila": sorted(fila),
        "atualizado_em": datetime.now().isoformat(timespec="seconds"),
        "expira_em": (datetime.now() + timedelta(minutes=5)).isoformat(timespec="seconds"),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def registrar_coleta_em_fila(apartamento_id: int, numeros: list[int], minutos_ttl: int = 25) -> None:
    import json
    from datetime import datetime, timedelta

    path = _caminho_lock_coleta(apartamento_id)
    lock = carregar_lock_coleta(apartamento_id)
    fila = set(int(n) for n in lock.get("em_fila") or [])
    fila.update(int(n) for n in numeros)
    payload = {
        "em_fila": sorted(fila),
        "atualizado_em": datetime.now().isoformat(timespec="seconds"),
        "expira_em": (datetime.now() + timedelta(minutes=minutos_ttl)).isoformat(timespec="seconds"),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def filtrar_numeros_para_coleta_automatica(
    apartamento_id: int, numeros: list[int]
) -> list[int]:
    """Evita reenfileirar CT-es que já têm arquivo/texto ou estão na fila."""
    mapa = mapa_cache_por_numero(apartamento_id)
    lock_nums = set(int(n) for n in carregar_lock_coleta(apartamento_id).get("em_fila") or [])
    pendentes = []
    for n in numeros:
        try:
            chave = int(n)
        except (TypeError, ValueError):
            continue
        if chave in lock_nums:
            continue
        if comprovante_completo_no_cache(mapa.get(chave)):
            continue
        pendentes.append(chave)
    return pendentes


def resolver_caminho_arquivo(apartamento_id: int, numero: int) -> str | None:
    itens = itens_para_numeros(apartamento_id, [numero])
    if not itens:
        return None
    path = itens[0].get("arquivo_local")
    if path and os.path.isfile(path):
        return path
    return None
