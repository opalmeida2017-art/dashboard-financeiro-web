import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
SH = r'''#!/bin/bash
export PATH=/usr/lib/postgresql/17/bin:$PATH
echo "test sudo -n:" $(sudo -n -u postgres whoami 2>&1)
sudo -n -u postgres psql -d sat1_sati_is -c "DROP SCHEMA IF EXISTS c2910 CASCADE" 2>&1 | tail -3
echo "=== pre-data ==="
sudo -n -u postgres pg_restore -d sat1_sati_is --no-owner --no-acl --section=pre-data /var/tmp/sati_manual.dump 2>&1 | head -25
echo "tables:" $(sudo -n -u postgres psql -d sat1_sati_is -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='c2910'")
'''
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.100.12',username='oitamar',password='oitapere',timeout=25)
sftp=c.open_sftp()
with sftp.open('/tmp/pg_pre2.sh','w') as f: f.write(SH)
sftp.close()
_,o,_=c.exec_command('bash /tmp/pg_pre2.sh',timeout=300)
o.channel.settimeout(300)
print(o.read().decode('utf-8','replace'))
c.close()
