import paramiko

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
BI = "/home/oitamar/dashboard-financeiro-web"
LOCAL = r"c:\python\BIWEB"
FILES = ["blueprints/helpers.py", "config.py"]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=25)
sftp = c.open_sftp()
for rel in FILES:
    sftp.put(f"{LOCAL}\\{rel.replace('/', chr(92))}", f"{BI}/{rel}")
    print("uploaded", rel)
sftp.close()

def run(cmd, t=60):
    _, o, e = c.exec_command(cmd, timeout=t)
    return (o.read() + e.read()).decode("utf-8", errors="replace")

print(run("pkill -f 'gunicorn.*127.0.0.1:8000.*app:app' || true"))
print(run(
    f"cd {BI} && ./venv/bin/gunicorn --workers 3 --worker-class gevent --bind 127.0.0.1:8000 "
    "--timeout 120 --daemon --pid /tmp/gunicorn-dashboard.pid app:app; sleep 2; pgrep -af 'gunicorn.*8000' | head -3"
))
print(run("curl -sI --max-time 15 -k https://dadosfrete.duckdns.org:8443/biweb/wcarlos/ | head -3"))
c.close()
