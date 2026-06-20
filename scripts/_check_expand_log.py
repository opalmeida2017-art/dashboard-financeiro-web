import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.100.12',username='oitamar',password='oitapere',timeout=20)
for cmd in ['cat /tmp/expand_var_tmp_20g.log 2>/dev/null | tail -40','df -h /var /tmp /home','sudo lvs 2>&1 | head -20']:
 i,o,e=c.exec_command(cmd); print('===',cmd,'==='); print(o.read().decode('utf-8','replace'))
c.close()
