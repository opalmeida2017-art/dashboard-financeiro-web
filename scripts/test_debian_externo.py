"""Testa links externos no Debian e opcionalmente faz deploy."""
from __future__ import annotations

import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
BI = "/home/oitamar/dashboard-financeiro-web"
EXT = "https://dadosfrete.duckdns.org:8443"
TENANTS = ("wcarlos", "rio-bonito")

PATHS = [
    "/api/monthly_summary?start_date=2026-01-01&end_date=2026-06-20",
    "/visao_comercial",
    "/visao/volume",
    "/fluxo_viagem",
    "/api/bi_audit?metric=receita_frete&start_date=2026-01-01&end_date=2026-06-20",
]

GC = [f"/api/gestao_comercial_data?analise={i}&start_date=2026-01-01&end_date=2026-06-20" for i in range(1, 8)]

PAINEL_QS = "start_date=2025-01-01&end_date=2026-06-20"


def run(c, cmd, t=120):
    _, o, e = c.exec_command(cmd, timeout=t)
    o.channel.settimeout(t)
    return (o.read() + e.read()).decode("utf-8", errors="replace")


def curl_status(c, url: str, cookie: str = "", timeout: int = 25) -> str:
    ck = f"-b {cookie} -c {cookie}" if cookie else ""
    cmd = f'curl -sk --max-time {timeout} {ck} -o /dev/null -w "%{{http_code}}" "{url}"'
    return run(c, cmd, t=timeout + 10).strip()


def test_tenant(c, slug: str) -> tuple[int, int]:
    cookie = f"/tmp/biweb_test_{slug}.cookie"
    run(c, f"rm -f {cookie}", t=10)
    ok = fail = 0
    entry = f"{EXT}/biweb/{slug}/"
    code = curl_status(c, entry, cookie)
    print(f"  ENTRADA {entry} -> {code}")
    if code == "200":
        ok += 1
    else:
        fail += 1

    painel_url = f"{EXT}/biweb/{slug}/?{PAINEL_QS}"
    painel_code = curl_status(c, painel_url, cookie, timeout=90)
    print(f"  PAINEL {painel_url} -> {painel_code}")
    if painel_code == "200":
        ok += 1
    else:
        fail += 1

    voltar_url = f"{EXT}/?{PAINEL_QS}"
    voltar_code = curl_status(c, voltar_url, cookie, timeout=90)
    print(f"  VOLTAR {voltar_url} -> {voltar_code}")
    if voltar_code == "200":
        ok += 1
    else:
        fail += 1
        print(f"  ERRO voltar painel deveria ser 200, obteve {voltar_code}")

    api_url = f"{EXT}/api/monthly_summary?{PAINEL_QS}"
    api_code = curl_status(c, api_url, cookie, timeout=90)
    print(f"  API 2025 {api_url} -> {api_code}")
    if api_code == "200":
        ok += 1
    else:
        fail += 1

    for path in PATHS + GC:
        url = f"{EXT}{path}"
        code = curl_status(c, url, cookie)
        tag = "OK" if code == "200" else f"ERRO {code}"
        if code == "200":
            ok += 1
        else:
            fail += 1
        if code != "200":
            print(f"  {tag} {path}")
    return ok, fail


def server_import_test(c) -> None:
    import base64

    py = b"""import os, sys
sys.path.insert(0, "/home/oitamar/dashboard-financeiro-web")
os.chdir("/home/oitamar/dashboard-financeiro-web")
os.environ.setdefault("BIWEB_PRODUCTION", "1")
from infra.tenant_licensing.bi_tenant_runtime import apply_tenant_env
from infra.tenant_licensing.bi_tenant_context import set_tenant
from app.data.database import switch_engine_for_request
from app import create_app
apply_tenant_env("wcarlos")
set_tenant("wcarlos")
switch_engine_for_request()
app = create_app()
with app.test_client() as client:
    with client.session_transaction() as s:
        s["bi_tenant_slug"] = "wcarlos"
    r = client.get("/visao_comercial")
    print("internal_visao", r.status_code)
    r2 = client.get("/api/gestao_comercial_data?analise=4&start_date=2026-01-01&end_date=2026-06-20")
    print("internal_gc4", r2.status_code)
"""
    b64 = base64.b64encode(py).decode("ascii")
    print(run(c, f"cd {BI} && echo {b64} | base64 -d | ./venv/bin/python", t=180))


def main():
    deploy = "--deploy" in sys.argv or "--confirmar-deploy" in sys.argv
    if deploy:
        from scripts._deploy_guard import exigir_confirmacao_deploy

        exigir_confirmacao_deploy("test_debian_externo")
        from scripts._deploy_debian_atual import main as deploy_main

        print("=== DEPLOY ===")
        deploy_main()
        print()

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)

    print("=== Gunicorn ===")
    print(run(c, "pgrep -af gunicorn | head -5 || true", t=20))

    print("\n=== Raiz (deve 403) ===")
    print(" / ->", curl_status(c, f"{EXT}/"))

    total_ok = total_fail = 0
    for slug in TENANTS:
        print(f"\n=== Tenant {slug} ===")
        ok, fail = test_tenant(c, slug)
        total_ok += ok
        total_fail += fail

    print("\n=== Teste import interno (wcarlos) ===")
    server_import_test(c)

    print(f"\n--- EXTERNO: {total_ok} ok, {total_fail} falhas ---")
    c.close()
    return 1 if total_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
