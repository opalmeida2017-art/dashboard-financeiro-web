"""Testa patch dom_endereco255 + restore parcial bi_wcarlos."""
import paramiko

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
BI = "/home/oitamar/dashboard-financeiro-web"

REMOTE = r'''
import os, sys
os.chdir("/home/oitamar/dashboard-financeiro-web")
sys.path.insert(0, "/home/oitamar/dashboard-financeiro-web")
os.environ["BI_TENANTS_ROOT"] = "/opt/biweb/tenants"

from pathlib import Path
from sati_integration.robos from sati_integration.robos import sati_db_restore as sr

zip_path = Path("/home/oitamar/dashboard-financeiro-web/downloads/1/SATI-c2910-atual.zip")
if not zip_path.is_file():
    print("SEM_ZIP")
    raise SystemExit(1)

from infra.tenant_licensing.bi_tenant_runtime import prepare_robot_context
prepare_robot_context(tenant_slug="w-carlos", apartamento_id=1)
import os
print("DB:", os.getenv("SATI_DATABASE_URL", "").split("/")[-1])

print("Restore bi_wcarlos c2910...")
sr.processar_arquivo_zip_sati(zip_path, apartamento_id=1)
print("RESTORE_OK")
'''

def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)
    sftp = c.open_sftp()
    with sftp.open(f"{BI}/scripts/_test_patch_wcarlos.py", "w") as f:
        f.write(REMOTE)
    sftp.close()
    _, o, e = c.exec_command(
        f"cd {BI} && ./venv/bin/python scripts/_test_patch_wcarlos.py",
        timeout=600,
    )
    o.channel.settimeout(600)
    out = (o.read() + e.read()).decode("utf-8", "replace")
    print(out[-4000:])
    c.close()

if __name__ == "__main__":
    main()
