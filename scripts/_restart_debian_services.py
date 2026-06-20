"""Reinicia gunicorn + rq worker no Debian."""
import paramiko

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
APP = "/home/oitamar/dashboard-financeiro-web"


def run(c, cmd, timeout=60):
    _, o, e = c.exec_command(cmd, timeout=timeout)
    try:
        return (o.read() + e.read()).decode(errors="replace")
    except Exception:
        return "(timeout parcial — comando em background)"


c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=20)

print(run(c, "pkill -f 'rq worker default' || true"))
print(run(c, f"rm -f {APP}/downloads/1/painel_documentos_robo.lock"))
print(run(c, f"cd {APP} && nohup ./venv/bin/rq worker default -u redis://localhost:6379 </dev/null >/dev/null 2>&1 &", timeout=15))
print(run(c, "sleep 2; pgrep -af 'rq worker' || echo 'rq nao encontrado'"))
print(run(c, "pkill -f 'gunicorn.*127.0.0.1:8000.*app:app' || true"))
print(run(c, (
    f"cd {APP} && ./venv/bin/gunicorn --workers 3 --worker-class gevent "
    "--bind 127.0.0.1:8000 --timeout 120 --log-level info "
    "--daemon --pid /tmp/gunicorn-dashboard.pid app:app"
), timeout=30))
print(run(c, "sleep 2; pgrep -af 'gunicorn.*8000' || echo 'gunicorn nao encontrado'"))
c.close()
