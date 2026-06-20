"""Corrige provision_bi_tenant, recria w-carlos e restore SATI c2910."""
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
BI = "/home/oitamar/dashboard-financeiro-web"
NFE = "/opt/nfe-web"
LOCAL = r"c:\python\BIWEB"
ZIP = f"{BI}/downloads/1/SATI-c2910-atual.zip"
LOG = f"{BI}/restore_w_carlos_fix.log"
SATI_URL = "https://sat3.intersite.com.br/c2910"


def run(c, cmd, t=120):
    _, o, e = c.exec_command(cmd, timeout=t)
    o.channel.settimeout(t)
    return (o.read() + e.read()).decode("utf-8", errors="replace")


def sudo(c, cmd, t=300):
    i, o, _ = c.exec_command(f"sudo -S {cmd}", get_pty=True)
    i.write(PASS + "\n")
    i.flush()
    o.channel.settimeout(t)
    return o.read().decode("utf-8", errors="replace")


def psql_count(c, sql):
    out = sudo(c, f"-u postgres psql -d sat1_sati_is -tAc \"{sql}\" 2>/dev/null", 60)
    for line in reversed(out.strip().splitlines()):
        line = line.strip()
        if line.isdigit():
            return int(line)
    return -1


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)

    sftp = c.open_sftp()
    for src, dst in [
        (f"{LOCAL}\\scripts\\_server_provision_bi_tenant.py", f"{NFE}/deploy/provision_bi_tenant.py"),
        (f"{LOCAL}\\sati_db_restore.py", f"{BI}/sati_db_restore.py"),
        (f"{LOCAL}\\sati_source.py", f"{BI}/sati_source.py"),
    ]:
        print(f"Upload {dst}")
        sftp.put(src, dst)
    sftp.close()

    print("\n=== Teste import provision_bi_tenant ===")
    print(
        run(
            c,
            f"cd {NFE} && ./venv/bin/python -c "
            "\"from deploy.provision_bi_tenant import remover_instancia_bi, criar_instancia_bi; print('ok')\"",
        )
    )

    print("\n=== Reiniciar nfe-web ===")
    print(sudo(c, "systemctl restart nfe-web", 60))
    time.sleep(3)

    print("\n=== Recriar w-carlos (banco + link + schema vazio) ===")
    recreate = (
        f"cd {NFE} && ./venv/bin/python -c \""
        f"from deploy.provision_bi_tenant import criar_instancia_bi; "
        f"r=criar_instancia_bi('W CARLOS', 'w-carlos', '{SATI_URL}'); "
        f"print('slug', r.get('slug')); print('db', r.get('pg_database')); print('url', r.get('url'))\""
    )
    print(run(c, recreate, 180))

    print("\n=== Limpar schema c2910 corrompido ===")
    clean_sql = f"{BI}/scripts_clean_c2910.sql"
    sql_body = """
DROP SCHEMA IF EXISTS c2910 CASCADE;
DO $body$
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
END $body$;
"""
    sftp2 = c.open_sftp()
    with sftp2.open(clean_sql, "w") as f:
        f.write(sql_body)
    sftp2.close()
    print(sudo(c, f"-u postgres psql -d sat1_sati_is -v ON_ERROR_STOP=1 -f {clean_sql}", 120))

    print("\n=== Restore SATI c2910 ===")
    run(c, f"rm -f {BI}/data/sati_restore.lock; truncate -s 0 {LOG}", 15)
    run(
        c,
        f"cd {BI} && export $(grep -v '^#' .env | xargs) && "
        f"export BI_TENANTS_ROOT=/opt/biweb/tenants && "
        f"nohup ./venv/bin/python -c \""
        f"from pathlib import Path; from sati_integration.robos from sati_integration.robos import sati_db_restore as s; "
        f"s.processar_arquivo_zip_sati(Path('{ZIP}'), apartamento_id=1)"
        f"\" > {LOG} 2>&1 &",
        20,
    )

    ok = False
    for i in range(60):
        time.sleep(20)
        tail = run(c, f"tail -12 {LOG}", 30)
        print(f"--- restore {i+1} ---")
        print(tail[-1800:])
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
    print(f"Restore SATI: {'OK' if ok else 'FALHOU'}")
    print(f"Tabelas c2910: {tabs}")
    print(f"CT-es: {conh}")
    print(f"HTTP painel: {http}")

    cfg = sudo(
        c,
        "-u postgres psql -d bi_w_carlos -c "
        "\"SELECT chave, left(valor,60) FROM configuracoes_robo ORDER BY chave\"",
    )
    print(cfg)

    c.close()


if __name__ == "__main__":
    main()
