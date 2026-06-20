import paramiko
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.100.12',username='oitamar',password='oitapere',timeout=20)
_,o,_=c.exec_command('tail -35 /home/oitamar/dashboard-financeiro-web/restore_2pass.log',timeout=60)
print(o.read().decode('utf-8','replace'))
i,o,_=c.exec_command("sudo -S -u postgres psql -d sat1_sati_is -tAc \"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='c2910'\"",get_pty=True)
i.write('oitapere\n'); i.flush()
print('tabs', o.read().decode('utf-8','replace'))
c.close()
