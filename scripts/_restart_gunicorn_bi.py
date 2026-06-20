"""Reinicia gunicorn BI no Debian."""
import paramiko
import time

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
BI = "/home/oitamar/dashboard-financeiro-web"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=25)

def run(cmd, t=60):
    _, o, e = c.exec_command(cmd, timeout=t)
    o.channel.settimeout(t)
    return (o.read() + e.read()).decode("utf-8", "replace")

print(run(
    f"cd {BI} && pkill -f 'gunicorn.*127.0.0.1:8000' || true; sleep 2; "
    "./venv/bin/gunicorn --workers 3 --worker-class gevent --bind 127.0.0.1:8000 "
    "--timeout 120 --log-level info --daemon --pid /tmp/gunicorn-dashboard.pid app:app; "
    "sleep 3; pgrep -af '127.0.0.1:8000' | head -3"
))
print(run("grep -n _df_cache_key data_manager.py | head -2", t=15) if False else "")
print(run(f"grep -n BIWEB_TENANT_SLUG {BI}/templates/layout.html | head -2"))
print(run("curl -sI --max-time 8 -k https://dadosfrete.duckdns.org:8443/biweb/rio-bonito/ | head -3"))
c.close()
