import paramiko
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.100.12',username='oitamar',password='oitapere',timeout=20)
def run(cmd):
 _,o,e=c.exec_command(cmd,timeout=30); return (o.read()+e.read()).decode('utf-8','replace')
secret=run("grep -E '^ADMIN_SECRET=' /opt/nfe-web/.env | head -1").split('=',1)[-1].strip().strip('"').strip("'")
print('remove fake:', run(f'curl -s -w "\\nHTTP %{{http_code}}" -X DELETE -H "X-Admin-Secret: {secret}" http://127.0.0.1:5000/api/painel/bi/tenants/slug-inexistente'))
print('import provision:', run(f'cd /opt/nfe-web && ./venv/bin/python -c "from deploy.provision_bi_tenant import remover_instancia_bi; print(\'ok\')"'))
i,o,_=c.exec_command("sudo -S -u postgres psql -d sat1_sati_is -tAc 'SELECT COUNT(*) FROM c2910.conhecimento'",get_pty=True)
i.write('oitapere\n'); i.flush(); print('ctes',o.read().decode())
i,o,_=c.exec_command("sudo -S -u postgres psql -d sat1_sati_is -tAc \"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='c2910' AND table_name='cliente')\"",get_pty=True)
i.write('oitapere\n'); i.flush(); print('cliente',o.read().decode())
c.close()
