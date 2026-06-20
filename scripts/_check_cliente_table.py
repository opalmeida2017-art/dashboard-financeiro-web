import paramiko
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.100.12',username='oitamar',password='oitapere',timeout=20)
def sudo(sql):
 i,o,_=c.exec_command(f"sudo -S -u postgres psql -d sat1_sati_is -c \"{sql}\"",get_pty=True)
 i.write('oitapere\n'); i.flush(); return o.read().decode('utf-8','replace')
print(sudo("SELECT table_name FROM information_schema.tables WHERE table_schema='c2910' AND table_name IN ('cliente','conhecimento','filial') ORDER BY 1"))
print(sudo("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='c2910'"))
_,o,_=c.exec_command('grep -i cliente /home/oitamar/dashboard-financeiro-web/restore_final2.log | head -5')
print(o.read().decode())
c.close()
