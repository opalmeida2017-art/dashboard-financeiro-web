"""Lê logs do robô BIWEB no servidor Debian."""
import paramiko

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
APP = "/home/oitamar/dashboard-financeiro-web"


def run(c, cmd, timeout=120):
    _, o, e = c.exec_command(cmd, timeout=timeout)
    return (o.read() + e.read()).decode(errors="replace")


c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=20)

cmds = [
    f"cd {APP} && ls -la downloads/*/ 2>/dev/null | head -20",
    f"cd {APP} && find downloads -name '*.log' -o -name '*lock*' 2>/dev/null | head -30",
    f"cd {APP} && ./venv/bin/python -c \"from app.data from app.data import database as db; from sqlalchemy import text; "
    "rows=db.engine.connect().execute(text('SELECT id, timestamp, mensagem FROM logs_robo "
    "ORDER BY id DESC LIMIT 80')).fetchall(); "
    "[print(r[0], r[1], r[2][:200]) for r in rows]\" 2>&1",
    "tail -80 /home/oitamar/cloudflared-tunnel.log 2>/dev/null || true",
    f"pgrep -af gunicorn | head -3",
    f"ls -la {APP}/downloads/*/painel_documentos_robo.lock 2>/dev/null || true",
    f"ls -la {APP}/downloads/*/idle_robo.lock 2>/dev/null || true",
]

for cmd in cmds:
    print("=" * 60)
    print(cmd[:120])
    print(run(c, cmd))

c.close()
