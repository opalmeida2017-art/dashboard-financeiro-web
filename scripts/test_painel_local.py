"""Testa rotas principais do painel (modo local)."""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("BIWEB_LOCAL_DEV", "1")

from app import create_app

app = create_app()

ENDPOINTS = [
    ("GET", "/", {}),
    ("GET", "/api/monthly_summary", {"start_date": "2026-01-01", "end_date": "2026-06-20"}),
    ("GET", "/api/bi_audit", {"metric": "receita_frete", "start_date": "2026-01-01", "end_date": "2026-06-20"}),
    ("GET", "/visao_comercial", {}),
    ("GET", "/visao/volume", {}),
    ("GET", "/fluxo_viagem", {}),
]

GC_ANALISES = list(range(1, 8))
VB_VISOES = ["volume", "custos", "margem", "exploratorio"]


def main():
    ok, fail = 0, 0
    with app.test_client() as c:
        for method, path, qs in ENDPOINTS:
            r = c.get(path, query_string=qs) if method == "GET" else c.post(path, query_string=qs)
            status = "OK" if r.status_code < 400 else f"ERRO {r.status_code}"
            if r.status_code >= 400:
                fail += 1
                print(f"{status} {path} -> {r.data[:200]!r}")
            else:
                ok += 1
                print(f"{status} {path}")

        for aid in GC_ANALISES:
            path = "/api/gestao_comercial_data"
            r = c.get(path, query_string={"analise": aid, "start_date": "2026-01-01", "end_date": "2026-06-20"})
            if r.status_code >= 400:
                fail += 1
                print(f"ERRO {path}?analise={aid} -> {r.status_code} {r.data[:300]!r}")
            else:
                ok += 1
                print(f"OK {path}?analise={aid}")

        for vk in VB_VISOES:
            r = c.get(f"/visao/{vk}")
            if r.status_code >= 400:
                fail += 1
                print(f"ERRO /visao/{vk} -> {r.status_code}")
            else:
                ok += 1
                print(f"OK /visao/{vk}")

            r2 = c.get(
                "/api/visao_bi_data",
                query_string={"visao": vk, "analise": 1, "start_date": "2026-01-01", "end_date": "2026-06-20"},
            )
            if r2.status_code >= 400:
                fail += 1
                print(f"ERRO /api/visao_bi_data?visao={vk} -> {r2.status_code} {r2.data[:300]!r}")
            else:
                ok += 1
                print(f"OK /api/visao_bi_data?visao={vk}")

    print(f"\n--- {ok} ok, {fail} falhas ---")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
