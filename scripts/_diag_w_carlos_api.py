"""Diagnóstico w-carlos: API remove, logs, estado banco/schema."""
import paramiko
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
NFE = "/opt/nfe-web"
BI = "/home/oitamar/dashboard-financeiro-web"


def run(c, cmd, t=90):
    _, o, e = c.exec_command(cmd, timeout=t)
    o.channel.settimeout(t)
    return (o.read() + e.read()).decode("utf-8", "replace")


def sudo(c, cmd, t=90):
    i, o, _ = c.exec_command(f"sudo -S {cmd}", get_pty=True)
    i.write(PASS + "\n")
    i.flush()
    o.channel.settimeout(t)
    return o.read().decode("utf-8", "replace")


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)

    print("=== provision_bi_tenant.py (head) ===")
    print(run(c, f"head -40 {NFE}/deploy/provision_bi_tenant.py"))

    print("\n=== nfe-web logs (500/remove) ===")
    print(sudo(c, "journalctl -u nfe-web --no-pager -n 80 2>/dev/null | tail -50"))

    print("\n=== painel_bi_tenant w-carlos ===")
    print(
        sudo(
            c,
            "-u postgres psql -d nfe_web -c "
            "\"SELECT slug, pg_database, url, ativo FROM painel_bi_tenant WHERE slug ILIKE '%carlos%'\"",
        )
    )

    print("\n=== bi_w_carlos config ===")
    print(
        sudo(
            c,
            "-u postgres psql -d bi_w_carlos -c "
            "\"SELECT chave, left(valor,80) FROM configuracoes_robo ORDER BY chave\" 2>&1",
        )
    )

    print("\n=== schema c2910 ===")
    print(
        sudo(
            c,
            "-u postgres psql -d sat1_sati_is -tAc "
            "\"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='c2910'\" 2>&1",
        )
    )
    print(
        sudo(
            c,
            "-u postgres psql -d sat1_sati_is -tAc "
            "'SELECT COUNT(*) FROM c2910.conhecimento' 2>&1",
        )
    )

    print("\n=== tenant dir ===")
    print(run(c, "ls -la /opt/biweb/tenants/w-carlos/ 2>&1; cat /opt/biweb/tenants/w-carlos/tenant.env 2>&1"))

    print("\n=== test DELETE API (dry) ===")
    secret = run(c, f"grep -E '^ADMIN_SECRET=' {NFE}/.env 2>/dev/null | head -1").strip()
    if secret:
        key = secret.split("=", 1)[1].strip().strip('"').strip("'")
        print(
            run(
                c,
                f'curl -s -w "\\nHTTP %{{http_code}}" -X DELETE '
                f'-H "X-Admin-Secret: {key}" '
                f'"http://127.0.0.1:5000/api/painel/bi/tenants/w-carlos-test-fake" 2>&1 | tail -5',
            )
        )

    c.close()


if __name__ == "__main__":
    main()
