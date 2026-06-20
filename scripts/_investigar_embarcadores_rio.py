"""Investiga embarcadores rio-bonito no Debian (várias fontes)."""
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
schema = env.get("SATI_SCHEMA", "c3219")
url = env.get("SATI_DATABASE_URL") or env.get("DATABASE_URL")
eng = create_engine(url)
with eng.connect() as conn:
    print("schema", schema)
    for q, label in [
        ("SELECT COUNT(*) FROM " + schema + ".embarcador", "embarcador rows"),
        ("SELECT COUNT(*) FROM " + schema + ".conhecimento WHERE codembarcador IS NOT NULL AND codembarcador > 0", "conh com codembarcador"),
        ("SELECT COUNT(DISTINCT codembarcador) FROM " + schema + ".conhecimento WHERE codembarcador IS NOT NULL AND codembarcador > 0", "cod distintos conh"),
        ("SELECT codembarcador, COUNT(*) c FROM " + schema + ".conhecimento WHERE codembarcador IS NOT NULL GROUP BY 1 ORDER BY c DESC LIMIT 15", "top codembarcador"),
    ]:
        try:
            r = conn.execute(text(q)).fetchall()
            print(label, r)
        except Exception as e:
            print(label, "ERR", e)
    try:
        r = conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema=:s AND table_name ILIKE '%embarc%'"
        ), {"s": schema}).fetchall()
        print("tabelas %embarc%", [x[0] for x in r])
    except Exception as e:
        print("tables err", e)
    try:
        r = conn.execute(text(
            "SELECT codtipocliente, COUNT(*) FROM " + schema + ".cliente GROUP BY 1 ORDER BY 2 DESC LIMIT 10"
        )).fetchall()
        print("cliente tipos", r)
    except Exception as e:
        print("cliente err", e)
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
