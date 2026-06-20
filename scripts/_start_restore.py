import paramiko
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.100.12',username='oitamar',password='oitapere',timeout=20)
BI='/home/oitamar/dashboard-financeiro-web'
cmd=f"pkill -f processar_arquivo_zip_sati || true; rm -f {BI}/data/sati_restore.lock; truncate -s 0 {BI}/restore_final2.log; cd {BI} && export $(grep -v '^#' .env | xargs) && nohup ./venv/bin/python -c \"from pathlib import Path; from sati_integration.robos from sati_integration.robos import sati_db_restore as s; s.processar_arquivo_zip_sati(Path('downloads/1/SATI-c2910-atual.zip'), apartamento_id=1)\" > {BI}/restore_final2.log 2>&1 < /dev/null &"
_,o,e=c.exec_command(cmd,timeout=10)
o.channel.settimeout(5)
try: print(o.read().decode())
except: print('started')
c.close()
