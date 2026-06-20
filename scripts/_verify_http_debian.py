import paramiko

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=25)

def run(cmd):
    _, o, e = c.exec_command(cmd, timeout=60)
    return (o.read() + e.read()).decode("utf-8", errors="replace")

for url in [
    "http://127.0.0.1:8000/",
    "https://dadosfrete.duckdns.org:8443/biweb/wcarlos/",
    "https://dadosfrete.duckdns.org:8443/biweb/rio-bonito/",
]:
    print(url)
    print(run(f"curl -sI --max-time 15 -k {url} 2>&1 | head -5"))
    print()

c.close()
