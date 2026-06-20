import paramiko
import time

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
BI = "/home/oitamar/dashboard-financeiro-web"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=25)


def run(cmd, t=90):
    _, o, e = c.exec_command(cmd, timeout=t)
    try:
        return (o.read() + e.read()).decode("utf-8", errors="replace")
    except Exception as ex:
        return f"timeout/partial: {ex}"


print("=== gunicorn ===")
print(
    run(
        f"cd {BI} && pkill -f 'gunicorn.*127.0.0.1:8000.*app:app' || true; sleep 2; "
        "./venv/bin/gunicorn --workers 3 --worker-class gevent --bind 127.0.0.1:8000 "
        "--timeout 120 --log-level info --daemon --pid /tmp/gunicorn-dashboard.pid app:app; "
        "sleep 2; pgrep -af gunicorn | head -5"
    )
)

print("\n=== import app ===")
print(run(f"cd {BI} && ./venv/bin/python -c \"from app.data import data_manager; import bi_audit; print('ok', hasattr(data_manager,'_total_investimento_estoque'))\"", t=60))

print("\n=== HTTP tenants ===")
for url in [
    "https://dadosfrete.duckdns.org:8443/biweb/wcarlos/",
    "https://dadosfrete.duckdns.org:8443/biweb/rio-bonito/",
]:
    print(url, "->", run(f"curl -sI --max-time 15 -k {url} 2>&1 | head -2").strip())

c.close()
