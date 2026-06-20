import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.100.12',username='oitamar',password='oitapere',timeout=20)
def run(cmd):
 _,o,e=c.exec_command(cmd,timeout=60); o.channel.settimeout(60); return (o.read()+e.read()).decode('utf-8','replace')
print('campo painel:', run('grep -c bi-url-login /opt/nfe-web/frontend/painel/index.html').strip())
print('http painel:', run('curl -s -o /dev/null -w "%{http_code}" -H "X-BI-Tenant-Slug: w-carlos" http://127.0.0.1:8000/').strip())
i,o,_=c.exec_command("sudo -S -u postgres psql -d sat1_sati_is -tAc 'SELECT COUNT(*) FROM c2910.conhecimento'",get_pty=True)
i.write('oitapere\n'); i.flush(); o.channel.settimeout(30)
print('c2910 ct-es:', ''.join(ch for ch in o.read().decode() if ch.isdigit()))
c.close()
