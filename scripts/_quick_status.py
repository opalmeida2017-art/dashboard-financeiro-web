import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.100.12", username="oitamar", password="oitapere", timeout=15)

def sudo(sql):
    i, o, _ = c.exec_command(f"sudo -S -u postgres psql -d sat1_sati_is -tAc \"{sql}\"", get_pty=True)
    i.write("oitapere\n")
    i.flush()
    return o.read().decode("utf-8", "replace").strip().split()[-1] if True else ""

_, o, _ = c.exec_command("df -h /var /tmp /home | tail -3")
print("DISCO:\n" + o.read().decode())
print("CTES:", sudo("SELECT COUNT(*) FROM c2910.conhecimento"))
print("TABELAS:", sudo("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='c2910'"))
_, o, _ = c.exec_command('curl -s -o /dev/null -w "%{http_code}" -H "X-BI-Tenant-Slug: w-carlos" http://127.0.0.1:8000/')
print("HTTP w-carlos:", o.read().decode().strip())
_, o, _ = c.exec_command('cd /opt/nfe-web && ./venv/bin/python -c "from deploy.provision_bi_tenant import remover_instancia_bi; print(\'API_OK\')" 2>&1')
print(o.read().decode().strip())
c.close()
