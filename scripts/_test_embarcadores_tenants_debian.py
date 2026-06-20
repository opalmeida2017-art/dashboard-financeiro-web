"""Testa get_unique_embarcadores por tenant no Debian."""
import base64
import paramiko

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"

py = b"""import os
from pathlib import Path
from sqlalchemy import create_engine, text

def parse_env(p):
    out = {}
    if not p.is_file():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out

import sys
sys.path.insert(0, "/home/oitamar/dashboard-financeiro-web")
os.chdir("/home/oitamar/dashboard-financeiro-web")

from infra.tenant_licensing.bi_tenant_runtime import apply_tenant_env
from infra.tenant_licensing.bi_tenant_context import set_tenant
from app.data.database import switch_engine_for_request
from app.data import data_manager as dm

for slug, apt in (("wcarlos", 1), ("rio-bonito", 2)):
    apply_tenant_env(slug)
    set_tenant(slug)
    switch_engine_for_request()
    os.environ["BIWEB_TRANSPORTADORA_ID"] = str(apt)
    emb = dm.get_unique_embarcadores(apt)
    print("===", slug, "count", len(emb))
    for e in emb:
        print(" ", e.get("label") or e.get("cod"))
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=25)
b64 = base64.b64encode(py).decode("ascii")
_, o, e = c.exec_command(
    f"cd /home/oitamar/dashboard-financeiro-web && echo {b64} | base64 -d | ./venv/bin/python",
    timeout=120,
)
o.channel.settimeout(120)
print((o.read() + e.read()).decode("utf-8", errors="replace"))
c.close()
