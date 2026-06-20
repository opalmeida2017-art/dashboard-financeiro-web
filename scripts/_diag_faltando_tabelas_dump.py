"""Compara tabelas do dump vs bi_wcarlos."""
import paramiko

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
DB = "bi_wcarlos"

REMOTE = r'''
import os, subprocess, tempfile, zipfile
from pathlib import Path

DB = "bi_wcarlos"
candidates = [
    "/home/oitamar/dashboard-financeiro-web/downloads/1/SATI-c2910-atual.zip",
    "/home/oitamar/dashboard-financeiro-web/downloads/11/SATI-c2910-atual.zip",
]
zip_path = next((p for p in candidates if os.path.isfile(p)), None)
if not zip_path:
    print("SEM_ZIP")
    raise SystemExit(0)
print("ZIP:", zip_path)

tmpdir = tempfile.mkdtemp()
with zipfile.ZipFile(zip_path) as zf:
    zf.extractall(tmpdir)
dump = next(Path(tmpdir).rglob("*.dump"), None)
if not dump:
    print("SEM_DUMP")
    raise SystemExit(1)
print("DUMP:", dump)

pg_restore = "/usr/lib/postgresql/17/bin/pg_restore"
lst = subprocess.run([pg_restore, "-l", str(dump)], capture_output=True, text=True)
tables_dump = sorted({
    ln.split("TABLE c2910 ")[-1].strip()
    for ln in lst.stdout.splitlines()
    if "TABLE c2910 " in ln and "TABLE DATA" not in ln
})
with open("/tmp/tables_dump.txt", "w") as f:
    f.write("\n".join(tables_dump))

db = subprocess.run(
    ["sudo", "-u", "postgres", "psql", "-d", DB, "-tAc",
     "SELECT tablename FROM pg_tables WHERE schemaname='c2910' ORDER BY 1"],
    capture_output=True, text=True,
)
tables_db = set(x.strip() for x in db.stdout.splitlines() if x.strip())
faltando = [t for t in tables_dump if t not in tables_db]
print("\n=== TABELAS NO DUMP MAS NAO NO BANCO (%d) ===" % len(faltando))
for t in faltando:
    print(t)

sql = subprocess.run([pg_restore, "-f", "-", str(dump)], capture_output=True, text=True)
out = sql.stdout
idx = out.find("CREATE TABLE c2910.cliente")
if idx >= 0:
    print("\n=== CREATE TABLE c2910.cliente (inicio) ===")
    print(out[idx:idx+2500])
else:
    print("\nCREATE TABLE cliente nao encontrado no SQL do dump")

# tenta criar cliente manualmente para ver erro
if faltando and "cliente" in faltando:
    frag = out[idx:idx+8000] if idx >= 0 else ""
    end = frag.find(");")
    if end > 0:
        create_stmt = frag[: end + 2]
        test = subprocess.run(
            ["sudo", "-u", "postgres", "psql", "-d", DB, "-v", "ON_ERROR_STOP=1", "-c", create_stmt],
            capture_output=True, text=True,
        )
        print("\n=== TESTE CREATE cliente (erro real) ===")
        print(test.stderr or test.stdout or "ok")
'''

def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)
    sftp = c.open_sftp()
    with sftp.open("/tmp/diag_dump_tables.py", "w") as f:
        f.write(REMOTE)
    sftp.close()
    _, o, e = c.exec_command("python3 /tmp/diag_dump_tables.py", timeout=180)
    print((o.read() + e.read()).decode("utf-8", "replace"))
    c.close()


if __name__ == "__main__":
    main()
