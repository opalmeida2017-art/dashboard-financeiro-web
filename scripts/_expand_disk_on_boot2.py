import paramiko, sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HOST,USER,PASS='192.168.100.12','oitamar','oitapere'

RESIZE_SH = r'''#!/bin/bash
set -e
LOG=/tmp/resize-home-lv.log
exec >> "$LOG" 2>&1
echo "=== resize boot $(date) ==="
if [ ! -f /root/do_resize_home_once ]; then
  echo "flag ausente, saindo"
  exit 0
fi

e2fsck -fy /dev/servidor-vg/home
resize2fs /dev/servidor-vg/home 52G
lvreduce -L 52G -y /dev/servidor-vg/home
lvextend -L 20G -r -y /dev/servidor-vg/var
lvextend -L 20G -r -y /dev/servidor-vg/tmp
rm -f /root/do_resize_home_once
echo "=== resize OK $(date) ==="
df -h /dev/mapper/servidor--vg-var /dev/mapper/servidor--vg-tmp /dev/mapper/servidor--vg-home 2>/dev/null || true
lvs servidor-vg
'''

c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,username=USER,password=PASS,timeout=30)
sftp=c.open_sftp()
with sftp.open('/tmp/resize_home_lv.sh','w') as f: f.write(RESIZE_SH)
sftp.close()

def sudo(cmd,t=60):
 i,o,_=c.exec_command('sudo -S '+cmd,get_pty=True); i.write(PASS+'\n'); i.flush(); o.channel.settimeout(t); return o.read().decode('utf-8','replace')

sudo('cp /tmp/resize_home_lv.sh /root/resize_home_lv.sh')
sudo('chmod +x /root/resize_home_lv.sh')
sudo('touch /root/do_resize_home_once')
print('reboot...')
sudo('reboot', t=10)
c.close()

print('aguardando reboot 2min...')
time.sleep(120)
for i in range(15):
    time.sleep(12)
    try:
        c2=paramiko.SSHClient(); c2.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c2.connect(HOST,username=USER,password=PASS,timeout=15)
        _,o,_=c2.exec_command('df -h /var /tmp /home; echo ---LOG---; cat /tmp/resize-home-lv.log 2>/dev/null')
        out=o.read().decode('utf-8','replace')
        print(f'\n=== {i+1} ===\n{out}')
        c2.close()
        if 'resize OK' in out or ' 20G ' in out:
            break
    except Exception as e:
        print('aguardando', e)
