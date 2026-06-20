"""Uma única tentativa de restore no Debian (sem poll longo)."""
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
APP = "/home/oitamar/dashboard-financeiro-web"
ENV = f"{APP}/.env"
ZIP = f"{APP}/downloads/1/SATI-c2910-atual.zip"
LOG = f"{APP}/restore_manual.log"
LOCAL = r"c:\python\BIWEB"


def run(c, cmd, timeout=120):
    _, o, e = c.exec_command(cmd, timeout=timeout)
    o.channel.settimeout(timeout)
    try:
        return (o.read() + e.read()).decode("utf-8", errors="replace")
    except Exception:
        return ""


def sudo(c, cmd, timeout=300):
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

    run(c, "pkill -f processar_arquivo_zip_sati || true; pkill -f sati_db_restore || true", 15)
    run(c, f"rm -f {APP}/data/sati_restore.lock; truncate -s 0 {LOG}", 10)
    run(c, "rm -rf /var/tmp/sati_* /home/oitamar/tmp_sati/sati_restore_* 2>/dev/null", 30)

    print("Iniciando restore (aguarde)...")
    run(
        c,
        f"cd {APP} && export $(grep -v '^#' {ENV} | xargs) && "
        f"nohup ./venv/bin/python -c \""
        f"from pathlib import Path; from sati_integration.robos from sati_integration.robos import sati_db_restore as s; "
        f"s.processar_arquivo_zip_sati(Path('{ZIP}'), apartamento_id=1)"
        f"\" > {LOG} 2>&1 &",
        30,
    )

    for i in range(80):
        time.sleep(20)
        tail = run(c, f"tail -12 {LOG}", 30)
        print(f"--- {i+1} ---")
        print(tail[-2000:])
        if "Restore do schema SATI concluído" in tail:
            print("SUCESSO")
            break
        if "Traceback" in tail or "pre-data incompleto" in tail:
            print("FALHOU")
            break

    print("=== tabelas ===")
    print(
        sudo(
            c,
            "-u postgres psql -d sat1_sati_is -tAc "
            "\"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='w_carlos'\"",
        )
    )
    print(
        sudo(
            c,
            "-u postgres psql -d sat1_sati_is -tAc "
            "\"SELECT COUNT(*) FROM w_carlos.conhecimento\"",
        )
    )
    c.close()


if __name__ == "__main__":
    main()
