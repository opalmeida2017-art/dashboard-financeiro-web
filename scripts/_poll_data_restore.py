import paramiko, time
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.100.12',username='oitamar',password='oitapere',timeout=20)
for i in range(40):
 _,o,_=c.exec_command('tail -5 /home/oitamar/dashboard-financeiro-web/restore_data_only.log 2>/dev/null; pgrep -af finish_restore || true',timeout=30)
 out=o.read().decode('utf-8','replace')
 print(f'---{i+1}---',out)
 if 'RESTORE_OK' in out or 'concluído' in out: break
 if 'Traceback' in out and 'restore_data' in out: break
 time.sleep(30)
i,o,_=c.exec_command("sudo -S -u postgres psql -d sat1_sati_is -tAc 'SELECT COUNT(*) FROM c2910.conhecimento'",get_pty=True)
i.write('oitapere\n'); i.flush(); print('ctes',o.read().decode())
c.close()
