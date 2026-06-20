"""Corrige nome 'Teste' no Debian: BD + arquivos + gunicorn."""
from pathlib import Path

import paramiko

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
APP = "/home/oitamar/dashboard-financeiro-web"
ROOT = Path(__file__).resolve().parents[1]
NOVO_NOME = "TRANSPORTES BRASIL LTDA"


def run(c, cmd, timeout=90):
    _, o, e = c.exec_command(cmd, timeout=timeout)
    return (o.read() + e.read()).decode(errors="replace")


c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=20)

sftp = c.open_sftp()
for rel in ("tenant.py", "app.py"):
    sftp.put(str(ROOT / rel), f"{APP}/{rel}")
sftp.close()
print("Arquivos tenant.py e app.py atualizados.")

py = (
    "from app.data from app.data import database as db\n"
    "from sqlalchemy import text\n"
    f"nome = {NOVO_NOME!r}\n"
    "with db.engine.begin() as conn:\n"
    "    r = conn.execute(text(\n"
    "        \"UPDATE apartamentos SET nome_empresa = :n \"\n"
    "        \"WHERE LOWER(TRIM(nome_empresa)) = 'teste'\"\n"
    "    ), {'n': nome})\n"
    "    print('linhas:', r.rowcount)\n"
    "    row = conn.execute(text('SELECT id, nome_empresa FROM apartamentos LIMIT 1')).first()\n"
    "    print('apartamento:', row)\n"
)
sftp = c.open_sftp()
with sftp.file("/home/oitamar/_fix_nome.py", "w") as f:
    f.write(py)
sftp.close()
print(run(c, f"cd {APP} && ./venv/bin/python /home/oitamar/_fix_nome.py 2>&1 || "
              f"cd {APP} && PYTHONPATH={APP} ./venv/bin/python /home/oitamar/_fix_nome.py"))

print(
    run(
        c,
        f"cd {APP} && pkill -f 'gunicorn.*127.0.0.1:8000.*app:app' || true; sleep 2; "
        "./venv/bin/gunicorn --workers 3 --worker-class gevent --bind 127.0.0.1:8000 "
        "--timeout 120 --daemon --pid /tmp/gunicorn-dashboard.pid app:app; sleep 2",
    )
)
print("navbar:", run(c, "curl -s http://127.0.0.1:8000/ | grep navbar-brand"))
c.close()
