"""Copia credenciais SATI do .env global para bi_w_carlos e reenfileira robô."""
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
BI = "/home/oitamar/dashboard-financeiro-web"

REMOTE = r'''
import os, sys
BI = "/home/oitamar/dashboard-financeiro-web"
os.chdir(BI)
sys.path.insert(0, BI)
os.environ["BI_TENANTS_ROOT"] = "/opt/biweb/tenants"

def load_env_file(path):
    out = {}
    if not os.path.isfile(path):
        return out
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out

global_env = load_env_file(".env")
tenant_env = load_env_file("/opt/biweb/tenants/w-carlos/tenant.env")

url = tenant_env.get("SATI_URL") or global_env.get("URL_LOGIN", "")
if not url:
    url = "https://sat3.intersite.com.br/c2910"
usuario = global_env.get("USUARIO_ROBO", "").strip()
senha = global_env.get("SENHA_ROBO", "").strip()

from infra.tenant_licensing.bi_tenant_runtime import prepare_robot_context
from app.data from app.data import data_manager as dm

prepare_robot_context(tenant_slug="w-carlos", apartamento_id=1)

rows = {
    "URL_LOGIN": url,
    "USUARIO_ROBO": usuario,
    "SENHA_ROBO": senha,
    "USE_SATI_SOURCE": "true",
}
if usuario and senha and url:
    dm.salvar_configuracoes_robo(1, rows)
    print("CREDS_OK", "url=" + url, "user=" + usuario[:3] + "***")
else:
    print("CREDS_MISSING", "url=" + bool(url), "user=" + bool(usuario), "pass=" + bool(senha))
    raise SystemExit(2)

from redis import Redis
from rq import Queue
from app.core import logic

q = Queue("default", connection=Redis.from_url("redis://localhost:6379"))
job = q.enqueue(logic.executar_atualizacao_bd_sati, 1, "w-carlos", job_timeout=7200)
print("JOB_ID=" + job.id)
'''


def run(c, cmd, t=90):
    _, o, e = c.exec_command(cmd, timeout=t)
    o.channel.settimeout(t)
    return (o.read() + e.read()).decode("utf-8", errors="replace")


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)

    path = f"{BI}/scripts/_fix_creds_enqueue_w_carlos.py"
    sftp = c.open_sftp()
    with sftp.open(path, "w") as f:
        f.write(REMOTE)
    sftp.close()

    print(run(c, f"cd {BI} && ./venv/bin/python scripts/_fix_creds_enqueue_w_carlos.py", t=45))

    print("\n=== Logs (poll) ===")
    for _ in range(40):
        time.sleep(15)
        logs = run(
            c,
            f"cd {BI} && ./venv/bin/python scripts/_tail_logs_w_carlos.py 2>/dev/null | tail -8",
            t=30,
        )
        for line in logs.splitlines():
            if line.strip():
                print(line)
        if any(
            x in logs
            for x in (
                "Restore concluído",
                "ERRO CRÍTICO",
                "Fechando o navegador",
            )
        ):
            break
    c.close()


if __name__ == "__main__":
    main()
