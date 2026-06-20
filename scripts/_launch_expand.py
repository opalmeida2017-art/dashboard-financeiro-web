import paramiko, sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HOST,USER,PASS='192.168.100.12','oitamar','oitapere'
REMOTE='/tmp/expand_var_tmp_20g.sh'
LOG='/tmp/expand_var_tmp_20g.log'
SCRIPT=open(r'c:\python\BIWEB\scripts\_expand_disk_offline.sh',encoding='utf-8').read() if False else None

SCRIPT = r'''#!/bin/bash
set -e
exec >>/tmp/expand_var_tmp_20g.log 2>&1
echo "=== INICIO $(date) ==="
df -h /var /tmp /home
systemctl stop gunicorn 2>/dev/null || true
systemctl stop nginx 2>/dev/null || true
sync
sleep 2
fuser -km /home 2>/dev/null || true
sleep 3
umount /home
e2fsck -fy /dev/servidor-vg/home
resize2fs /dev/servidor-vg/home 52G
lvreduce -L 52G -y /dev/servidor-vg/home
lvextend -L 20G -r -y /dev/servidor-vg/var
lvextend -L 20G -r -y /dev/servidor-vg/tmp
mount /home
systemctl start nginx 2>/dev/null || true
systemctl start gunicorn 2>/dev/null || true
echo "=== FIM $(date) ==="
df -h /var /tmp /home
vgs servidor-vg; lvs servidor-vg
echo DISK_EXPAND_OK
'''

c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,username=USER,password=PASS,timeout=30)
sftp=c.open_sftp()
with sftp.open(REMOTE,'w') as f: f.write(SCRIPT)
sftp.close()
c.exec_command(f'chmod +x {REMOTE}')
time.sleep(1)
i,o,e=c.exec_command(f'sudo -S bash -c "nohup {REMOTE} &"', get_pty=True)
i.write(PASS+'\n'); i.flush(); i.channel.shutdown_write()
time.sleep(2)
print('launch:', o.read(2000).decode('utf-8','replace'))
c.close()
print('aguardando 90s...')
time.sleep(90)
c2=paramiko.SSHClient(); c2.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c2.connect(HOST,username=USER,password=PASS,timeout=30)
_,o,_=c2.exec_command(f'tail -30 {LOG}; echo ---; df -h /var /tmp /home')
print(o.read().decode('utf-8','replace'))
c2.close()
