import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.100.12',username='oitamar',password='oitapere',timeout=20)
_,o,e=c.exec_command('find /opt/nfe-web -path "*painel*" -name "*.html"',timeout=30)
print((o.read()+e.read()).decode())
