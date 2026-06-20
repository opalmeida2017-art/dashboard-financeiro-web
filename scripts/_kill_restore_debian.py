"""Mata restore em andamento e revalida w_carlos."""
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


def dig(s):
    d = "".join(ch for ch in s if ch.isdigit())
    return int(d) if d else 0


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=20)

    print("Matando restores...")
    run(c, "pkill -f processar_arquivo_zip_sati; pkill -f sati_db_restore; pkill -f restore_manual", 15)
    run(c, f"rm -f {APP}/data/sati_restore.lock", 10)

    tabs = dig(
        sudo(
            c,
            "-u postgres psql -d sat1_sati_is -tAc "
            "\"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='w_carlos'\"",
        )
    )
    conh = dig(
        sudo(
            c,
            "-u postgres psql -d sat1_sati_is -tAc "
            "\"SELECT COUNT(*) FROM w_carlos.conhecimento\" 2>&1",
        )
    )
    print(f"w_carlos: {tabs} tabelas, {conh} conhecimentos")
    c.close()
    return tabs, conh


if __name__ == "__main__":
    main()
