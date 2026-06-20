"""Extrai trechos relevantes do provisionamento BI no Debian."""
import paramiko
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
APP = "/opt/nfe-web"


def run(c, cmd, t=90):
    _, o, e = c.exec_command(cmd, timeout=t)
    o.channel.settimeout(t)
    return (o.read() + e.read()).decode("utf-8", errors="replace")


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=20)

    for path in [
        "deploy/provision_bi_tenant.py",
        "bi_store.py",
        "bi_tenant_registry.py",
    ]:
        print(f"\n### FILE {path}")
        print(run(c, f"cat {APP}/{path}"))

    print("\n### painel.py bi routes")
    print(run(c, f"sed -n '180,274p' {APP}/backend/app/routers/painel.py"))

    print("\n### painel.js bi section")
    print(run(c, f"grep -n 'bi\\|BI' {APP}/frontend/painel/painel.js | head -60"))

    print("\n### bi instances dirs")
    print(run(c, "find /home/oitamar -maxdepth 2 -name '.env' 2>/dev/null | head -20"))
    print(run(c, "grep -l 'SATI_DATABASE_URL' /home/oitamar/*/.env /home/oitamar/*/*/.env 2>/dev/null | head -10"))

    c.close()


if __name__ == "__main__":
    main()
