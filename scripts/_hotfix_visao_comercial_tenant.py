import paramiko
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
from scripts._deploy_guard import exigir_confirmacao_deploy

exigir_confirmacao_deploy("_hotfix_visao_comercial_tenant")

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
BI = "/home/oitamar/dashboard-financeiro-web"
LOCAL = r"c:\python\BIWEB"
FILES = ["app.py", "bi_tenant_runtime.py"]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=25)
sftp = c.open_sftp()
for rel in FILES:
    sftp.put(f"{LOCAL}\\{rel}", f"{BI}/{rel}")
    print("uploaded", rel)
sftp.close()


def run(cmd, t=90):
    _, o, e = c.exec_command(cmd, timeout=t)
    return (o.read() + e.read()).decode("utf-8", errors="replace")


print(run("pkill -f 'gunicorn.*127.0.0.1:8000.*app:app' || true"))
print(
    run(
        f"cd {BI} && ./venv/bin/gunicorn --workers 3 --worker-class gevent --bind 127.0.0.1:8000 "
        "--timeout 120 --daemon --pid /tmp/gunicorn-dashboard.pid app:app; sleep 2"
    )
)

script = r'''
import os, sys
sys.path.insert(0, "/home/oitamar/dashboard-financeiro-web")
os.chdir("/home/oitamar/dashboard-financeiro-web")
from infra.tenant_licensing.bi_tenant_runtime import apply_tenant_env
from app.data.database import switch_engine_for_request
apply_tenant_env("wcarlos")
switch_engine_for_request()
from app import app
c = app.test_client()
with c.session_transaction() as sess:
    sess["bi_tenant_slug"] = "wcarlos"
r = c.get("/visao_comercial/1")
print("visao_comercial status", r.status_code)
r2 = c.get("/")
print("raiz status", r2.status_code)
'''

sftp = c.open_sftp()
with sftp.open(f"{BI}/_tmp_test_visao.py", "w") as f:
    f.write(script)
sftp.close()
print(run(f"cd {BI} && ./venv/bin/python _tmp_test_visao.py 2>&1"))
print(run("curl -sI --max-time 15 -k https://dadosfrete.duckdns.org:8443/biweb/wcarlos/ | head -2"))
c.exec_command(f"rm -f {BI}/_tmp_test_visao.py")
c.close()
