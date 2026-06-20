import paramiko
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.100.12',username='oitamar',password='oitapere',timeout=20)
_,o,_=c.exec_command("grep -i 'cliente' /home/oitamar/dashboard-financeiro-web/restore_final2.log | grep -iE 'ERRO|error|already' | head -15",timeout=60)
print(o.read().decode('utf-8','replace'))
_,o,_=c.exec_command("grep -i 'TABLE c2910.cliente' /home/oitamar/dashboard-financeiro-web/restore_final2.log | head -5",timeout=60)
print(o.read().decode('utf-8','replace'))
c.close()
