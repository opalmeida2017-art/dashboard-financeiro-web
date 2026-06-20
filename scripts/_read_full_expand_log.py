import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.100.12',username='oitamar',password='oitapere',timeout=20)
i,o,_=c.exec_command('sudo -S cat /tmp/expand_var_tmp_20g.log',get_pty=True)
i.write('oitapere\n'); i.flush(); o.channel.settimeout(60)
print(o.read().decode('utf-8','replace'))
c.close()
