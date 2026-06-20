"""Deploy sati_db_restore fix + sudoers + restore c2910."""
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
BI = "/home/oitamar/dashboard-financeiro-web"
NFE = "/opt/nfe-web"
LOCAL = r"c:\python\BIWEB"
ZIP = f"{BI}/downloads/1/SATI-c2910-atual.zip"
LOG = f"{BI}/restore_w_carlos_final.log"


def run(c, cmd, t=120):
    _, o, e = c.exec_command(cmd, timeout=t)
    o.channel.settimeout(t)
    return (o.read() + e.read()).decode("utf-8", "replace")


def sudo(c, cmd, t=300):
    i, o, _ = c.exec_command(f"sudo -S {cmd}", get_pty=True)
    i.write(PASS + "\n")
    i.flush()
    o.channel.settimeout(t)
    return o.read().decode("utf-8", "replace")


def psql_count(c, sql):
    out = sudo(c, f"-u postgres psql -d sat1_sati_is -tAc \"{sql}\" 2>/dev/null", 60)
    for line in reversed(out.strip().splitlines()):
        if line.strip().isdigit():
            return int(line.strip())
    return -1


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)

    sftp = c.open_sftp()
    sftp.put(f"{LOCAL}\\sati_db_restore.py", f"{BI}/sati_db_restore.py")
    sftp.put(f"{LOCAL}\\scripts\\_server_provision_bi_tenant.py", f"{NFE}/deploy/provision_bi_tenant.py")
    sftp.close()

    sudoers = "oitamar ALL=(postgres) NOPASSWD: ALL\nwww-data ALL=(postgres) NOPASSWD: ALL\n"
    sftp2 = c.open_sftp()
    with sftp2.open("/tmp/biweb-pg-restore", "w") as f:
        f.write(sudoers)
    sftp2.close()
    print("sudoers:", sudo(c, "cp /tmp/biweb-pg-restore /etc/sudoers.d/biweb-pg-restore && chmod 440 /etc/sudoers.d/biweb-pg-restore"))
    print("sudo -n test:", run(c, "sudo -n -u postgres whoami"))

    print("\n=== Domínios public antes ===")
    print(psql_count(c, "SELECT COUNT(*) FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace WHERE n.nspname='public' AND t.typtype='d' AND t.typname LIKE 'dom_%'"))

    run(c, f"pkill -f processar_arquivo_zip_sati || true; rm -f {BI}/data/sati_restore.lock; truncate -s 0 {LOG}", 15)
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
    for i in range(90):
        time.sleep(25)
        tail = run(c, f"tail -15 {LOG}", 30)
        print(f"--- {i+1} ---\n{tail[-2000:]}")
        if "Restore do schema SATI concluído" in tail:
            ok = True
            break
        if "Traceback" in tail or "pre-data incompleto" in tail or "pg_restore (pre-data" in tail:
            break

    tabs = psql_count(c, "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='c2910'")
    conh = psql_count(c, "SELECT COUNT(*) FROM c2910.conhecimento")

    print(f"\nRESULTADO restore={'OK' if ok else 'FALHOU'} tabelas={tabs} ctes={conh}")
    print("HTTP:", run(c, 'curl -s -o /dev/null -w "%{http_code}" -H "X-BI-Tenant-Slug: w-carlos" http://127.0.0.1:8000/'))

    # teste API remover (slug fake)
    secret = run(c, f"grep -E '^ADMIN_SECRET=' {NFE}/.env | head -1").split("=", 1)[-1].strip().strip('"').strip("'")
    if secret:
        print(
            "API remove test:",
            run(
                c,
                f'curl -s -w "\\nHTTP %{{http_code}}" -X DELETE -H "X-Admin-Secret: {secret}" '
                f'"http://127.0.0.1:5000/api/painel/bi/tenants/nao-existe-slug"',
            ),
        )

    c.close()


if __name__ == "__main__":
    main()
