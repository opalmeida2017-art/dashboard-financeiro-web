import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.100.12", username="oitamar", password="oitapere", timeout=25)
i,o,_=c.exec_command("sudo -S -u postgres psql -d nfe_web -c \"SELECT slug, apartamento_id, pg_database FROM painel_bi_tenant ORDER BY apartamento_id\"", get_pty=True)
i.write("oitapere\n"); i.flush()
print(o.read().decode())
for slug, apt in (("wcarlos", 1), ("rio-bonito", 2)):
    _,o,_=c.exec_command(f"grep BIWEB_TRANSPORTADORA_ID /opt/biweb/tenants/{slug}/tenant.env")
    print(f"{slug} env:", o.read().decode().strip())
    db = "bi_wcarlos" if slug == "wcarlos" else "bi_rio_bonito"
    i,o,_=c.exec_command(f"sudo -S -u postgres psql -d {db} -tAc \"SELECT id, nome_empresa FROM apartamentos\"", get_pty=True)
    i.write("oitapere\n"); i.flush()
    print(f"{slug} apartamentos:", o.read().decode().strip())
c.close()
