import paramiko
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.100.12',username='oitamar',password='oitapere',timeout=20)
i,o,_=c.exec_command("sudo -S -u postgres psql -d sat1_sati_is -c \"SELECT table_name FROM information_schema.tables WHERE table_schema='c2910' AND table_name ILIKE '%cliente%' ORDER BY 1\"",get_pty=True)
i.write('oitapere\n'); i.flush(); print(o.read().decode())
_,o,_=c.exec_command('sudo -n -u postgres pg_restore --list /var/tmp/sati_manual.dump 2>/dev/null | grep -i "TABLE.*cliente" | head -10',timeout=60)
print(o.read().decode())
c.close()
