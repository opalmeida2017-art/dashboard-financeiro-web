import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.100.12',username='oitamar',password='oitapere',timeout=20)
def sudo(cmd,t=60):
 i,o,_=c.exec_command('sudo -S '+cmd,get_pty=True); i.write('oitapere\n'); i.flush(); o.channel.settimeout(t); return o.read().decode('utf-8','replace')
print('LOG:\n',open_remote:=sudo('cat /tmp/expand_var_tmp_20g.log'))
print('fuser:', sudo('fuser -vm /home 2>&1 | head -30'))
print('mount:', sudo('mount | grep home'))
c.close()
