"""Lê logs do robô BIWEB no Debian (tb_logs_robo + estado)."""
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
    f"pgrep -af 'dashboard-financeiro|biweb|8000' || true",
    f"cat {APP}/downloads/1/idle_robo_estado.json 2>/dev/null",
    f"cat {APP}/downloads/1/comprovantes_coleta_lock.json 2>/dev/null",
    f"cat {APP}/downloads/1/painel_documentos_robo.lock 2>/dev/null",
    f"ps -p $(cat {APP}/downloads/1/painel_documentos_robo.lock 2>/dev/null) -o pid,cmd 2>/dev/null || echo 'PID lock morto ou invalido'",
    f"cd {APP} && ./venv/bin/python -c \""
    "from app.data from app.data import database as db; from sqlalchemy import text; "
    "with db.engine.connect() as conn: "
    " rows=conn.execute(text('SELECT id, timestamp, mensagem FROM tb_logs_robo "
    "WHERE apartamento_id=1 ORDER BY id DESC LIMIT 60')).fetchall(); "
    "[print('---', r[0], r[1]); print(r[2]) for r in rows]\" 2>&1",
    f"journalctl -u gunicorn-biweb --no-pager -n 80 2>/dev/null || "
    f"journalctl --user -u biweb --no-pager -n 80 2>/dev/null || "
    f"ls -la /etc/systemd/system/*biweb* /etc/systemd/system/*dashboard* 2>/dev/null",
    f"tail -100 {APP}/gunicorn.log 2>/dev/null || tail -100 /var/log/gunicorn*.log 2>/dev/null || true",
]

for cmd in cmds:
    print("=" * 70)
    print(cmd[:150])
    out = run(c, cmd)
    print(out[:12000] if len(out) > 12000 else out)

c.close()
