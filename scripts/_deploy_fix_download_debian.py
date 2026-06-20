"""Deploy correção download SATI + tenant no worker."""
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
BI = "/home/oitamar/dashboard-financeiro-web"
LOCAL = r"c:\python\BIWEB"


def run(c, cmd, t=120):
    _, o, e = c.exec_command(cmd, timeout=t)
    o.channel.settimeout(t)
    return (o.read() + e.read()).decode("utf-8", errors="replace")


def sudo(c, cmd, t=120):
    i, o, _ = c.exec_command(f"sudo -S {cmd}", get_pty=True)
    i.write(PASS + "\n")
    i.flush()
    o.channel.settimeout(t)
    return o.read().decode("utf-8", errors="replace")


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)

    sftp = c.open_sftp()
    files = [
        "app.py",
        "bi_tenant_runtime.py",
        "logic.py",
        "sati_db_restore.py",
        "database.py",
        "db_connection.py",
        "robos/base_robo.py",
        "robos/coletor_atualizacao_bd.py",
        "blueprints/main.py",
        "blueprints/api.py",
        "templates/configuracao.html",
    ]
    for f in files:
        dst = f"{BI}/{f}"
        print(f"Upload {dst}")
        sftp.put(f"{LOCAL}\\{f.replace('/', chr(92))}", dst)
    sftp.close()

    print("\n=== Reiniciar gunicorn + rq worker ===")
    print(run(c, "pkill -HUP -f 'gunicorn.*8000' || true"))
    print(run(c, "pkill -f 'rq worker default' || true"))
    time.sleep(2)
    print(
        run(
            c,
            f"cd {BI} && nohup ./venv/bin/rq worker default -u redis://localhost:6379 "
            f">> rq_worker.log 2>&1 & sleep 1; pgrep -af 'rq worker'",
        )
    )

    print("\n=== Pasta downloads w-carlos ===")
    print(run(c, "ls -la /opt/biweb/tenants/w-carlos/downloads/1/ 2>&1 | head -10"))

    c.close()
    print("Deploy download fix concluído.")


if __name__ == "__main__":
    main()
