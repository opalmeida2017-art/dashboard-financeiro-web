import paramiko

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
BI = "/home/oitamar/dashboard-financeiro-web"
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=25)

def run(cmd, t=90):
    _, o, e = c.exec_command(cmd, timeout=t)
    return (o.read() + e.read()).decode("utf-8", errors="replace")

print(run(f"curl -s --max-time 20 -k https://dadosfrete.duckdns.org:8443/biweb/wcarlos/ 2>&1 | head -30"))
print("--- journal ---")
print(run(f"journalctl -u gunicorn-dashboard -n 30 --no-pager 2>/dev/null || true"))
print("--- test wsgi ---")
print(
    run(
        f"cd {BI} && ./venv/bin/python - <<'PY'\n"
        "from app import app\n"
        "c = app.test_client()\n"
        "with app.app_context():\n"
        "    r = c.get('/biweb/wcarlos/', follow_redirects=False)\n"
        "    print('status', r.status_code)\n"
        "    print(r.data[:500])\n"
        "PY",
        t=120,
    )
)

c.close()
