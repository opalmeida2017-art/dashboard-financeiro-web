"""Limpa /tmp, schema c2910 e roda restore completo w-carlos."""
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


def psql_count(c, sql, timeout=60):
    out = sudo(
        c,
        f"-u postgres psql -d sat1_sati_is -tAc \"{sql}\" 2>/dev/null",
        timeout=timeout,
    )
    for line in reversed(out.strip().splitlines()):
        line = line.strip()
        if line.isdigit():
            return int(line)
    return -1


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=20)

    sftp = c.open_sftp()
    sftp.put(f"{LOCAL}\\sati_db_restore.py", f"{APP}/sati_db_restore.py")
    sftp.close()

    print("=== Disco antes ===")
    print(run(c, "df -h /var /tmp /home | tail -4"))

    print("=== Limpando /tmp (arquivos >1d) ===")
    print(sudo(c, "find /tmp -mindepth 1 -mtime +0 -delete 2>/dev/null; df -h /tmp | tail -1"))

    run(c, "pkill -f processar_arquivo_zip_sati || true", 15)
    run(c, "pkill -f scripts_teste_restore_w_carlos || true", 10)
    run(c, f"rm -f {APP}/data/sati_restore.lock; truncate -s 0 {LOG}", 10)
    run(c, "rm -f /var/tmp/sati_* 2>/dev/null; mkdir -p /home/oitamar/tmp_sati", 10)

    print("=== Limpando schema c2910 e domínios public ===")
    sql = r"""
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

    tabs_antes = psql_count(
        c, "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='c2910'"
    )
    print(f"Tabelas c2910 antes do restore: {tabs_antes}")

    print("=== Iniciando restore (pode levar vários minutos) ===")
    run(
        c,
        f"cd {APP} && export $(grep -v '^#' {ENV} | xargs) && "
        f"nohup ./venv/bin/python -c \""
        f"from pathlib import Path; from sati_integration.robos from sati_integration.robos import sati_db_restore as s; "
        f"s.processar_arquivo_zip_sati(Path('{ZIP}'), apartamento_id=1)"
        f"\" > {LOG} 2>&1 &",
        30,
    )

    ok = False
    for i in range(120):
        time.sleep(30)
        try:
            tail = run(c, f"tail -20 {LOG}", 30)
        except Exception:
            c.connect(HOST, username=USER, password=PASS, timeout=20)
            tail = run(c, f"tail -20 {LOG}", 30)
        print(f"--- poll {i + 1} ---")
        print(tail[-2800:])
        if "Restore do schema SATI concluído" in tail:
            ok = True
            break
        if "Traceback" in tail or "pre-data incompleto" in tail:
            break

    tabs = psql_count(
        c, "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='c2910'"
    )
    conh = psql_count(c, "SELECT COUNT(*) FROM c2910.conhecimento")
    http = run(
        c,
        'curl -s -o /dev/null -w "%{http_code}" -H "X-BI-Tenant-Slug: w-carlos" http://127.0.0.1:8000/',
    ).strip()

    print("\n=== RESULTADO ===")
    print(f"Restore: {'SUCESSO' if ok else 'FALHOU'}")
    print(f"Tabelas c2910: {tabs}")
    print(f"CT-es conhecimento: {conh}")
    print(f"HTTP painel: {http}")
    print("=== Disco depois ===")
    print(run(c, "df -h /var /tmp /home | tail -4"))

    c.close()


if __name__ == "__main__":
    main()
