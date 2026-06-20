"""Copia creds SATI apt 11 → bi_w_carlos e dispara robô."""
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

SRC_DB = "dashboard_db"
SRC_APT = 11
DST_APT = 1

import subprocess

def psql_tsv(db, sql):
    r = subprocess.run(
        ["sudo", "-u", "postgres", "psql", "-d", db, "-tAc", sql],
        capture_output=True,
        text=True,
        check=False,
    )
    return r.stdout.strip()

lines = psql_tsv(SRC_DB, f"""
    SELECT chave || E'\\t' || valor
    FROM configuracoes_robo
    WHERE apartamento_id={SRC_APT}
      AND chave IN ('URL_LOGIN','USUARIO_ROBO','SENHA_ROBO')
""").splitlines()
rows = {}
for line in lines:
    if "\t" in line:
        k, v = line.split("\t", 1)
        rows[k.strip()] = v.strip()

if not all(rows.get(k) for k in ("URL_LOGIN", "USUARIO_ROBO", "SENHA_ROBO")):
    print("COPY_FAIL missing keys", sorted(rows.keys()))
    raise SystemExit(2)

rows["USE_SATI_SOURCE"] = "true"
from infra.tenant_licensing.bi_tenant_runtime import prepare_robot_context
from app.data from app.data import data_manager as dm
from redis import Redis
from rq import Queue
from app.core import logic

prepare_robot_context(tenant_slug="w-carlos", apartamento_id=DST_APT)
dm.salvar_configuracoes_robo(DST_APT, rows)
print("COPY_OK user=" + rows["USUARIO_ROBO"][:3] + "*** url=" + rows["URL_LOGIN"])

q = Queue("default", connection=Redis.from_url("redis://localhost:6379"))
job = q.enqueue(logic.executar_atualizacao_bd_sati, DST_APT, "w-carlos", job_timeout=7200)
print("JOB_ID=" + job.id)
'''

TAIL = r'''
import os, sys
BI = "/home/oitamar/dashboard-financeiro-web"
os.chdir(BI)
sys.path.insert(0, BI)
os.environ["BI_TENANTS_ROOT"] = "/opt/biweb/tenants"
from infra.tenant_licensing.bi_tenant_runtime import prepare_robot_context
from sqlalchemy import text
from app.data.db_connection import engine
prepare_robot_context(tenant_slug="w-carlos", apartamento_id=1)
with engine.connect() as conn:
    rows = conn.execute(text(
        "SELECT timestamp, mensagem FROM tb_logs_robo WHERE apartamento_id=1 ORDER BY id DESC LIMIT 15"
    )).fetchall()
for ts, msg in reversed(rows):
    print(f"{ts}\t{msg}")
'''


def run(c, cmd, t=60):
    _, o, e = c.exec_command(cmd, timeout=t)
    o.channel.settimeout(t)
    return (o.read() + e.read()).decode("utf-8", errors="replace")


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)
    sftp = c.open_sftp()
    with sftp.open(f"{BI}/scripts/_copy_creds_run.py", "w") as f:
        f.write(REMOTE)
    with sftp.open(f"{BI}/scripts/_tail_logs_w_carlos.py", "w") as f:
        f.write(TAIL)
    sftp.close()

    print(run(c, f"cd {BI} && ./venv/bin/python scripts/_copy_creds_run.py", t=45))

    print("\n=== Acompanhando (até ~12 min) ===")
    for _ in range(50):
        time.sleep(15)
        logs = run(c, f"cd {BI} && ./venv/bin/python scripts/_tail_logs_w_carlos.py", t=30)
        new = [ln for ln in logs.splitlines() if ln.strip()]
        if new:
            print("\n".join(new[-6:]))
        blob = "\n".join(new)
        if any(
            x in blob
            for x in (
                "Restore concluído",
                "ERRO CRÍTICO",
                "Fechando o navegador.",
            )
        ):
            break
    c.close()


if __name__ == "__main__":
    main()
