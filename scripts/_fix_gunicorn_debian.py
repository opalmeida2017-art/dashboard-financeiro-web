import paramiko
import time

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
APP = "/home/oitamar/dashboard-financeiro-web"


def run(c, cmd, timeout=120):
    _, o, e = c.exec_command(cmd, timeout=timeout)
    return (o.read() + e.read()).decode(errors="replace")


c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=20)

print("=== import app ===")
print(run(c, f"cd {APP} && ./venv/bin/python -c 'import app; print(\"ok\")' 2>&1"))

print("=== restart gunicorn ===")
cmd = (
    f"cd {APP} && pkill -f 'gunicorn.*app:app' || true; sleep 2; "
    "./venv/bin/gunicorn --workers 3 --worker-class gevent --bind 127.0.0.1:8000 "
    "--timeout 120 --daemon --pid /tmp/gunicorn-dashboard.pid app:app; sleep 3; "
    "curl -sI http://127.0.0.1:8000/ | head -4"
)
print(run(c, cmd, timeout=60))
print(run(c, "pgrep -af gunicorn | head -5"))
c.close()
