"""Diagnóstico pg_restore c2910."""
import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HOST,USER,PASS='192.168.100.12','oitamar','oitapere'
BI='/home/oitamar/dashboard-financeiro-web'

c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,username=USER,password=PASS,timeout=25)

def run(cmd,t=120):
 _,o,e=c.exec_command(cmd,timeout=t); o.channel.settimeout(t); return (o.read()+e.read()).decode('utf-8','replace')
def sudo(cmd,t=120):
 i,o,_=c.exec_command('sudo -S '+cmd,get_pty=True); i.write(PASS+'\n'); i.flush(); o.channel.settimeout(t); return o.read().decode('utf-8','replace')

cmds=[
 f'head -80 {BI}/restore_w_carlos_fix.log',
 f'grep -E "pg_restore|ERRO|error|already exists|dom_" {BI}/restore_w_carlos_fix.log | head -40',
 'grep SATI_RESTORE /home/oitamar/dashboard-financeiro-web/.env',
 'sudo -n -u postgres psql -d sat1_sati_is -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=\'c2910\'"',
 'sudo -n -u postgres psql -d sat1_sati_is -tAc "SELECT COUNT(*) FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace WHERE n.nspname=\'public\' AND t.typtype=\'d\'"',
 'sudo -n -u postgres psql -d sat1_sati_is -tAc "SELECT nspname FROM pg_namespace WHERE nspname LIKE \'c%\' ORDER BY 1"',
 'ls -lh /home/oitamar/dashboard-financeiro-web/downloads/1/SATI-c2910-atual.zip',
]
for cmd in cmds:
 print('\n===',cmd,'===')
 if cmd.startswith('sudo -n'):
  print(run(cmd))
 else:
  print(sudo(cmd) if 'sudo' in cmd else run(cmd))
c.close()
