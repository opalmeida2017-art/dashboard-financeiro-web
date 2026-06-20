"""Auditoria fluxo painel BI -> provision -> link -> import."""
import paramiko
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"


def run(c, cmd, t=90):
    _, o, e = c.exec_command(cmd, timeout=t)
    o.channel.settimeout(t)
    return (o.read() + e.read()).decode("utf-8", errors="replace")


def sudo(c, cmd, t=90):
    i, o, _ = c.exec_command(f"sudo -S {cmd}", get_pty=True)
    i.write(PASS + "\n")
    i.flush()
    o.channel.settimeout(t)
    return o.read().decode("utf-8", errors="replace")


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=20)

    print("=== garantir_schema_sati_vazio no BIWEB ===")
    print(run(c, "grep -n 'def garantir_schema\\|def _garantir_schema' /home/oitamar/dashboard-financeiro-web/sati_db_restore.py | head -10"))

    print("\n=== TENANTS_ROOT ===")
    print(run(c, "grep TENANTS_ROOT /opt/nfe-web/deploy/provision_bi_tenant.py | head -5"))

    print("\n=== public_urls.py ===")
    print(run(c, "cat /opt/nfe-web/public_urls.py"))

    print("\n=== tenants BI registrados ===")
    print(sudo(c, "-u postgres psql -d nfe_web -c \"SELECT slug, pg_database, ativo, left(url,60) FROM painel_bi_tenant\""))

    print("\n=== bancos bi_* ===")
    print(sudo(c, "-u postgres psql -d postgres -c \"SELECT datname FROM pg_database WHERE datname LIKE 'bi_%' OR datname IN ('dashboard_db','sat1_sati_is') ORDER BY 1\""))

    print("\n=== nginx biweb ===")
    print(run(c, "grep -rn biweb /etc/nginx/ 2>/dev/null | head -30"))

    print("\n=== env dashboard-financeiro-web (chaves SATI) ===")
    print(run(c, "grep -E '^(SATI_|DATABASE_|BIWEB_|URL_LOGIN|USUARIO_ROBO)' /home/oitamar/dashboard-financeiro-web/.env | sed 's/=.*/=***/'"))

    print("\n=== teste provision schema logic ===")
    print(run(c, "grep -n '_schema_from' /opt/nfe-web/deploy/provision_bi_tenant.py"))

    c.close()


if __name__ == "__main__":
    main()
