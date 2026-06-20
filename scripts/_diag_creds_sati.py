"""Diagnóstico credenciais SATI no Debian (sem expor senha)."""
import paramiko

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"


def run(c, cmd, t=30):
    _, o, e = c.exec_command(cmd, timeout=t)
    return (o.read() + e.read()).decode("utf-8", errors="replace")


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)

    print("=== .env global (chaves robô) ===")
    print(
        run(
            c,
            "grep -E '^(URL_LOGIN|USUARIO_ROBO|SENHA_ROBO)=' "
            "/home/oitamar/dashboard-financeiro-web/.env | "
            "sed 's/\\(SENHA_ROBO=\\).*/\\1***/; s/\\(USUARIO_ROBO=\\).*/\\1***/'",
        )
    )

    print("=== configuracoes_robo bi_w_carlos ===")
    print(
        run(
            c,
            'sudo -u postgres psql -d bi_w_carlos -tAc '
            '"SELECT chave, CASE WHEN chave LIKE \'%SENHA%\' THEN \'***\' '
            "ELSE left(valor,70) END FROM configuracoes_robo ORDER BY chave\"",
        )
    )

    print("=== configuracoes_robo sat1_sati_is apt 11 ===")
    print(
        run(
            c,
            'sudo -u postgres psql -d sat1_sati_is -tAc '
            '"SELECT chave, CASE WHEN chave LIKE \'%SENHA%\' THEN \'***\' '
            "ELSE left(valor,70) END FROM configuracoes_robo "
            "WHERE apartamento_id=11 ORDER BY chave\"",
        )
    )

    print("=== configuracoes_robo sat1_sati_is qualquer apt ===")
    print(
        run(
            c,
            'sudo -u postgres psql -d sat1_sati_is -tAc '
            '"SELECT apartamento_id, chave FROM configuracoes_robo '
            "WHERE chave IN ('URL_LOGIN','USUARIO_ROBO','SENHA_ROBO') "
            'ORDER BY apartamento_id, chave"',
        )
    )

    c.close()


if __name__ == "__main__":
    main()
