"""Verifica patches BI aplicados no servidor."""
import paramiko
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
BI = "/home/oitamar/dashboard-financeiro-web"


def run(c, cmd, t=90):
    _, o, e = c.exec_command(cmd, timeout=t)
    o.channel.settimeout(t)
    return (o.read() + e.read()).decode("utf-8", errors="replace")


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=20)

    checks = [
        f"grep -n biweb_switch_tenant {BI}/app.py",
        f"grep -n switch_engine_for_request {BI}/database.py",
        f"grep -n try_auto_login_por_slug {BI}/tenant.py",
        f"grep -n URL_LOGIN {BI}/sati_source.py | head -5",
        f"grep -n tenant_downloads {BI}/robos/base_robo.py {BI}/biweb_paths.py 2>/dev/null",
        f"grep -n url_login {BI}/../opt/nfe-web/frontend/painel/painel.js 2>/dev/null; grep -n url_login /opt/nfe-web/frontend/painel/painel.js",
        f"sudo -u postgres psql -d bi_w_carlos -c \"SELECT chave, left(valor,50) FROM configuracoes_robo ORDER BY chave\"",
        f"sudo -u postgres psql -d bi_w_carlos -c \"SELECT id, nome_empresa, slug FROM apartamentos\"",
    ]
    for cmd in checks:
        print(f"\n### {cmd[:75]}")
        if cmd.startswith("sudo"):
            i, o, _ = c.exec_command(f"sudo -S {cmd[5:]}", get_pty=True)
            i.write(PASS + "\n")
            i.flush()
            o.channel.settimeout(60)
            print(o.read().decode("utf-8", errors="replace"))
        else:
            print(run(c, cmd))
    c.close()


if __name__ == "__main__":
    main()
