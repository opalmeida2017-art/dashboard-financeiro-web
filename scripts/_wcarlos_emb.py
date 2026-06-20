"""Compara cadastro vs conhecimento wcarlos c2910."""
import base64, paramiko
HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
py = b"""from pathlib import Path
from sqlalchemy import create_engine, text
env={}
for line in Path("/opt/biweb/tenants/wcarlos/tenant.env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k,v=line.split("=",1); env[k.strip()]=v.strip().strip('"')
eng=create_engine(env["SATI_DATABASE_URL"])
s="c2910"
with eng.connect() as c:
    print("cadastro:")
    for r in c.execute(text("SELECT codembarcador,nome FROM "+s+".embarcador ORDER BY 1")):
        print(" ",r)
    print("distintos conhecimento:")
    for r in c.execute(text("SELECT DISTINCT c.codembarcador,emb.nome FROM "+s+".conhecimento c LEFT JOIN "+s+".embarcador emb ON emb.codembarcador=c.codembarcador WHERE c.codembarcador>0 ORDER BY 1")):
        print(" ",r)
"""
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy()); c.connect(HOST,username=USER,password=PASS,timeout=25)
b64=base64.b64encode(py).decode()
_,o,e=c.exec_command(f"cd /home/oitamar/dashboard-financeiro-web && echo {b64}|base64 -d|./venv/bin/python",timeout=90)
o.channel.settimeout(90); print((o.read()+e.read()).decode()); c.close()
