"""Testa isolamento rio-bonito vs wcarlos no Debian."""
import paramiko
import json

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
BI = "/home/oitamar/dashboard-financeiro-web"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=25)

def run(cmd, t=60):
    _, o, e = c.exec_command(cmd, timeout=t)
    o.channel.settimeout(t)
    return (o.read() + e.read()).decode("utf-8", "replace")

checks = [
    f"grep -n '_df_cache_scope' {BI}/data_manager.py | head -2",
    f"grep -n 'X-BI-Tenant-Slug' {BI}/templates/layout.html | head -3",
    "curl -sI --max-time 10 -k https://dadosfrete.duckdns.org:8443/biweb/rio-bonito/ | head -3",
    "curl -sI --max-time 10 -k https://dadosfrete.duckdns.org:8443/biweb/wcarlos/ | head -3",
]

for cmd in checks:
    print(f"\n$ {cmd}")
    print(run(cmd, t=30))

# Contagem CT-es por tenant via API interna
py = r'''
import os, sys
sys.path.insert(0, "/home/oitamar/dashboard-financeiro-web")
os.chdir("/home/oitamar/dashboard-financeiro-web")

from infra.tenant_licensing.bi_tenant_runtime import apply_tenant_env
from app.data.database import switch_engine_for_request, engine
from sqlalchemy import text

for slug in ("rio-bonito", "wcarlos"):
    apply_tenant_env(slug)
    switch_engine_for_request()
    db = os.getenv("BI_PG_DATABASE", "?")
    schema = os.getenv("SATI_SCHEMA", "?")
    with engine.connect() as conn:
        n = conn.execute(text(f'SELECT COUNT(*) FROM "{schema}".conhecimento')).scalar()
    print(f"{slug}|db={db}|schema={schema}|ctes={n}")
'''

print("\n$ contagem CT-es por tenant")
print(run(f"cd {BI} && ./venv/bin/python -c {json.dumps(py)}", t=120))

# Teste HTTP com header
for slug in ("rio-bonito", "wcarlos"):
    cmd = (
        f'curl -s --max-time 15 -k -H "X-BI-Tenant-Slug: {slug}" '
        f'"https://dadosfrete.duckdns.org:8443/biweb/{slug}/" | '
        f'grep -oE "transportadora[^<]*" | head -1 || echo "(sem match html)"'
    )
    print(f"\n$ HTML {slug}")
    print(run(cmd, t=25))

c.close()
