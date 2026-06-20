"""Deploy correções fluxo painel BI → provision → link → import SATI."""
import paramiko
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
BI = "/home/oitamar/dashboard-financeiro-web"
NFE = "/opt/nfe-web"
LOCAL = r"c:\python\BIWEB"


def run(c, cmd, t=120):
    _, o, e = c.exec_command(cmd, timeout=t)
    o.channel.settimeout(t)
    return (o.read() + e.read()).decode("utf-8", errors="replace")


def sudo(c, cmd, t=120):
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
    uploads = [
        (f"{LOCAL}\\sati_db_restore.py", f"{BI}/sati_db_restore.py"),
        (f"{LOCAL}\\sati_source.py", f"{BI}/sati_source.py"),
        (f"{LOCAL}\\bi_tenant_context.py", f"{BI}/bi_tenant_context.py"),
        (f"{LOCAL}\\biweb_paths.py", f"{BI}/biweb_paths.py"),
        (f"{LOCAL}\\scripts\\_server_provision_bi_tenant.py", f"{NFE}/deploy/provision_bi_tenant.py"),
        (f"{LOCAL}\\scripts\\_server_painel.js", f"{NFE}/frontend/painel/painel.js"),
    ]
    for src, dst in uploads:
        print(f"Upload {dst}")
        sftp.put(src, dst)
    sftp.close()

    # Campo URL SATI no painel HTML
    html_patch = r"""
      <div class="form-row">
        <label>URL login SATI (código cliente)</label>
        <input id="bi-url-login" placeholder="https://sat3.intersite.com.br/c2910" />
      </div>
"""
    run(
        c,
        f"grep -q 'bi-url-login' {NFE}/frontend/painel/index.html || "
        f"sed -i '/id=\"bi-slug\"/a\\      <div class=\"form-row\">\\n        <label>URL login SATI (código cliente)</label>\\n        <input id=\"bi-url-login\" placeholder=\"https://sat3.intersite.com.br/c2910\" />\\n      </div>' "
        f"{NFE}/frontend/painel/index.html",
    )

    print("\n=== Corrigir w-carlos (USE_SATI + schema c2910) ===")
    print(
        sudo(
            c,
            "-u postgres psql -d bi_w_carlos -c "
            "\"UPDATE configuracoes_robo SET valor='true' WHERE chave='USE_SATI_SOURCE'; "
            "DELETE FROM configuracoes_robo WHERE chave='SATI_PG_SCHEMA'; "
            "INSERT INTO configuracoes_robo (apartamento_id, chave, valor) "
            "SELECT 1, 'SATI_URL_CODIGO', 'c2910' "
            "WHERE NOT EXISTS (SELECT 1 FROM configuracoes_robo WHERE chave='SATI_URL_CODIGO');\"",
        )
    )

    print("\n=== Teste garantir_schema_sati_vazio ===")
    print(
        run(
            c,
            f"cd {BI} && export $(grep -v '^#' .env | xargs) && "
            "./venv/bin/python -c \"from sati_integration.robos from sati_integration.robos import sati_db_restore as s; print('fn', hasattr(s,'garantir_schema_sati_vazio'))\"",
        )
    )

    print("\n=== Reiniciar serviços ===")
    print(run(c, f"pkill -HUP -f 'gunicorn.*8000' || true"))
    print(run(c, "systemctl restart nfe-web 2>/dev/null || true"))

    print("\n=== w-carlos config ===")
    print(
        sudo(
            c,
            "-u postgres psql -d bi_w_carlos -c "
            "\"SELECT chave, left(valor,60) FROM configuracoes_robo ORDER BY chave\"",
        )
    )
    c.close()
    print("Deploy concluído.")


if __name__ == "__main__":
    main()
