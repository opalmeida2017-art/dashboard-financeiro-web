"""Lista embarcadores no schema do tenant rio-bonito no Debian."""
import base64
import paramiko

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"

py = b"""from pathlib import Path
from sqlalchemy import create_engine, text

def parse_env(p):
    out = {}
    if not p.is_file():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out

base = Path("/opt/biweb/tenants/rio-bonito")
env = parse_env(base / "tenant.env")
env.update(parse_env(base / ".env"))
url = env.get("SATI_DATABASE_URL") or env.get("DATABASE_URL")
schema = env.get("SATI_SCHEMA", "?")
print("schema", schema)
print("db", (url or "").split("/")[-1])
eng = create_engine(url)
with eng.connect() as conn:
    q1 = "SELECT codembarcador, nome FROM " + schema + ".embarcador WHERE codembarcador IS NOT NULL AND codembarcador > 0 ORDER BY nome"
    rows = conn.execute(text(q1)).fetchall()
    print("total cadastro", len(rows))
    for r in rows:
        print(r[0], "-", r[1])
    q2 = "SELECT DISTINCT c.codembarcador, emb.nome FROM " + schema + ".conhecimento c LEFT JOIN " + schema + ".embarcador emb ON emb.codembarcador = c.codembarcador WHERE c.codembarcador IS NOT NULL AND c.codembarcador > 0 ORDER BY 1"
    conh = conn.execute(text(q2)).fetchall()
    print("distintos conhecimento", len(conh))
    for r in conh:
        print(" c", r[0], "-", r[1])
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=25)
b64 = base64.b64encode(py).decode("ascii")
_, o, e = c.exec_command(
    f"cd /home/oitamar/dashboard-financeiro-web && echo {b64} | base64 -d | ./venv/bin/python",
    timeout=90,
)
o.channel.settimeout(90)
print((o.read() + e.read()).decode("utf-8", errors="replace"))
c.close()
