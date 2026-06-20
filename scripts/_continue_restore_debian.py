"""Continua restore: data + post-data + rename c2910 -> w_carlos."""
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
APP = "/home/oitamar/dashboard-financeiro-web"
ENV = f"{APP}/.env"
ZIP = f"{APP}/downloads/1/SATI-c2910-atual.zip"
LOG = f"{APP}/restore_continue.log"
LOCAL = r"c:\python\BIWEB"
PG_RESTORE = "/usr/lib/postgresql/17/bin/pg_restore"
DB = "sat1_sati_is"


def run(c, cmd, timeout=120):
    _, o, e = c.exec_command(cmd, timeout=timeout)
    o.channel.settimeout(timeout)
    try:
        return (o.read() + e.read()).decode("utf-8", errors="replace")
    except Exception:
        return ""


def sudo(c, cmd, timeout=600):
    i, o, _ = c.exec_command(f"sudo -S {cmd}", get_pty=True)
    i.write(PASS + "\n")
    i.flush()
    o.channel.settimeout(timeout)
    try:
        return o.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=20)

    sftp = c.open_sftp()
    sftp.put(f"{LOCAL}\\sati_db_restore.py", f"{APP}/sati_db_restore.py")
    sftp.close()

    run(c, "pkill -f processar_arquivo_zip_sati || true", 15)
    run(c, f"truncate -s 0 {LOG}", 10)

    print("=== estado atual ===")
    print(
        sudo(
            c,
            f"-u postgres psql -d {DB} -c "
            "\"SELECT table_schema, COUNT(*) FROM information_schema.tables "
            "WHERE table_schema IN ('c2910','w_carlos') GROUP BY 1;\"",
        )
    )
    raw = sudo(
        c,
        f"-u postgres psql -d {DB} -tAc "
        "\"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='c2910'\"",
    )
    digits = "".join(ch for ch in raw if ch.isdigit())
    n = int(digits) if digits else 0
    if n < 50:
        print("c2910 sem tabelas suficientes — rode restore completo.")
        c.close()
        return

    print("Extraindo dump para /var/tmp...")
    py = f"""
import uuid, shutil, zipfile
from pathlib import Path
z = Path('{ZIP}')
tmp = Path('/home/oitamar/tmp_sati') / f'cont_{{uuid.uuid4().hex}}'
tmp.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(z) as zf:
    zf.extractall(tmp)
dumps = list(tmp.rglob('*.dump'))
dump = sorted(dumps, key=lambda p: p.stat().st_mtime, reverse=True)[0]
dest = Path('/home/oitamar/tmp_sati/sati_continue.dump')
shutil.copy2(dump, dest)
dest.chmod(0o644)
print(dest)
"""
    dump_path = run(c, f"cd {APP} && ./venv/bin/python -c \"{py}\"", 180).strip().splitlines()[-1]
    print(f"Dump: {dump_path}")

    for label, section in (("data", "data"), ("post-data", "post-data")):
        print(f"pg_restore {section}...")
        out = sudo(
            c,
            f"-u postgres {PG_RESTORE} -d {DB} --no-owner --no-acl "
            f"--section={section} {dump_path} 2>&1 | tail -5",
            timeout=7200,
        )
        print(out[-1500:])

    print("Renomeando c2910 -> w_carlos...")
    sudo(c, f"-u postgres psql -d {DB} -v ON_ERROR_STOP=1 -c 'DROP SCHEMA IF EXISTS w_carlos CASCADE;'")
    print(
        sudo(
            c,
            f"-u postgres psql -d {DB} -v ON_ERROR_STOP=1 -c 'ALTER SCHEMA c2910 RENAME TO w_carlos;'",
        )
    )

    print("=== validação ===")
    print(
        sudo(
            c,
            f"-u postgres psql -d {DB} -tAc "
            "\"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='w_carlos'\"",
        )
    )
    print(
        sudo(
            c,
            f"-u postgres psql -d {DB} -tAc "
            "\"SELECT COUNT(*) FROM w_carlos.conhecimento\"",
        )
    )
    c.close()


if __name__ == "__main__":
    main()
