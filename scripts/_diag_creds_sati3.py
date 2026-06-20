import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.100.12", username="oitamar", password="oitapere", timeout=25)


def run(cmd):
    _, o, e = c.exec_command(cmd, timeout=30)
    return (o.read() + e.read()).decode("utf-8", "replace")


print("=== dashboard_db configuracoes_robo ===")
print(
    run(
        "sudo -u postgres psql -d dashboard_db -c "
        "\"SELECT apartamento_id, chave, "
        "CASE WHEN chave LIKE '%SENHA%' THEN '***' ELSE left(valor,50) END AS valor "
        "FROM configuracoes_robo "
        "WHERE chave IN ('URL_LOGIN','USUARIO_ROBO','SENHA_ROBO') "
        "ORDER BY apartamento_id, chave\""
    )
)

print("=== bi_transportes_brasil_ltda ===")
print(
    run(
        "sudo -u postgres psql -d bi_transportes_brasil_ltda -c "
        "\"SELECT chave, CASE WHEN chave LIKE '%SENHA%' THEN '***' ELSE left(valor,50) END "
        "FROM configuracoes_robo WHERE chave IN ('URL_LOGIN','USUARIO_ROBO','SENHA_ROBO')\""
    )
)

c.close()
