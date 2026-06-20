import paramiko

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
BI = "/home/oitamar/dashboard-financeiro-web"
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=25)

script = r'''
import os, sys, traceback
sys.path.insert(0, "/home/oitamar/dashboard-financeiro-web")
os.chdir("/home/oitamar/dashboard-financeiro-web")

from infra.tenant_licensing.bi_tenant_runtime import apply_tenant_env
from app.data.database import switch_engine_for_request

for slug in ("wcarlos", "rio-bonito"):
    print("===", slug, "===")
    try:
        apply_tenant_env(slug)
        switch_engine_for_request()
        from app import app
        c = app.test_client()
        r = c.get("/", headers={
            "Host": "dadosfrete.duckdns.org",
            "X-BI-Tenant-Slug": slug,
        })
        print("status", r.status_code)
        if r.status_code >= 400:
            print(r.data[:1200].decode("utf-8", "replace"))
    except Exception:
        traceback.print_exc()
'''

sftp = c.open_sftp()
with sftp.open(f"{BI}/_tmp_test_tenant_err.py", "w") as f:
    f.write(script)
sftp.close()

_, o, e = c.exec_command(f"cd {BI} && ./venv/bin/python _tmp_test_tenant_err.py 2>&1", timeout=300)
print((o.read() + e.read()).decode("utf-8", "replace"))
c.exec_command(f"rm -f {BI}/_tmp_test_tenant_err.py")
c.close()
