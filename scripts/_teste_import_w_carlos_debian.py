"""Teste restore SATI w-carlos — script no servidor."""
import paramiko
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
BI = "/home/oitamar/dashboard-financeiro-web"
REMOTE_PY = f"{BI}/scripts_teste_restore_w_carlos.py"
LOG = f"{BI}/teste_import_w_carlos.log"


def run(c, cmd, t=300):
    _, o, e = c.exec_command(cmd, timeout=t)
    o.channel.settimeout(t)
    try:
        return (o.read() + e.read()).decode("utf-8", errors="replace")
    except Exception:
        return ""


def sudo(c, cmd, t=60):
    i, o, _ = c.exec_command(f"sudo -S {cmd}", get_pty=True)
    i.write(PASS + "\n")
    i.flush()
    o.channel.settimeout(t)
    return o.read().decode("utf-8", errors="replace")


REMOTE_SCRIPT = r'''
import os
import sys
from pathlib import Path

BI = "/home/oitamar/dashboard-financeiro-web"
os.chdir(BI)
sys.path.insert(0, BI)

for line in open(".env"):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

os.environ["BI_TENANTS_ROOT"] = "/opt/biweb/tenants"

from infra.tenant_licensing.bi_tenant_context import set_tenant
from app.data.database import switch_engine_for_request
from sati_integration.robos from sati_integration.robos import sati_db_restore as sr

set_tenant("w-carlos")
switch_engine_for_request()

zip_path = Path(BI) / "downloads/1/SATI-c2910-atual.zip"
if not zip_path.is_file():
    raise SystemExit(f"ZIP ausente: {zip_path}")

print("ZIP:", zip_path)
print("Schema SATI esperado: c2910")
sr.processar_arquivo_zip_sati(zip_path, apartamento_id=1)
print("RESTORE_OK")
'''


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=20)

    sftp = c.open_sftp()
    with sftp.open(REMOTE_PY, "w") as f:
        f.write(REMOTE_SCRIPT)
    sftp.close()

    run(c, f"rm -f {BI}/data/sati_restore.lock; truncate -s 0 {LOG}", 15)
    run(c, "pkill -f scripts_teste_restore_w_carlos || true", 10)

    antes = "".join(ch for ch in sudo(c, "-u postgres psql -d sat1_sati_is -tAc \"SELECT COUNT(*) FROM c2910.conhecimento\"") if ch.isdigit())
    print(f"CT-es antes: {antes}")

    print("Iniciando restore...")
    run(
        c,
        f"cd {BI} && nohup ./venv/bin/python {REMOTE_PY} > {LOG} 2>&1 &",
        20,
    )

    ok = False
    for i in range(80):
        time.sleep(12)
        tail = run(c, f"tail -15 {LOG}", 30)
        print(f"--- {i+1} ---")
        print(tail[-2000:])
        if "RESTORE_OK" in tail or "Restore do schema SATI concluído" in tail:
            ok = True
            break
        if "Traceback" in tail or "pre-data incompleto" in tail:
            break

    depois = "".join(ch for ch in sudo(c, "-u postgres psql -d sat1_sati_is -tAc \"SELECT COUNT(*) FROM c2910.conhecimento\"") if ch.isdigit())
    tabs = "".join(ch for ch in sudo(c, "-u postgres psql -d sat1_sati_is -tAc \"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='c2910'\"") if ch.isdigit())

    print(f"\nResultado: {'SUCESSO' if ok else 'FALHOU ou incompleto'}")
    print(f"CT-es depois: {depois} (antes: {antes})")
    print(f"Tabelas c2910: {tabs}")
    print(f"HTTP painel: {run(c, 'curl -s -o /dev/null -w \"%{http_code}\" -H \"X-BI-Tenant-Slug: w-carlos\" http://127.0.0.1:8000/').strip()}")

    c.close()


if __name__ == "__main__":
    main()
