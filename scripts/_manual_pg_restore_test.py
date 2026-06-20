"""Captura erros reais do pg_restore pre-data."""
import paramiko, sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HOST,USER,PASS='192.168.100.12','oitamar','oitapere'
BI='/home/oitamar/dashboard-financeiro-web'

REMOTE = r'''#!/bin/bash
set -e
export PATH=/usr/lib/postgresql/17/bin:$PATH
ZIP=/home/oitamar/dashboard-financeiro-web/downloads/1/SATI-c2910-atual.zip
TMP=/home/oitamar/tmp_sati/manual_restore
mkdir -p "$TMP"
cd "$TMP"
rm -f SATI-c2910.dump
unzip -qo "$ZIP" -d .
DUMP=$(ls *.dump | head -1)
cp "$DUMP" /var/tmp/sati_manual.dump
chmod 644 /var/tmp/sati_manual.dump

echo "=== domains public (amostra) ==="
sudo -u postgres psql -d sat1_sati_is -tAc "SELECT typname FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace WHERE n.nspname='public' AND t.typtype='d' ORDER BY 1 LIMIT 15"

echo "=== domains no dump c2910 ==="
sudo -u postgres pg_restore --list /var/tmp/sati_manual.dump 2>/dev/null | grep -i "DOMAIN" | head -15

echo "=== limpa c2910 ==="
sudo -u postgres psql -d sat1_sati_is -v ON_ERROR_STOP=1 -c "DROP SCHEMA IF EXISTS c2910 CASCADE"

echo "=== pre-data verbose (primeiros erros) ==="
sudo -u postgres pg_restore -d sat1_sati_is --no-owner --no-acl --section=pre-data /var/tmp/sati_manual.dump 2>&1 | head -60

echo "=== tabelas apos ==="
sudo -u postgres psql -d sat1_sati_is -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='c2910'"
'''

c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,username=USER,password=PASS,timeout=25)
sftp=c.open_sftp()
with sftp.open('/tmp/manual_pg_restore_test.sh','w') as f: f.write(REMOTE)
sftp.close()
i,o,e=c.exec_command('chmod +x /tmp/manual_pg_restore_test.sh && bash /tmp/manual_pg_restore_test.sh',timeout=300)
o.channel.settimeout(300)
print(o.read().decode('utf-8','replace'))
print(e.read().decode('utf-8','replace'))
c.close()
