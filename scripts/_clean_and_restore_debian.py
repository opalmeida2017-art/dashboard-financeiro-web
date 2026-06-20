"""Limpa schemas SATI residuais e roda restore completo."""
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

    run(c, "pkill -f processar_arquivo_zip_sati || true", 15)
    run(c, f"rm -f {APP}/data/sati_restore.lock; truncate -s 0 {LOG}", 10)
    run(c, "rm -f /var/tmp/sati_* 2>/dev/null", 10)

    print("Limpando schemas e domínios espelhados...")
    sql = """
    DROP SCHEMA IF EXISTS w_carlos CASCADE;
    DROP SCHEMA IF EXISTS c2910 CASCADE;
    DO $$
    DECLARE r record;
    BEGIN
      FOR r IN
        SELECT t.typname AS n
        FROM pg_type t
        JOIN pg_namespace ns ON ns.oid = t.typnamespace
        WHERE ns.nspname = 'public' AND t.typtype = 'd' AND t.typname LIKE 'dom_%'
      LOOP
        EXECUTE format('DROP DOMAIN IF EXISTS public.%I CASCADE', r.n);
      END LOOP;
    END $$;
    """
    print(sudo(c, f"-u postgres psql -d sat1_sati_is -v ON_ERROR_STOP=1 -c \"{sql}\""))

    print("Iniciando restore...")
    run(
        c,
        f"cd {APP} && export $(grep -v '^#' {ENV} | xargs) && "
        f"nohup ./venv/bin/python -c \""
        f"from pathlib import Path; from sati_integration.robos from sati_integration.robos import sati_db_restore as s; "
        f"s.processar_arquivo_zip_sati(Path('{ZIP}'), apartamento_id=1)"
        f"\" > {LOG} 2>&1 &",
        30,
    )

    for i in range(120):
        time.sleep(30)
        try:
            tail = run(c, f"tail -15 {LOG}", 30)
        except Exception:
            c.connect(HOST, username=USER, password=PASS, timeout=20)
            tail = run(c, f"tail -15 {LOG}", 30)
        print(f"--- {i+1} ---")
        print(tail[-2500:])
        if "Restore do schema SATI concluído" in tail:
            print("SUCESSO")
            break
        if "Traceback" in tail or "pre-data incompleto" in tail:
            print("FALHOU")
            break

    print(sudo(c, "-u postgres psql -d sat1_sati_is -tAc \"SELECT COUNT(*) FROM w_carlos.conhecimento\" 2>&1"))
    c.close()


if __name__ == "__main__":
    main()
