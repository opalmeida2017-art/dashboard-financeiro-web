import paramiko
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.100.12',username='oitamar',password='oitapere',timeout=20)
def sudo(sql):
 i,o,_=c.exec_command(f"sudo -S -u postgres psql -d sat1_sati_is -tAc \"{sql}\"",get_pty=True)
 i.write('oitapere\n'); i.flush(); return o.read().decode('utf-8','replace')
_,o,_=c.exec_command('grep -E "concluído|Traceback|data \\(3|conhecimento" /home/oitamar/dashboard-financeiro-web/restore_2pass.log | tail -10')
print(o.read().decode('utf-8','replace'))
print('ctes', sudo('SELECT COUNT(*) FROM c2910.conhecimento'))
print('http', end=' ')
_,o,_=c.exec_command('curl -s -o /dev/null -w "%{http_code}" -H "X-BI-Tenant-Slug: w-carlos" http://127.0.0.1:8000/')
print(o.read().decode())
c.close()
