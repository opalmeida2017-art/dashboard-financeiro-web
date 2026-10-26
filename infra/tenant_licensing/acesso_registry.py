"""Links pessoais do BI (/acesso/{tenant}/{usuario}) — mesmo banco da transportadora."""
from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ACESSOS_PATH = Path(os.getenv("BI_ACESSOS_FILE", ROOT / "data" / "acessos_bi.json"))


def slugify(texto: str) -> str:
    t = unicodedata.normalize("NFKD", str(texto or ""))
    t = t.encode("ascii", "ignore").decode("ascii")
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t.lower()).strip("-")
    return (t[:40] or "usuario").strip("-")


def _load() -> dict:
    if not ACESSOS_PATH.is_file():
        return {"acessos": []}
    try:
        raw = json.loads(ACESSOS_PATH.read_text(encoding="utf-8"))
        return {"acessos": list(raw.get("acessos") or [])}
    except Exception:
        return {"acessos": []}


def _save(data: dict) -> None:
    ACESSOS_PATH.parent.mkdir(parents=True, exist_ok=True)
    ACESSOS_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def list_acessos(tenant_slug: str | None = None) -> list[dict]:
    items = list(_load().get("acessos") or [])
    if tenant_slug:
        ts = str(tenant_slug).strip().lower()
        items = [a for a in items if str(a.get("tenant_slug") or "").lower() == ts]
    return items


def get_acesso(slug: str) -> dict | None:
    s = str(slug or "").strip().lower()
    if not s:
        return None
    for item in list_acessos():
        if str(item.get("slug") or "").lower() == s:
            return dict(item)
    return None


def acesso_exists(slug: str) -> bool:
    return get_acesso(slug) is not None


def acesso_for_tenant(usuario: str, tenant_slug: str) -> dict | None:
    a = get_acesso(usuario)
    if not a or not a.get("ativo", True):
        return None
    if str(a.get("tenant_slug") or "").lower() != str(tenant_slug or "").strip().lower():
        return None
    return a


def _urls(tenant_slug: str, usuario: str) -> tuple[str, str]:
    host = os.getenv("BI_PUBLIC_HOST", os.getenv("NFE_PUBLIC_HOST", "192.168.100.12"))
    ext = (
        os.getenv("BI_PUBLIC_EXTERNAL_URL", "").strip()
        or os.getenv("NFE_PUBLIC_EXTERNAL_URL", "").strip()
        or "https://dadosfrete.duckdns.org"
    ).rstrip("/")
    t = str(tenant_slug or "").strip().lower()
    u = str(usuario or "").strip().lower()
    lan = f"http://{host}/acesso/{t}/{u}"
    return lan, f"{ext}/acesso/{t}/{u}"


def enrich_acesso(item: dict) -> dict:
    out = dict(item)
    parent = str(out.get("tenant_slug") or "").lower()
    slug = str(out.get("slug") or "").lower()
    lan, ext = _urls(parent, slug)
    out["url"] = lan
    out["url_externa"] = ext
    out["tipo"] = "acesso_usuario"
    out["path_curto"] = f"/acesso/{parent}/{slug}" if parent and slug else ""
    return out


def register_acesso(nome: str, tenant_slug: str, slug: str | None = None) -> dict:
    from infra.tenant_licensing.bi_tenant_context import tenant_slug_registrado

    nome_ok = str(nome or "").strip()
    if not nome_ok:
        raise ValueError("Informe o nome do usuário.")
    parent = str(tenant_slug or "").strip().lower()
    if not parent:
        raise ValueError("Informe a transportadora base.")
    if not tenant_slug_registrado(parent):
        raise ValueError(f"Transportadora BI '{parent}' não está no registro.")

    slug_ok = slugify(slug or nome_ok)
    if tenant_slug_registrado(slug_ok) and slug_ok != parent:
        raise ValueError(f"O slug '{slug_ok}' já é uma transportadora. Use outro nome.")
    if acesso_exists(slug_ok):
        raise ValueError(f"Já existe link de usuário '{slug_ok}'.")

    item = {
        "slug": slug_ok,
        "nome": nome_ok,
        "tenant_slug": parent,
        "ativo": True,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    data = _load()
    data.setdefault("acessos", []).append(item)
    _save(data)
    return enrich_acesso(item)


def set_acesso_ativo(slug: str, ativo: bool) -> dict:
    s = str(slug or "").strip().lower()
    data = _load()
    found = None
    for item in data.get("acessos") or []:
        if str(item.get("slug") or "").lower() == s:
            item["ativo"] = bool(ativo)
            found = item
            break
    if not found:
        raise ValueError(f"Link de usuário '{slug}' não encontrado.")
    _save(data)
    return enrich_acesso(found)


def unregister_acesso(slug: str) -> bool:
    s = str(slug or "").strip().lower()
    data = _load()
    lista = [
        a
        for a in (data.get("acessos") or [])
        if str(a.get("slug") or "").lower() != s
    ]
    if len(lista) == len(data.get("acessos") or []):
        return False
    data["acessos"] = lista
    _save(data)
    return True
