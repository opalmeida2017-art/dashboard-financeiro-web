"""Alinha SATI_SCHEMA=c2910 e renomeia w_carlos->c2910 se necessário."""
import paramiko
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
APP = "/home/oitamar/dashboard-financeiro-web"
ENV = f"{APP}/.env"


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

    sftp = c.open_sftp()
    sftp.put(r"c:\python\BIWEB\sati_db_restore.py", f"{APP}/sati_db_restore.py")
    sftp.close()

    wc = "".join(ch for ch in sudo(c, "-u postgres psql -d sat1_sati_is -tAc \"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='w_carlos'\"") if ch.isdigit())
    c2 = "".join(ch for ch in sudo(c, "-u postgres psql -d sat1_sati_is -tAc \"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='c2910'\"") if ch.isdigit())

    if int(wc or 0) > 0 and int(c2 or 0) == 0:
        print("Renomeando w_carlos -> c2910...")
        print(sudo(c, "-u postgres psql -d sat1_sati_is -c 'ALTER SCHEMA w_carlos RENAME TO c2910;'"))
    elif int(wc or 0) > 0 and int(c2 or 0) > 0:
        print("Ambos schemas existem — mantendo c2910; removendo w_carlos órfão...")
        print(sudo(c, "-u postgres psql -d sat1_sati_is -c 'DROP SCHEMA IF EXISTS w_carlos CASCADE;'"))

    run(c, f"sed -i 's/^SATI_SCHEMA=.*/SATI_SCHEMA=c2910/' {ENV}")
    print(run(c, f"grep SATI_SCHEMA {ENV}"))

    print(sudo(c, "-u postgres psql -d sat1_sati_is -tAc \"SELECT COUNT(*) FROM c2910.conhecimento\""))
    c.close()


if __name__ == "__main__":
    main()
