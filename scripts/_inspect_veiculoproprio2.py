import paramiko
for db, sch in [("bi_wcarlos","c2910"),("bi_rio_bonito","c3219")]:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect("192.168.100.12", username="oitamar", password="oitapere", timeout=25)
    _, o, e = c.exec_command(f"sudo -u postgres psql -d {db} -c \"SELECT veiculoproprio, count(*) FROM {sch}.veiculo GROUP BY 1 ORDER BY 2 DESC\"", timeout=30)
    print(f"=== {db} ===")
    print((o.read()+e.read()).decode())
    c.close()
