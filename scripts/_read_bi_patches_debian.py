"""Lê patches BI tenant e nginx location no Debian."""
import paramiko
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"


def run(c, cmd, t=120):
    _, o, e = c.exec_command(cmd, timeout=t)
    o.channel.settimeout(t)
    return (o.read() + e.read()).decode("utf-8", errors="replace")


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=20)

    files = [
        "/home/oitamar/dashboard-financeiro-web/bi_tenant_context.py",
        "/opt/nfe-web/deploy/bi_patches/bi_tenant_context.py",
        "/opt/nfe-web/deploy/bi_patches/apply_bi_isolation.py",
    ]
    for f in files:
        print(f"\n### {f}")
        print(run(c, f"cat {f} 2>/dev/null")[:12000])

    print("\n### nginx biweb block")
    print(run(c, "sed -n '88,115p' /etc/nginx/sites-available/default"))

    print("\n### tenant w-carlos")
    print(run(c, "find /opt/biweb/tenants/w-carlos -type f | head -20"))
    print(run(c, "cat /opt/biweb/tenants/w-carlos/tenant.env 2>/dev/null"))
    print(run(c, "head -30 /opt/biweb/tenants/w-carlos/.env 2>/dev/null || echo sem .env"))

    print("\n### painel bi tenants")
    i, o, _ = c.exec_command("sudo -S -u postgres psql -d nfe_web -c \"SELECT slug, pg_database, ativo FROM painel_bi_tenant\"", get_pty=True)
    i.write("oitapere\n")
    i.flush()
    o.channel.settimeout(60)
    print(o.read().decode("utf-8", errors="replace"))

    c.close()


if __name__ == "__main__":
    main()
