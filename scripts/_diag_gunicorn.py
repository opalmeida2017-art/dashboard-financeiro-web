"""Diagnóstico gunicorn + tenant no Debian."""
import paramiko

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
BI = "/home/oitamar/dashboard-financeiro-web"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=25)

def run(cmd, t=90):
    _, o, e = c.exec_command(cmd, timeout=t)
    o.channel.settimeout(t)
    out = (o.read() + e.read()).decode("utf-8", "replace")
    print(f"$ {cmd[:120]}")
    print(out[:4000] if out else "(vazio)")
    print("---")
    return out

run("pgrep -af gunicorn || echo 'sem gunicorn'")
run(f"test -f /tmp/gunicorn-dashboard.pid && cat /tmp/gunicorn-dashboard.pid || echo 'sem pid'")
run(f"cd {BI} && tail -30 nohup.out 2>/dev/null || tail -30 /var/log/gunicorn*.log 2>/dev/null || echo 'sem log'")
run(f"cd {BI} && ./venv/bin/python -c \"import app; print('app ok')\" 2>&1")
run("curl -sI --max-time 8 -k http://127.0.0.1:8000/ 2>&1 | head -5")
run("curl -sI --max-time 8 -k https://dadosfrete.duckdns.org:8443/biweb/rio-bonito/ 2>&1 | head -5")
c.close()
