"""Valida restore w_carlos e tenta completar data se necessário."""
import paramiko
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
APP = "/home/oitamar/dashboard-financeiro-web"
ZIP = f"{APP}/downloads/1/SATI-c2910-atual.zip"
PG = "/usr/lib/postgresql/17/bin/pg_restore"
DB = "sat1_sati_is"


def run(c, cmd, t=120):
    _, o, e = c.exec_command(cmd, timeout=t)
    o.channel.settimeout(t)
    return (o.read() + e.read()).decode("utf-8", errors="replace")


def sudo(c, cmd, t=7200):
    i, o, _ = c.exec_command(f"sudo -S {cmd}", get_pty=True)
    i.write(PASS + "\n")
    i.flush()
    o.channel.settimeout(t)
    try:
        return o.read().decode("utf-8", errors="replace")
    except Exception:
        return "timeout"


def digits(s):
    d = "".join(ch for ch in s if ch.isdigit())
    return int(d) if d else 0


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=20)

    for tbl in ("conhecimento", "nota", "cliente", "veiculo", "manifev"):
        print(
            f"{tbl}:",
            digits(
                sudo(
                    c,
                    f"-u postgres psql -d {DB} -tAc "
                    f"\"SELECT COUNT(*) FROM w_carlos.{tbl}\" 2>&1",
                )
            ),
        )

    print("\n=== preparando dump legível pelo postgres ===")
    py = (
        "import uuid, shutil, zipfile\n"
        "from pathlib import Path\n"
        f"z = Path('{ZIP}')\n"
        "tmp = Path('/home/oitamar/tmp_sati') / ('ext_' + uuid.uuid4().hex)\n"
        "tmp.mkdir(parents=True, exist_ok=True)\n"
        "with zipfile.ZipFile(z) as zf:\n"
        "    zf.extractall(tmp)\n"
        "dump = sorted(tmp.rglob('*.dump'), key=lambda p: p.stat().st_mtime, reverse=True)[0]\n"
        "dest = Path('/var/tmp/sati_pg.dump')\n"
        "shutil.copy2(dump, dest)\n"
        "dest.chmod(0o644)\n"
        "print(dest, dest.stat().st_size)\n"
    )
    print(run(c, f"cd {APP} && ./venv/bin/python -c \"{py}\"", 180))

    print("\n=== renomear w_carlos -> c2910 para pg_restore ===")
    print(
        sudo(
            c,
            f"-u postgres psql -d {DB} -v ON_ERROR_STOP=1 -c 'ALTER SCHEMA w_carlos RENAME TO c2910;'",
        )
    )

    print("\n=== pg_restore data (pode demorar) ===")
    out = sudo(
        c,
        f"-u postgres {PG} -d {DB} --no-owner --no-acl --section=data /var/tmp/sati_pg.dump 2>&1 | tail -20",
        t=7200,
    )
    print(out[-3000:])

    print("\n=== pg_restore post-data ===")
    out2 = sudo(
        c,
        f"-u postgres {PG} -d {DB} --no-owner --no-acl --section=post-data /var/tmp/sati_pg.dump 2>&1 | tail -10",
        t=3600,
    )
    print(out2[-2000:])

    print("\n=== rename c2910 -> w_carlos ===")
    print(
        sudo(
            c,
            f"-u postgres psql -d {DB} -v ON_ERROR_STOP=1 -c 'ALTER SCHEMA c2910 RENAME TO w_carlos;'",
        )
    )

    print("\n=== contagens finais ===")
    for tbl in ("conhecimento", "nota", "cliente", "veiculo", "manifev"):
        print(
            f"{tbl}:",
            digits(
                sudo(
                    c,
                    f"-u postgres psql -d {DB} -tAc "
                    f"\"SELECT COUNT(*) FROM w_carlos.{tbl}\"",
                )
            ),
        )

    print("\n=== reiniciar app ===")
    print(sudo(c, "systemctl restart biweb-rq biweb-gunicorn 2>/dev/null || true"))
    print(run(c, "df -h /var"))
    c.close()


if __name__ == "__main__":
    main()
