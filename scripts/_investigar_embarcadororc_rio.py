"""Tabelas embarcador* no schema c3219 (rio-bonito)."""
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

env = parse_env(Path("/opt/biweb/tenants/rio-bonito/tenant.env"))
schema = env.get("SATI_SCHEMA", "c3219")
eng = create_engine(env.get("SATI_DATABASE_URL"))
with eng.connect() as conn:
    for tbl in ("embarcador", "embarcadororc", "embarcadorcont"):
        try:
            n = conn.execute(text("SELECT COUNT(*) FROM " + schema + "." + tbl)).scalar()
            print(tbl, "count", n)
            cols = conn.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema=:s AND table_name=:t ORDER BY ordinal_position LIMIT 8"
            ), {"s": schema, "t": tbl}).fetchall()
            print("  cols", [c[0] for c in cols])
            if n and n <= 30:
                rows = conn.execute(text("SELECT * FROM " + schema + "." + tbl + " LIMIT 30")).fetchall()
                for r in rows:
                    print(" ", r)
        except Exception as e:
            print(tbl, "ERR", e)
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
