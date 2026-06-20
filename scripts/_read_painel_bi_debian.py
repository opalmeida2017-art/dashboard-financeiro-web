"""Lê código do painel BI no Debian (/opt/nfe-web)."""
import paramiko
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
APP = "/opt/nfe-web"


def run(c, cmd, t=60):
    _, o, e = c.exec_command(cmd, timeout=t)
    o.channel.settimeout(t)
    return (o.read() + e.read()).decode("utf-8", errors="replace")


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=20)

    files = [
        "bi_store.py",
        "bi_tenant_registry.py",
        "backend/app/routers/painel.py",
        "frontend/painel/painel.js",
    ]
    for f in files:
        print(f"\n{'='*60}\n### {f}\n{'='*60}")
        print(run(c, f"wc -l {APP}/{f} 2>/dev/null; head -5 {APP}/{f} 2>/dev/null"))

    print("\n=== grep criar bi ===")
    print(run(c, f"grep -rn 'criar.*bi\\|def criar' {APP}/bi_store.py {APP}/bi_tenant_registry.py {APP}/backend/app/routers/painel.py 2>/dev/null | head -40"))

    print("\n=== instancias BI ===")
    print(run(c, f"ls -la /home/oitamar/ 2>/dev/null | grep -i bi"))

    c.close()


if __name__ == "__main__":
    main()
