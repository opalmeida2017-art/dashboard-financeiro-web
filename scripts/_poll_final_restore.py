import paramiko, time
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.100.12',username='oitamar',password='oitapere',timeout=20)
LOG='/home/oitamar/dashboard-financeiro-web/restore_final2.log'
for i in range(80):
 _,o,_=c.exec_command(f'tail -12 {LOG} 2>/dev/null; pgrep -af processar_arquivo_zip_sati || true',timeout=45)
 out=o.read().decode('utf-8','replace')
 print(f'---{i+1}---\n{out[-2500:]}')
 if 'Restore do schema SATI concluído' in out or 'RESTORE_OK' in out: break
 if 'Traceback' in out and 'sati_db_restore' in out: break
 time.sleep(30)
i,o,_=c.exec_command("sudo -S -u postgres psql -d sat1_sati_is -tAc \"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='c2910'\"",get_pty=True)
i.write('oitapere\n'); i.flush(); print('tabs',o.read().decode())
i,o,_=c.exec_command("sudo -S -u postgres psql -d sat1_sati_is -tAc 'SELECT COUNT(*) FROM c2910.conhecimento'",get_pty=True)
i.write('oitapere\n'); i.flush(); print('ctes',o.read().decode())
c.close()
