"""Deploy provision + schema template Windows para Debian."""
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
NFE = "/opt/nfe-web"
BI = "/home/oitamar/dashboard-financeiro-web"
LOCAL = r"c:\python\BIWEB"
SCHEMA_REMOTE = "/opt/biweb/schema-template"


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
    c.connect(HOST, username=USER, password=PASS, timeout=25)

    print("=== Pasta schema-template ===")
    print(sudo(c, f"mkdir -p {SCHEMA_REMOTE} && chown -R oitamar:oitamar {SCHEMA_REMOTE} || mkdir -p /tmp/biweb-schema"))

    sftp = c.open_sftp()
    tmp_sql = "/tmp/biweb_app_schema_template.sql"
    sftp.put(f"{LOCAL}\\sql\\biweb_app_schema_template.sql", tmp_sql)
    print(sudo(c, f"mkdir -p {NFE}/deploy/schema && cp {tmp_sql} {NFE}/deploy/schema/biweb_app_schema_template.sql"))
    print(sudo(c, f"cp {tmp_sql} {SCHEMA_REMOTE}/biweb_app_schema_template.sql 2>/dev/null || true"))
    uploads = [
        (f"{LOCAL}\\sati_dominios_patch.py", f"{BI}/sati_dominios_patch.py"),
        (f"{LOCAL}\\sati_dominios_patch.py", f"{NFE}/deploy/sati_dominios_patch.py"),
        (f"{LOCAL}\\sati_db_restore.py", f"{BI}/sati_db_restore.py"),
        (f"{LOCAL}\\scripts\\_server_provision_bi_tenant.py", f"{NFE}/deploy/provision_bi_tenant.py"),
        (f"{LOCAL}\\bi_tenant_runtime.py", f"{BI}/bi_tenant_runtime.py"),
        (f"{LOCAL}\\biweb_paths.py", f"{BI}/biweb_paths.py"),
        (f"{LOCAL}\\bi_tenant_context.py", f"{BI}/bi_tenant_context.py"),
        (f"{LOCAL}\\scripts\\_server_painel.js", f"{NFE}/frontend/painel/painel.js"),
    ]
    for src, dst in uploads:
        print(f"Upload {dst}")
        sftp.put(src, dst)
    sftp.close()

    print("\n=== Teste import provision ===")
    print(
        run(
            c,
            f"cd {NFE} && ./venv/bin/python -c "
            "\"from deploy.provision_bi_tenant import _localizar_template_schema; "
            "p=_localizar_template_schema(); print('template', p)\"",
        )
    )

    print("\n=== Reiniciar serviços ===")
    run(c, "pkill -HUP -f 'gunicorn.*8000' 2>/dev/null || true")
    run(c, "pkill -HUP -f 'uvicorn.*nfe' 2>/dev/null || true")

    c.close()
    print("Deploy provision/schema concluído.")


if __name__ == "__main__":
    main()
