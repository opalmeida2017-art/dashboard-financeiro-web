"""Enfileira atualização SATI w-carlos no Debian e acompanha logs iniciais."""
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
BI = "/home/oitamar/dashboard-financeiro-web"


def run(c, cmd, t=60):
    _, o, e = c.exec_command(cmd, timeout=t)
    o.channel.settimeout(t)
    return (o.read() + e.read()).decode("utf-8", errors="replace")


ENQUEUE_PY = r'''
import os, sys
BI = "/home/oitamar/dashboard-financeiro-web"
os.chdir(BI)
sys.path.insert(0, BI)
os.environ["BI_TENANTS_ROOT"] = "/opt/biweb/tenants"

from redis import Redis
from rq import Queue
from app.core import logic

q = Queue("default", connection=Redis.from_url("redis://localhost:6379"))
job = q.enqueue(
    logic.executar_atualizacao_bd_sati,
    1,
    "w-carlos",
    job_timeout=7200,
)
print("JOB_ID=" + job.id)
print("JOB_STATUS=" + job.get_status())
'''

LOGS_PY = r'''
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
    rows = conn.execute(
        text(
            "SELECT timestamp, mensagem FROM tb_logs_robo "
            "WHERE apartamento_id = 1 ORDER BY id DESC LIMIT 25"
        )
    ).fetchall()
for ts, msg in reversed(rows):
    print(f"{ts}\t{msg}")
'''


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)

    print("=== Verificar RQ worker ===")
    print(run(c, "pgrep -af 'rq worker default' || echo SEM_WORKER"))

    remote_enqueue = f"{BI}/scripts/_enqueue_w_carlos.py"
    remote_logs = f"{BI}/scripts/_tail_logs_w_carlos.py"
    sftp = c.open_sftp()
    with sftp.open(remote_enqueue, "w") as f:
        f.write(ENQUEUE_PY)
    with sftp.open(remote_logs, "w") as f:
        f.write(LOGS_PY)
    sftp.close()

    print("\n=== Enfileirar atualização SATI (w-carlos) ===")
    out = run(
        c,
        f"cd {BI} && ./venv/bin/python scripts/_enqueue_w_carlos.py",
        t=30,
    )
    print(out.strip())

    print("\n=== Acompanhando logs (até 8 min) ===")
    seen = set()
    deadline = time.time() + 480
    done_markers = (
        "Restore concluído",
        "ERRO CRÍTICO",
        "ERRO: tenant BI não identificado",
        "Fechando o navegador",
    )
    while time.time() < deadline:
        time.sleep(12)
        logs = run(c, f"cd {BI} && ./venv/bin/python scripts/_tail_logs_w_carlos.py", t=45)
        for line in logs.splitlines():
            line = line.strip()
            if not line or line in seen:
                continue
            seen.add(line)
            print(line)
            if any(m in line for m in done_markers):
                c.close()
                return
    print("\n(timeout acompanhamento — job pode continuar no servidor)")
    c.close()


if __name__ == "__main__":
    main()
