import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
REMOTE = r'''#!/bin/bash
export PATH=/usr/lib/postgresql/17/bin:$PATH
cd /home/oitamar/dashboard-financeiro-web
./venv/bin/python -c "
import zipfile
from pathlib import Path
z=Path('downloads/1/SATI-c2910-atual.zip')
out=Path('/var/tmp/sati_manual.dump')
with zipfile.ZipFile(z) as zf:
    name=[n for n in zf.namelist() if n.endswith('.dump')][0]
    out.write_bytes(zf.read(name))
print('dump bytes', out.stat().st_size)
"
chmod 644 /var/tmp/sati_manual.dump
sudo -u postgres psql -d sat1_sati_is -c "DROP SCHEMA IF EXISTS c2910 CASCADE"
echo "=== DOMAIN sample in dump ==="
sudo -u postgres pg_restore --list /var/tmp/sati_manual.dump 2>/dev/null | grep -i DOMAIN | head -10
echo "=== PRE-DATA errors ==="
sudo -u postgres pg_restore -d sat1_sati_is --no-owner --no-acl --section=pre-data /var/tmp/sati_manual.dump 2>&1 | head -50
echo "=== TABLES ==="
sudo -u postgres psql -d sat1_sati_is -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='c2910'"
'''
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.100.12',username='oitamar',password='oitapere',timeout=25)
sftp=c.open_sftp()
with sftp.open('/tmp/manual_pg_restore_test2.sh','w') as f: f.write(REMOTE)
sftp.close()
_,o,e=c.exec_command('bash /tmp/manual_pg_restore_test2.sh',timeout=300)
o.channel.settimeout(300)
print(o.read().decode('utf-8','replace'))
print(e.read().decode('utf-8','replace'))
c.close()
