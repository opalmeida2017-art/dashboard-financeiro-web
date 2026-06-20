"""Diagnóstico + restore limpo w-carlos."""
import paramiko, sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
BI = "/home/oitamar/dashboard-financeiro-web"

def run(c,cmd,t=120):
 _,o,e=c.exec_command(cmd,timeout=t); o.channel.settimeout(t); return (o.read()+e.read()).decode('utf-8','replace')
def sudo(c,cmd,t=120):
 i,o,_=c.exec_command('sudo -S '+cmd,get_pty=True); i.write(PASS+'\n'); i.flush(); o.channel.settimeout(t); return o.read().decode('utf-8','replace')
def num(s):
 d=''.join(ch for ch in s if ch.isdigit()); return int(d) if d else 0

c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy()); c.connect(HOST,username=USER,password=PASS,timeout=20)
print('disco:', run(c,'df -h /var /tmp /home | tail -4'))
print('tabelas:', num(sudo(c,"-u postgres psql -d sat1_sati_is -tAc \"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='c2910'\"")))
print('conh:', num(sudo(c,"-u postgres psql -d sat1_sati_is -tAc 'SELECT COUNT(*) FROM c2910.conhecimento' 2>&1")))
print('log tail:', run(c,f'tail -8 {BI}/teste_import_w_carlos.log'))
c.close()
