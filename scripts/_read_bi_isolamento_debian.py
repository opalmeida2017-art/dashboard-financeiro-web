"""Lê isolamento BI e nginx no Debian."""
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

    for cmd in [
        "head -25 /opt/nfe-web/deploy/provision_bi_tenant.py",
        "grep -rn biweb /etc/nginx/ 2>/dev/null | head -25",
        "ls -la /opt/biweb/tenants 2>/dev/null || echo sem_opt_biweb",
        "cat /opt/nfe-web/deploy/_bi_isolamento_brasil.py 2>/dev/null | head -120",
        "grep -rn SCRIPT_NAME\\|biweb\\|tenant.env /home/oitamar/dashboard-financeiro-web/app.py /home/oitamar/dashboard-financeiro-web/wsgi.py 2>/dev/null",
    ]:
        print(f"\n### {cmd[:70]}")
        print(run(c, cmd)[:6000])
    c.close()


if __name__ == "__main__":
    main()
