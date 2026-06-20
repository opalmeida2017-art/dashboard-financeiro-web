"""Testa CREATE cliente e domínios usados."""
import paramiko

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
DB = "bi_wcarlos"

REMOTE = r'''
import subprocess, tempfile, zipfile
from pathlib import Path

DB = "bi_wcarlos"
zip_path = "/home/oitamar/dashboard-financeiro-web/downloads/1/SATI-c2910-atual.zip"
pg_restore = "/usr/lib/postgresql/17/bin/pg_restore"

tmpdir = tempfile.mkdtemp()
with zipfile.ZipFile(zip_path) as zf:
    zf.extractall(tmpdir)
dump = next(Path(tmpdir).rglob("*.dump"))

sql = subprocess.run([pg_restore, "-f", "-", str(dump)], capture_output=True, text=True).stdout
idx = sql.find("CREATE TABLE c2910.cliente")
end = sql.find(");", idx) + 2
create = sql[idx:end]

doms = [
    "dom_codint", "dom_nomepessoa", "dom_endereco255", "dom_complender",
    "dom_cep", "dom_quantreal", "dom_cgc2", "dom_ie", "dom_fone2",
    "dom_resp", "dom_dinheiro2", "dom_codint2", "dom_nomepessoa2",
    "dom_endereco2",
]
print("=== Domínios usados por cliente em public ===")
for d in doms:
    r = subprocess.run(
        ["sudo", "-u", "postgres", "psql", "-d", DB, "-tAc",
         f"SELECT typname FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace "
         f"WHERE n.nspname='public' AND t.typname='{d}' AND t.typtype='d'"],
        capture_output=True, text=True,
    )
    ok = "OK" if r.stdout.strip() else "FALTA"
    print(f"  public.{d}: {ok}")

print("\n=== Tabelas realmente faltando (amostra) ===")
for t in ["cliente", "parametros", "usuarios", "parametro", "usuario", "conhecimento", "cidade"]:
    r = subprocess.run(
        ["sudo", "-u", "postgres", "psql", "-d", DB, "-tAc",
         f"SELECT to_regclass('c2910.{t}')"],
        capture_output=True, text=True,
    )
    print(f"  c2910.{t}: {'OK' if r.stdout.strip() else 'FALTA'}")

print("\n=== Erro ao criar cliente manualmente ===")
r = subprocess.run(
    ["sudo", "-u", "postgres", "psql", "-d", DB, "-v", "ON_ERROR_STOP=1", "-c", create],
    capture_output=True, text=True,
)
print((r.stderr or r.stdout)[-1500:])
'''

def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)
    sftp = c.open_sftp()
    with sftp.open("/tmp/diag_cliente.py", "w") as f:
        f.write(REMOTE)
    sftp.close()
    _, o, e = c.exec_command("python3 /tmp/diag_cliente.py", timeout=120)
    print((o.read() + e.read()).decode("utf-8", "replace"))
    c.close()

if __name__ == "__main__":
    main()
