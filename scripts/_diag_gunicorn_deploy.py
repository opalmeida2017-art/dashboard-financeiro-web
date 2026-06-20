import paramiko

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
BI = "/home/oitamar/dashboard-financeiro-web"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=25)


def run(cmd, t=120):
    _, o, e = c.exec_command(cmd, timeout=t)
    return (o.read() + e.read()).decode("utf-8", errors="replace")

print(run(f"pgrep -af gunicorn || echo 'sem gunicorn'"))
print("--- gunicorn test ---")
print(run(f"cd {BI} && ./venv/bin/python -c 'import app' 2>&1", t=90))
print("--- start foreground error ---")
print(
    run(
        f"cd {BI} && timeout 8 ./venv/bin/gunicorn --workers 1 --bind 127.0.0.1:8000 app:app 2>&1 || true",
        t=30,
    )
)
print("--- tail log ---")
print(run(f"tail -40 {BI}/rq_worker.log 2>/dev/null; ls -la {BI}/*.log 2>/dev/null | tail -5"))

c.close()
