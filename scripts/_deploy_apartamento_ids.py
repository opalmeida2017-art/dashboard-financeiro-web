"""Deploy apartamento_id sequencial + corrige wcarlos=1, rio-bonito=2 no Debian."""
import os
import re
import shutil
import sys
from pathlib import Path

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
BI = "/home/oitamar/dashboard-financeiro-web"
NFE = "/opt/nfe-web"
LOCAL = Path(r"c:\python\BIWEB")
TENANTS = "/opt/biweb/tenants"

# slug -> apartamento_id desejado
APARTAMENTOS = {
    "wcarlos": 1,
    "rio-bonito": 2,
}


def run(c, cmd, t=120):
    _, o, e = c.exec_command(cmd, timeout=t)
    o.channel.settimeout(t)
    return (o.read() + e.read()).decode("utf-8", "replace")


def sudo(c, cmd, t=120):
    i, o, _ = c.exec_command(f"sudo -S bash -lc {repr(cmd)}", get_pty=True)
    i.write(PASS + "\n")
    i.flush()
    o.channel.settimeout(t)
    return o.read().decode("utf-8", "replace")


def patch_file(path: Path, old: str, new: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        return new in text
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    return True


REMOTE_FIX_PY = r'''
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, "/opt/nfe-web")
os.chdir("/opt/nfe-web")

TENANTS = Path("/opt/biweb/tenants")
APARTAMENTOS = {"wcarlos": 1, "rio-bonito": 2}

def patch_env(pasta: Path, apt_id: int):
    import subprocess

    for nome in ("tenant.env", ".env"):
        p = pasta / nome
        if not p.is_file() and nome != "tenant.env":
            continue
        if p.is_file():
            raw = p.read_text(encoding="utf-8")
        else:
            raw = ""
        lines = []
        found = False
        for line in raw.splitlines():
            if line.startswith("BIWEB_TRANSPORTADORA_ID="):
                lines.append(f"BIWEB_TRANSPORTADORA_ID={apt_id}")
                found = True
            else:
                lines.append(line)
        if not found:
            lines.append(f"BIWEB_TRANSPORTADORA_ID={apt_id}")
        content = "\n".join(lines) + "\n"
        tmp = Path(f"/tmp/biweb_env_{pasta.name}_{nome}")
        tmp.write_text(content, encoding="utf-8")
        subprocess.run(["sudo", "cp", str(tmp), str(p)], check=False)
        subprocess.run(["sudo", "chown", "nfe-web:nfe-web", str(p)], check=False)
        tmp.unlink(missing_ok=True)

def migrar_banco(pg_db: str, apt_id: int):
    import database_connection as dc
    import psycopg2
    from deploy.provision_bi_tenant import _migrar_apartamento_id_cur

    conn = psycopg2.connect(**{**dc._dsn(), "dbname": pg_db})
    try:
        conn.autocommit = False
        cur = conn.cursor()
        cur.execute("SELECT id FROM apartamentos ORDER BY id LIMIT 1")
        row = cur.fetchone()
        if row and int(row[0]) != apt_id:
            _migrar_apartamento_id_cur(cur, int(row[0]), apt_id)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def mover_downloads(pasta: Path, apt_id: int):
    import subprocess

    dl = pasta / "downloads"
    subprocess.run(["sudo", "mkdir", "-p", str(dl)], check=False)
    dest = dl / str(apt_id)
    legado = dl / "1"
    if apt_id != 1 and legado.is_dir():
        if not dest.exists():
            subprocess.run(["sudo", "mv", str(legado), str(dest)], check=False)
    subprocess.run(["sudo", "mkdir", "-p", str(dest)], check=False)
    subprocess.run(["sudo", "chown", "-R", "nfe-web:nfe-web", str(dl)], check=False)

def main():
    import bi_store as bs
    from deploy.provision_bi_tenant import salvar_apartamento_painel

    bs.ensure_schema()
    for slug, apt_id in APARTAMENTOS.items():
        salvar_apartamento_painel(slug, apt_id)
        pasta = TENANTS / slug
        if not pasta.is_dir():
            for child in TENANTS.iterdir():
                env = child / "tenant.env"
                if env.is_file() and f"BI_TENANT_SLUG={slug}" in env.read_text(encoding="utf-8"):
                    pasta = child
                    break
        if pasta.is_dir():
            patch_env(pasta, apt_id)
            mover_downloads(pasta, apt_id)
        item = None
        for t in bs.list_tenants():
            if str(t.get("slug", "")).lower() == slug:
                item = t
                break
        if item and item.get("pg_database"):
            migrar_banco(item["pg_database"], apt_id)
        print(f"OK {slug} -> apartamento {apt_id}")

    print("=== painel_bi_tenant ===")
    conn = bs._connect_central()
    cur = conn.cursor()
    cur.execute("SELECT slug, apartamento_id, pg_database FROM painel_bi_tenant ORDER BY apartamento_id NULLS LAST, slug")
    for row in cur.fetchall():
        print(row)
    conn.close()

if __name__ == "__main__":
    main()
'''


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)

    # Patch bi_store.register_tenant para gravar apartamento_id
    bi_store = f"{NFE}/bi_store.py"
    reg = f"{NFE}/bi_tenant_registry.py"
    prov = f"{NFE}/deploy/provision_bi_tenant.py"

    print("=== Baixar bi_store / bi_tenant_registry para patch local ===")
    sftp = c.open_sftp()
    tmp_bs = LOCAL / "scripts" / "_tmp_bi_store.py"
    tmp_reg = LOCAL / "scripts" / "_tmp_bi_tenant_registry.py"
    sftp.get(bi_store, str(tmp_bs))
    sftp.get(reg, str(tmp_reg))

    patch_file(
        tmp_bs,
        "(slug, razao, pg_db, None, url)",
        "(slug, razao, pg_db, apartamento_id, url)",
    )
    patch_file(
        tmp_reg,
        "item = _store().register_tenant(razao, slug, url, None, pg_db)",
        "item = _store().register_tenant(razao, slug, url, apartamento_id, pg_db)",
    )
    patch_file(
        tmp_reg,
        '"apartamento_id": None,',
        '"apartamento_id": apartamento_id,',
    )

    uploads = [
        (str(LOCAL / "scripts" / "_server_provision_bi_tenant.py"), prov),
        (str(LOCAL / "scripts" / "_server_painel.js"), f"{NFE}/frontend/painel/painel.js"),
        (str(tmp_bs), bi_store),
        (str(tmp_reg), reg),
    ]
    for src, dst in uploads:
        print(f"Upload {dst}")
        sftp.put(src, dst)
    sftp.close()

    fix_path = f"{NFE}/deploy/_fix_apartamento_ids_run.py"
    sftp2 = c.open_sftp()
    with sftp2.file(fix_path, "w") as f:
        f.write(REMOTE_FIX_PY)
    sftp2.close()

    print("\n=== Aplicar apartamentos wcarlos=1, rio-bonito=2 ===")
    print(
        run(
            c,
            f"cd {NFE} && ./venv/bin/python deploy/_fix_apartamento_ids_run.py",
            t=180,
        )
    )

    print("\n=== Reiniciar gunicorn BI ===")
    print(
        run(
            c,
            f"pkill -HUP -f 'gunicorn.*127.0.0.1:8000' 2>/dev/null; sleep 2; "
            f"pgrep -af '127.0.0.1:8000' | head -2",
            t=30,
        )
    )
    c.close()
    print("Deploy apartamento_id concluído.")


if __name__ == "__main__":
    main()
