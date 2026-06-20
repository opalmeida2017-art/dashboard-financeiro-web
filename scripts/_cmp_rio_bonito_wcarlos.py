"""Compara bi_rio_bonito (OK) vs bi_wcarlos (falhou) — dom_endereco255."""
import paramiko

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"

REMOTE = r'''
import subprocess, tempfile, zipfile, re
from pathlib import Path

def q(db, sql):
    r = subprocess.run(
        ["sudo", "-u", "postgres", "psql", "-d", db, "-tAc", sql],
        capture_output=True, text=True,
    )
    return (r.stdout or "").strip()

def check_db(label, db, schema):
    print(f"\n{'='*60}")
    print(f"BANCO: {label} ({db}) schema {schema}")
    print('='*60)
    for dom in ["dom_endereco255", "dom_endereco", "dom_endereco2"]:
        c = q(db, f"SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace "
                   f"WHERE n.nspname='{schema}' AND t.typname='{dom}' AND t.typtype='d'")
        p = q(db, f"SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace "
                   f"WHERE n.nspname='public' AND t.typname='{dom}' AND t.typtype='d'")
        print(f"  {dom}: c2910/c3219={'OK' if c else 'NAO'}  public={'OK' if p else 'NAO'}")
    cliente = q(db, f"SELECT to_regclass('{schema}.cliente')")
    ntab = q(db, f"SELECT count(*) FROM pg_tables WHERE schemaname='{schema}'")
    nconh = q(db, f"SELECT count(*) FROM {schema}.conhecimento") if cliente else "—"
    print(f"  cliente: {'OK' if cliente else 'FALTA'}")
    print(f"  tabelas schema: {ntab}")
    print(f"  conhecimento linhas: {nconh}")

check_db("RIO BONITO (sucesso)", "bi_rio_bonito", "c3219")
check_db("W CARLOS (falhou)", "bi_wcarlos", "c2910")

# dumps nos downloads
for zip_name, schema in [
    ("SATI-c3219-atual.zip", "c3219"),
    ("SATI-c2910-atual.zip", "c2910"),
]:
    zip_path = f"/home/oitamar/dashboard-financeiro-web/downloads/1/{zip_name}"
    if not Path(zip_path).is_file():
        print(f"\nZIP ausente: {zip_path}")
        continue
    tmpdir = tempfile.mkdtemp()
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(tmpdir)
    dump = next(Path(tmpdir).rglob("*.dump"))
    sql = subprocess.run(
        ["/usr/lib/postgresql/17/bin/pg_restore", "-f", "-", str(dump)],
        capture_output=True, text=True,
    ).stdout
    has_dom = bool(re.search(r"CREATE DOMAIN c\d+\.dom_endereco255\b", sql, re.I))
    uses_dom = "dom_endereco255" in sql
    cliente_uses = "public.dom_endereco255" in sql
    create_dom_line = [ln for ln in sql.splitlines() if "dom_endereco255" in ln.lower()]
    print(f"\n--- DUMP {zip_name} ---")
    print(f"  CREATE DOMAIN dom_endereco255 no dump: {'SIM' if has_dom else 'NAO'}")
    print(f"  Referencia dom_endereco255: {'SIM' if uses_dom else 'NAO'}")
    print(f"  cliente usa public.dom_endereco255: {'SIM' if cliente_uses else 'NAO'}")
    if create_dom_line:
        for ln in create_dom_line[:5]:
            print(f"    > {ln.strip()[:120]}")
'''

def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)
    sftp = c.open_sftp()
    with sftp.open("/tmp/cmp_dom.py", "w") as f:
        f.write(REMOTE)
    sftp.close()
    _, o, e = c.exec_command("python3 /tmp/cmp_dom.py", timeout=180)
    print((o.read() + e.read()).decode("utf-8", "replace"))
    c.close()


if __name__ == "__main__":
    main()
