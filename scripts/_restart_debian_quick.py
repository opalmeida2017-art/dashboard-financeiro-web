"""Reinicia gunicorn/rq no Debian e mostra tenant.env w-carlos."""
import paramiko

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)

    def run(cmd, t=30):
        _, o, e = c.exec_command(cmd, timeout=t)
        o.channel.settimeout(t)
        return (o.read() + e.read()).decode("utf-8", errors="replace")

    run("pkill -HUP -f 'gunicorn.*8000' 2>/dev/null || true")
    run(
        "pkill -f 'rq worker default' 2>/dev/null; sleep 1; "
        "cd /home/oitamar/dashboard-financeiro-web && "
        "nohup ./venv/bin/rq worker default -u redis://localhost:6379 "
        ">> rq_worker.log 2>&1 &",
        t=15,
    )

    print("=== processos ===")
    print(run("pgrep -af gunicorn || echo sem_gunicorn"))
    print(run("pgrep -af 'rq worker' || echo sem_rq"))
    print(run("systemctl is-active gunicorn biweb-rq 2>/dev/null || true"))

    print("=== tenant.env w-carlos (mascarado) ===")
    print(run("cat /opt/biweb/tenants/w-carlos/tenant.env 2>&1 | head -20"))

    c.close()


if __name__ == "__main__":
    main()
