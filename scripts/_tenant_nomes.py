"""Nomes empresa em cada banco tenant."""
import paramiko

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=25)

def run(cmd, t=30):
    _, o, e = c.exec_command(cmd, timeout=t)
    o.channel.settimeout(t)
    return (o.read() + e.read()).decode("utf-8", "replace").strip()

for db in ("bi_rio_bonito", "bi_wcarlos"):
    q = f"sudo -u postgres psql -d {db} -tAc \"SELECT id, nome_empresa, slug FROM apartamentos LIMIT 3\""
    print(f"\n{db}:")
    print(run(q))

c.close()
