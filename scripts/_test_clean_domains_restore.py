import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PASS='oitapere'
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.100.12',username='oitamar',password='oitapere',timeout=25)

def sudo(cmd,t=300):
 i,o,_=c.exec_command('sudo -S '+cmd,get_pty=True); i.write(PASS+'\n'); i.flush(); o.channel.settimeout(t); return o.read().decode('utf-8','replace')

print('log head:')
i,o,_=c.exec_command('head -40 /home/oitamar/dashboard-financeiro-web/restore_w_carlos_final.log',timeout=60)
print(o.read().decode('utf-8','replace'))

SH='''#!/bin/bash
export PATH=/usr/lib/postgresql/17/bin:$PATH
sudo -u postgres psql -d sat1_sati_is -v ON_ERROR_STOP=1 <<'SQL'
DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT t.typname AS n FROM pg_type t
    JOIN pg_namespace ns ON ns.oid = t.typnamespace
    WHERE ns.nspname = 'public' AND t.typtype = 'd' AND t.typname LIKE 'dom_%'
  LOOP
    EXECUTE format('DROP DOMAIN IF EXISTS public.%I CASCADE', r.n);
  END LOOP;
END $$;
DROP SCHEMA IF EXISTS c2910 CASCADE;
SQL
echo doms: $(sudo -u postgres psql -d sat1_sati_is -tAc "SELECT COUNT(*) FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace WHERE n.nspname='public' AND t.typtype='d'")
sudo -n -u postgres pg_restore -d sat1_sati_is --no-owner --no-acl --section=pre-data /var/tmp/sati_manual.dump > /tmp/pg_out.txt 2>&1 || true
head -20 /tmp/pg_out.txt
echo ...
tail -5 /tmp/pg_out.txt
echo tables: $(sudo -n -u postgres psql -d sat1_sati_is -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='c2910'")
'''
sftp=c.open_sftp()
with sftp.open('/tmp/pg_clean_test.sh','w') as f: f.write(SH)
sftp.close()
print('\n=== clean + pre-data test ===')
print(sudo('bash /tmp/pg_clean_test.sh',t=300))
c.close()
