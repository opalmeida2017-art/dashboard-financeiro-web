"""Compara nome transportadora nas duas URLs."""
import paramiko

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=25)

def run(cmd, t=45):
    _, o, e = c.exec_command(cmd, timeout=t)
    o.channel.settimeout(t)
    return (o.read() + e.read()).decode("utf-8", "replace")

for slug in ("rio-bonito", "wcarlos"):
    cmd = (
        f"curl -sS --max-time 20 -k "
        f"'https://dadosfrete.duckdns.org:8443/biweb/{slug}/' "
        f"| grep -oP '(?<=<title>)[^<]+' | head -1"
    )
    print(f"{slug}: {run(cmd).strip()}")

# API com header explícito
for slug in ("rio-bonito", "wcarlos"):
    cmd = (
        f"curl -sS --max-time 20 -H 'X-BI-Tenant-Slug: {slug}' "
        f"http://127.0.0.1:8000/api/transportadora-info 2>&1 | head -c 200"
    )
    print(f"api {slug}: {run(cmd).strip()}")

c.close()
