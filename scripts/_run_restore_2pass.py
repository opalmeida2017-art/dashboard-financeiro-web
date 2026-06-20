"""Deploy fluxo 2-pass pre-data e restore c2910."""
import sys, time, paramiko
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HOST,USER,PASS='192.168.100.12','oitamar','oitapere'
BI='/home/oitamar/dashboard-financeiro-web'
LOCAL=r'c:\python\BIWEB'
LOG=f'{BI}/restore_final2.log'

c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,username=USER,password=PASS,timeout=25)
sftp=c.open_sftp(); sftp.put(f'{LOCAL}\\sati_db_restore.py',f'{BI}/sati_db_restore.py'); sftp.close()
sftp=c.open_sftp(); sftp.put(f'{LOCAL}\\sati_db_restore.py',f'{BI}/sati_db_restore.py'); sftp.close()

def run(cmd,t=120):
 _,o,e=c.exec_command(cmd,timeout=t); o.channel.settimeout(t); return (o.read()+e.read()).decode('utf-8','replace')

run(f'pkill -f processar_arquivo_zip_sati || true; rm -f {BI}/data/sati_restore.lock; truncate -s 0 {LOG}')
run(f"cd {BI} && export $(grep -v '^#' .env | xargs) && nohup ./venv/bin/python -c \"from pathlib import Path; from sati_integration.robos from sati_integration.robos import sati_db_restore as s; s.processar_arquivo_zip_sati(Path('downloads/1/SATI-c2910-atual.zip'), apartamento_id=1)\" > {LOG} 2>&1 &",30)

ok=False
for i in range(90):
 time.sleep(25)
 tail=run(f'tail -18 {LOG}',40)
 print(f'---{i+1}---\n{tail[-2200:]}')
 if 'Restore do schema SATI concluído' in tail: ok=True; break
 if 'Traceback' in tail or 'pre-data incompleto' in tail: break

def sudo(cmd):
 i,o,_=c.exec_command('sudo -S '+cmd,get_pty=True); i.write(PASS+'\n'); i.flush(); o.channel.settimeout(60); return o.read().decode('utf-8','replace')
print('tabelas', sudo("-u postgres psql -d sat1_sati_is -tAc \"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='c2910'\""))
print('ctes', sudo("-u postgres psql -d sat1_sati_is -tAc 'SELECT COUNT(*) FROM c2910.conhecimento'"))
print('ok', ok)
c.close()
