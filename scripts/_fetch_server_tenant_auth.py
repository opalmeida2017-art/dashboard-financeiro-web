import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.100.12',username='oitamar',password='oitapere',timeout=20)
BI='/home/oitamar/dashboard-financeiro-web'
def run(cmd):
 _,o,e=c.exec_command(cmd,timeout=90); o.channel.settimeout(90); return (o.read()+e.read()).decode('utf-8','replace')
print(run('sed -n "170,215p" '+BI+'/app.py'))
print('---tenant---')
print(run('sed -n "165,230p" '+BI+'/tenant.py'))
print('---auth---')
print(run('cat '+BI+'/blueprints/auth.py'))
print('---sati_schema---')
print(run('sed -n "78,125p" '+BI+'/sati_source.py'))
