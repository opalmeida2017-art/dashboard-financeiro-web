"""Completa restore: data + post-data (pre-data já OK com ~494 tabelas)."""
import sys, time, paramiko
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HOST,USER,PASS='192.168.100.12','oitamar','oitapere'
BI='/home/oitamar/dashboard-financeiro-web'
LOCAL=r'c:\python\BIWEB'
LOG=f'{BI}/restore_data_only.log'

REMOTE=r'''
import os
from pathlib import Path
os.chdir(%r)
for line in open(".env"):
    line=line.strip()
    if line and not line.startswith("#") and "=" in line:
        k,v=line.split("=",1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
from sati_integration.robos from sati_integration.robos import sati_db_restore as sr
pg=sr._parse_pg_url(os.environ["SATI_DATABASE_URL"])
pg_restore=sr._find_pg_restore()
usar=sr._usar_postgres_sudo()
z=Path("downloads/1/SATI-c2910-atual.zip")
tmp=sr._tmpdir_restore()/ "finish_restore"
tmp.mkdir(parents=True, exist_ok=True)
dump=sr.extrair_zip_dump(z, tmp/"x")
dr=sr._dump_path_para_restore(dump, usar, 1)
for sec,label,ob in [("data","data (3/4)",True),("post-data","post-data (4/4)",False)]:
    sr._executar_pg_restore(pg_restore, pg, dr, ["--section="+sec], label, 1, usar, obrigatorio=ob)
sr._conceder_schema_usuario_app(os.environ["SATI_DATABASE_URL"], "c2910", pg["user"], 1, pg, usar)
sr._verificar_tabelas_apos_restore(1, "c2910")
print("RESTORE_OK")
''' % BI

c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,username=USER,password=PASS,timeout=25)
sftp=c.open_sftp()
sftp.put(f'{LOCAL}\\sati_db_restore.py',f'{BI}/sati_db_restore.py')
with sftp.open(f'{BI}/finish_restore_data.py','w') as f: f.write(REMOTE)
sftp.close()

def run(cmd,t=120):
 _,o,e=c.exec_command(cmd,timeout=t); o.channel.settimeout(t); return (o.read()+e.read()).decode('utf-8','replace')

run(f'truncate -s 0 {LOG}')
run(f'cd {BI} && nohup ./venv/bin/python finish_restore_data.py > {LOG} 2>&1 &',20)
for i in range(120):
 time.sleep(30)
 tail=run(f'tail -8 {LOG}',40)
 print(f'---{i+1}---\n{tail}')
 if 'RESTORE_OK' in tail or 'concluído' in tail: break
 if 'Traceback' in tail: break

def sudo(cmd):
 i,o,_=c.exec_command('sudo -S '+cmd,get_pty=True); i.write(PASS+'\n'); i.flush(); o.channel.settimeout(60); return o.read().decode('utf-8','replace')
print('ctes', sudo("psql -d sat1_sati_is -tAc 'SELECT COUNT(*) FROM c2910.conhecimento'"))
c.close()
