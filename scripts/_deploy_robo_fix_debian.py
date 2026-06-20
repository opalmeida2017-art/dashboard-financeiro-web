"""Envia correções do robô para o Debian e reinicia serviços."""
import paramiko
import time

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
APP = "/home/oitamar/dashboard-financeiro-web"
LOCAL = r"c:\python\BIWEB"

ARQUIVOS = [
    "robos/base_robo.py",
    "robos/coletor_painel_documentos.py",
    "robos/coletor_atualizacao_bd.py",
    "sati_db_restore.py",
    "fluxo_monitor.py",
]


def run(c, cmd, timeout=120):
    _, o, e = c.exec_command(cmd, timeout=timeout)
    return (o.read() + e.read()).decode(errors="replace")


c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=20)

sftp = c.open_sftp()
for rel in ARQUIVOS:
    local = f"{LOCAL}/{rel.replace('/', chr(92))}"
    remote = f"{APP}/{rel}"
    print(f"Upload: {rel}")
    sftp.put(local, remote)
sftp.close()

print("=== reiniciar RQ worker ===")
print(run(c, "pkill -f 'rq worker default' || true; sleep 2"))
print(run(c, f"cd {APP} && nohup ./venv/bin/rq worker default -u redis://localhost:6379 >> rq_worker.log 2>&1 & sleep 1; pgrep -af 'rq worker'"))

print("=== reiniciar gunicorn ===")
cmd_g = (
    f"cd {APP} && pkill -f 'gunicorn.*127.0.0.1:8000.*app:app' || true; sleep 2; "
    "./venv/bin/gunicorn --workers 3 --worker-class gevent --bind 127.0.0.1:8000 "
    "--timeout 120 --log-level info --daemon --pid /tmp/gunicorn-dashboard.pid app:app; "
    "sleep 2; pgrep -af 'gunicorn.*8000'"
)
print(run(c, cmd_g, timeout=60))

print("=== limpar lock antigo (formato PID simples) ===")
print(run(c, f"rm -f {APP}/downloads/1/painel_documentos_robo.lock"))

c.close()
print("Deploy robô concluído.")
