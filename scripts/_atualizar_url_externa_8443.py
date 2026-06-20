"""Atualiza URLs externas para porta 8443 (4G — operadora bloqueia 80/443)."""
import paramiko

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
EXT = "https://dadosfrete.duckdns.org:8443"
PAINEL = "https://dadosfrete.duckdns.org:8443/painel_licenca/"

RUN = f'''
import os, re
from pathlib import Path

EXT = "{EXT}"
PAINEL = "{PAINEL}"

def patch_env(path):
    p = Path(path)
    if not p.is_file():
        return
    t = p.read_text(encoding="utf-8")
    reps = {{
        "BI_PUBLIC_EXTERNAL_URL": EXT,
        "NFE_PUBLIC_EXTERNAL_URL": EXT,
        "PAINEL_WEB_EXTERNAL_URL": PAINEL,
    }}
    for k, v in reps.items():
        if re.search(rf"^{{k}}=", t, re.M):
            t = re.sub(rf"^{{k}}=.*$", f"{{k}}={{v}}", t, flags=re.M)
        else:
            t += f"\\n{{k}}={{v}}\\n"
    p.write_text(t, encoding="utf-8")
    print("env ok", path)

patch_env("/opt/nfe-web/.env")

import sys
sys.path.insert(0, "/opt/nfe-web")
import painel_store as ps, bi_store as bs, web_tenant_registry as wr, bi_tenant_registry as br

conn = ps._connect_central()
conn.autocommit = True
cur = conn.cursor()
cur.execute(
    "INSERT INTO painel_meta (chave, valor) VALUES ('external_base_url', %s) "
    "ON CONFLICT (chave) DO UPDATE SET valor = EXCLUDED.valor",
    (EXT,),
)
conn.close()
bs.set_external_base_url(EXT)
ps.normalize_tenant_urls()
bs.normalize_bi_urls()

print("WEB")
for t in wr.list_tenants():
    e = wr.enrich_tenant(t)
    print(e["slug"], e.get("url_externa"))
print("BI")
for t in br.list_tenants():
    e = br.enrich_tenant(t)
    print(e["slug"], e.get("url_externa"))
'''


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=20)
    sftp = c.open_sftp()
    with sftp.open("/tmp/_url8443.py", "w") as f:
        f.write(RUN)
    sftp.close()
    _, o, e = c.exec_command(
        "cd /opt/nfe-web && ./venv/bin/python /tmp/_url8443.py 2>&1", timeout=90
    )
    print((o.read() + e.read()).decode("utf-8", "replace"))
    c.close()


if __name__ == "__main__":
    main()
