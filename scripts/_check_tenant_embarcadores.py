"""Verifica schema SATI usado por cada tenant no Debian."""
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

for slug in ("wcarlos", "rio-bonito"):
    base = Path("/opt/biweb/tenants") / slug
    env = parse_env(base / "tenant.env")
    env.update(parse_env(base / ".env"))
    db = env.get("DATABASE_URL", "")
    sati = env.get("SATI_DATABASE_URL", "")
    schema_env = env.get("SATI_SCHEMA", "")
    apt = env.get("BIWEB_TRANSPORTADORA_ID", "?")
    print("===", slug, "apt", apt, "schema_env", schema_env)
    eng = create_engine(db)
    with eng.connect() as conn:
        rows = conn.execute(text(
            "SELECT chave, valor FROM configuracoes_robo WHERE chave IN "
            "('URL_LOGIN','SATI_URL_CODIGO','SATI_PG_SCHEMA','USE_SATI_SOURCE') ORDER BY 1"
        )).fetchall()
        for r in rows:
            print(" ", r[0], "=", r[1])
    if sati and schema_env:
        seng = create_engine(sati)
        with seng.connect() as conn:
            n = conn.execute(text(
                "SELECT COUNT(*) FROM " + schema_env + ".embarcador"
            )).scalar()
            print("  embarcadores em", schema_env, ":", n)
            rows = conn.execute(text(
                "SELECT codembarcador, nome FROM " + schema_env + ".embarcador ORDER BY nome LIMIT 20"
            )).fetchall()
            for r in rows:
                print("   ", r[0], "-", r[1])
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
