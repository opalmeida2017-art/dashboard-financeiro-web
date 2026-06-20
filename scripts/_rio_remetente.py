"""Distinct codremetente/codembarcador rio-bonito."""
import base64, paramiko
HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
py = b"""from pathlib import Path
from sqlalchemy import create_engine, text
env = {}
for p in [Path("/opt/biweb/tenants/rio-bonito/tenant.env")]:
    for line in p.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k,v=line.split("=",1); env[k.strip()]=v.strip().strip('"')
schema=env.get("SATI_SCHEMA","c3219")
eng=create_engine(env["SATI_DATABASE_URL"])
with eng.connect() as c:
    q="SELECT COUNT(DISTINCT codremetente) FROM "+schema+".conhecimento WHERE codremetente IS NOT NULL AND codremetente>0"
    print("distinct remetente", c.execute(text(q)).scalar())
    q2="SELECT c.codremetente, cl.nome, COUNT(*) FROM "+schema+".conhecimento c JOIN "+schema+".cliente cl ON cl.codcliente=c.codremetente WHERE c.codremetente IS NOT NULL GROUP BY 1,2 ORDER BY 3 DESC LIMIT 15"
    for r in c.execute(text(q2)):
        print(r)
"""
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy()); c.connect(HOST,username=USER,password=PASS,timeout=25)
b64=base64.b64encode(py).decode()
_,o,e=c.exec_command(f"cd /home/oitamar/dashboard-financeiro-web && echo {b64}|base64 -d|./venv/bin/python",timeout=90)
o.channel.settimeout(90); print((o.read()+e.read()).decode()); c.close()
