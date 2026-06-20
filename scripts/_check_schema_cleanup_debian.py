"""Verifica limpeza de schemas SATI no Debian."""
import paramiko
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
APP = "/home/oitamar/dashboard-financeiro-web"


def run(c, cmd, t=60):
    _, o, e = c.exec_command(cmd, timeout=t)
    o.channel.settimeout(t)
    return (o.read() + e.read()).decode("utf-8", errors="replace")


def sudo(c, cmd, t=60):
    i, o, _ = c.exec_command(f"sudo -S {cmd}", get_pty=True)
    i.write(PASS + "\n")
    i.flush()
    o.channel.settimeout(t)
    return o.read().decode("utf-8", errors="replace")


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=20)

    print("=== .env SATI_RESTORE_KEEP_SCHEMA ===")
    print(run(c, f"grep SATI_RESTORE_KEEP {APP}/.env || echo '(nao definido)'"))

    print("\n=== schemas SATI ===")
    print(
        sudo(
            c,
            "-u postgres psql -d sat1_sati_is -c "
            "\"SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name IN ('w_carlos','c2910','c3332') ORDER BY 1;\"",
        )
    )

    print("=== dominios public.dom_* ===")
    print(
        sudo(
            c,
            "-u postgres psql -d sat1_sati_is -tAc "
            "\"SELECT COUNT(*) FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace "
            "WHERE n.nspname='public' AND t.typtype='d' AND t.typname LIKE 'dom_%'\"",
        )
    )
    c.close()


if __name__ == "__main__":
    main()
