"""Logs BD SATI + erros no Debian."""
import paramiko

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
APP = "/home/oitamar/dashboard-financeiro-web"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=20)

script = r'''
from app.data from app.data import database as db
from sqlalchemy import text
with db.engine.connect() as conn:
    rows = conn.execute(text(
        "SELECT id, timestamp, mensagem FROM tb_logs_robo "
        "WHERE apartamento_id=1 AND (mensagem ILIKE '%ERRO%' OR mensagem ILIKE '%SATI%' "
        "OR mensagem ILIKE '%INICIANDO%' OR mensagem ILIKE '%CONCLU%') "
        "ORDER BY id DESC LIMIT 50"
    )).fetchall()
for r in rows:
    print("---", r[0], r[1])
    print(r[2])
    print()
'''

sftp = c.open_sftp()
with sftp.open(f"{APP}/_tmp_logs2.py", "w") as f:
    f.write(script)
sftp.close()

_, o, e = c.exec_command(f"cd {APP} && ./venv/bin/python _tmp_logs2.py 2>&1", timeout=60)
print((o.read() + e.read()).decode(errors="replace"))

# .env SATI vars (masked)
_, o, e = c.exec_command(
    f"grep -E 'SATI_|ROBO_|EXECUTION|REDIS|HEADLESS' {APP}/.env 2>/dev/null | "
    "sed 's/=.*/=***/'"
)
print("=== .env (mascarado) ===")
print((o.read() + e.read()).decode(errors="replace"))

c.exec_command(f"rm -f {APP}/_tmp_logs2.py")
c.close()
