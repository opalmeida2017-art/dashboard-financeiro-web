"""Acha banco app com credenciais robô apt 11."""
import paramiko

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"


def run(c, cmd, t=30):
    _, o, e = c.exec_command(cmd, timeout=t)
    return (o.read() + e.read()).decode("utf-8", errors="replace")


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)

    print("=== DATABASE_URL global ===")
    print(
        run(
            c,
            "grep '^DATABASE_URL=' /home/oitamar/dashboard-financeiro-web/.env | "
            "sed 's/:\\([^:@]*\\)@/:***@/'",
        )
    )

    print("=== Bancos bi_* ===")
    print(run(c, "sudo -u postgres psql -tAc \"SELECT datname FROM pg_database WHERE datname LIKE 'bi_%' ORDER BY 1\""))

    for db in ("bi_w_carlos", "biweb", "dashboard_financeiro", "dashboard-financeiro"):
        print(f"\n=== configuracoes_robo em {db} ===")
        out = run(
            c,
            f"sudo -u postgres psql -d {db} -tAc "
            "\"SELECT chave, CASE WHEN chave LIKE '%SENHA%' THEN '***' "
            "ELSE left(valor,60) END FROM configuracoes_robo "
            "WHERE chave IN ('URL_LOGIN','USUARIO_ROBO','SENHA_ROBO') ORDER BY chave\" 2>&1",
        )
        print(out.strip() or "(vazio ou DB inexistente)")

    print("\n=== tenant .env w-carlos ===")
    print(
        run(
            c,
            "grep -E '^(URL_LOGIN|USUARIO_ROBO|SENHA_ROBO)=' "
            "/opt/biweb/tenants/w-carlos/.env 2>/dev/null | "
            "sed 's/\\(SENHA_ROBO=\\).*/\\1***/; s/\\(USUARIO_ROBO=\\).*/\\1***/' || echo sem",
        )
    )

    c.close()


if __name__ == "__main__":
    main()
