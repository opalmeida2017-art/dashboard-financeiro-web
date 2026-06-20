import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.100.12", username="oitamar", password="oitapere", timeout=25)


def run(cmd):
    _, o, e = c.exec_command(cmd, timeout=30)
    return (o.read() + e.read()).decode("utf-8", "replace")


print("=== logs chave ===")
print(
    run(
        "sudo -u postgres psql -d bi_w_carlos -c "
        "\"SELECT timestamp, left(mensagem,120) FROM tb_logs_robo "
        "WHERE mensagem LIKE '%Download salvo%' OR mensagem LIKE '%Restaurando%' "
        "OR mensagem LIKE '%Tenant%' ORDER BY id DESC LIMIT 8\""
    )
)

print("=== tabela cliente ===")
print(
    run(
        "sudo -u postgres psql -d bi_w_carlos -tAc "
        "\"SELECT to_regclass('c2910.cliente')\""
    )
)

print("=== count tabelas c2910 ===")
print(
    run(
        "sudo -u postgres psql -d bi_w_carlos -tAc "
        "\"SELECT count(*) FROM pg_tables WHERE schemaname='c2910'\""
    )
)

print("=== zip tenant ===")
print(run("ls -la /opt/biweb/tenants/w-carlos/downloads/1/*.zip 2>&1 | tail -3"))

c.close()
