"""Deploy banco exclusivo por cliente, remove w-carlos antigo e recria do zero."""
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
BI = "/home/oitamar/dashboard-financeiro-web"
NFE = "/opt/nfe-web"
LOCAL = r"c:\python\BIWEB"
SATI_URL = "https://sat3.intersite.com.br/c2910"
SLUG = "w-carlos"
RAZAO = "W CARLOS"


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


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)

    sftp = c.open_sftp()
    uploads = [
        (f"{LOCAL}\\bi_tenant_runtime.py", f"{BI}/bi_tenant_runtime.py"),
        (f"{LOCAL}\\db_connection.py", f"{BI}/db_connection.py"),
        (f"{LOCAL}\\database.py", f"{BI}/database.py"),
        (f"{LOCAL}\\sati_source.py", f"{BI}/sati_source.py"),
        (f"{LOCAL}\\app.py", f"{BI}/app.py"),
        (f"{LOCAL}\\bi_tenant_context.py", f"{BI}/bi_tenant_context.py"),
        (f"{LOCAL}\\sati_db_restore.py", f"{BI}/sati_db_restore.py"),
        (f"{LOCAL}\\scripts\\_server_provision_bi_tenant.py", f"{NFE}/deploy/provision_bi_tenant.py"),
        (f"{LOCAL}\\scripts\\_server_painel.js", f"{NFE}/frontend/painel/painel.js"),
    ]
    for src, dst in uploads:
        print(f"Upload {dst}")
        sftp.put(src, dst)
    remote_script = "/home/oitamar/recriar_w_carlos.py"
    run(c, f"rm -f {remote_script} 2>/dev/null; true")
    sftp.put(f"{LOCAL}\\scripts\\_recriar_w_carlos_server.py", remote_script)
    sftp.close()

    print("\n=== Ajustar permissões nfe-web ===")
    print(
        sudo(
            c,
            f"chown -R nfe-web:nfe-web /opt/nfe-web/bi_tenants.json /opt/biweb/tenants {remote_script}; "
            "chmod 775 /opt/biweb/tenants 2>/dev/null; true",
        )
    )

    print("\n=== Remover + criar w-carlos (banco exclusivo) ===")
    print(sudo(c, f"-u nfe-web /opt/nfe-web/venv/bin/python {remote_script} recriar", 300))

    print("\n=== Reiniciar nfe-web ===")
    print(sudo(c, "systemctl restart nfe-web", 60))
    time.sleep(2)

    print("\n=== tenant.env ===")
    print(run(c, f"cat /opt/biweb/tenants/{SLUG}/tenant.env"))

    print("\n=== Reiniciar gunicorn BI ===")
    print(run(c, "pkill -HUP -f 'gunicorn.*8000' || true"))
    time.sleep(2)

    tenant_db = "bi_w_carlos"
    print("\n=== Verificar banco exclusivo ===")
    print(
        sudo(
            c,
            f"-u postgres psql -d {tenant_db} -c "
            "\"SELECT chave, left(valor,55) FROM configuracoes_robo ORDER BY chave\"",
        )
    )
    print(
        sudo(
            c,
            "-u postgres psql -d postgres -tAc "
            f"\"SELECT 1 FROM pg_database WHERE datname='{tenant_db}'\"",
        )
    )

    print(
        sudo(
            c,
            "-u postgres psql -d bi_w_carlos -tAc "
            "\"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='c2910'\"",
        )
    )
    print(
        sudo(
            c,
            "-u postgres psql -d bi_w_carlos -tAc "
            "\"SELECT schema_name FROM information_schema.schemata WHERE schema_name='c2910'\"",
        )
    )

    http = run(
        c,
        f'curl -s -o /dev/null -w "%{{http_code}}" -H "X-BI-Tenant-Slug: {SLUG}" http://127.0.0.1:8000/',
    ).strip()
    print(f"\nHTTP painel ({SLUG}): {http}")
    print("\nDeploy concluído. Rode a atualização SATI pelo painel BI para popular o schema c2910.")

    c.close()


if __name__ == "__main__":
    main()
