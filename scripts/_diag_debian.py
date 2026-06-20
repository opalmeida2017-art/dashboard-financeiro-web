"""Diagnóstico rápido do gunicorn e app no Debian."""
from __future__ import annotations

import paramiko

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
BI = "/home/oitamar/dashboard-financeiro-web"


def run(c, cmd, t=60):
    _, o, e = c.exec_command(cmd, timeout=t)
    o.channel.settimeout(t)
    return (o.read() + e.read()).decode("utf-8", errors="replace")


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)

    cmds = [
        "pgrep -af 'gunicorn.*127.0.0.1:8000' | head -5 || true",
        f"tail -15 {BI}/gunicorn_error.log 2>/dev/null || echo sem_gunicorn_error",
        f"cd {BI} && ./venv/bin/python -c 'from wsgi import application; print(\"wsgi_ok\", type(application).__name__)'",
        "crontab -l 2>/dev/null | grep -i gunicorn || true",
        "systemctl list-units --type=service 2>/dev/null | grep -iE 'gunicorn|dashboard|biweb' || true",
    ]
    for cmd in cmds:
        print(f"\n$ {cmd[:80]}...")
        print(run(c, cmd, t=90).strip())

    c.close()


if __name__ == "__main__":
    main()
