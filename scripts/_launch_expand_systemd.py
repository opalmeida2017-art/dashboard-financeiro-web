import paramiko, sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HOST,USER,PASS='192.168.100.12','oitamar','oitapere'

SCRIPT = r'''#!/bin/bash
set -x
exec > /tmp/expand_var_tmp_20g.log 2>&1
echo "=== INICIO $(date) ==="
df -h /var /tmp /home

systemctl stop gunicorn nginx cloudflared 2>/dev/null || true
loginctl terminate-user oitamar 2>/dev/null || true
sleep 3
fuser -km /home 2>/dev/null || true
sleep 5

umount /home

e2fsck -fy /dev/servidor-vg/home
resize2fs /dev/servidor-vg/home 52G
lvreduce -L 52G -y /dev/servidor-vg/home
lvextend -L 20G -r -y /dev/servidor-vg/var
lvextend -L 20G -r -y /dev/servidor-vg/tmp
mount /home

systemctl start nginx gunicorn cloudflared 2>/dev/null || true
echo "=== FIM $(date) ==="
df -h /var /tmp /home
vgs servidor-vg; lvs servidor-vg
echo DISK_EXPAND_OK
'''

UNIT = r'''[Unit]
Description=Expand var and tmp to 20G
After=network.target

[Service]
Type=oneshot
ExecStart=/tmp/expand_var_tmp_20g.sh
RemainAfterExit=no
'''

c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,username=USER,password=PASS,timeout=30)
sftp=c.open_sftp()
with sftp.open('/tmp/expand_var_tmp_20g.sh','w') as f: f.write(SCRIPT)
with sftp.open('/tmp/expand-var-tmp.service','w') as f: f.write(UNIT)
sftp.close()

def sudo(cmd,t=30):
 i,o,_=c.exec_command('sudo -S '+cmd,get_pty=True); i.write(PASS+'\n'); i.flush(); o.channel.settimeout(t); return o.read().decode('utf-8','replace')

sudo('chmod +x /tmp/expand_var_tmp_20g.sh')
sudo('cp /tmp/expand-var-tmp.service /etc/systemd/system/expand-var-tmp.service')
sudo('systemctl daemon-reload')
print(sudo('systemctl start expand-var-tmp.service',t=10))
print('agendado via systemd — aguardando...')
c.close()

for sec in [45, 60, 90, 120, 180]:
    time.sleep(sec if sec==45 else sec-45 if False else 45)
    try:
        c2=paramiko.SSHClient(); c2.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c2.connect(HOST,username=USER,password=PASS,timeout=30)
        _,o,_=c2.exec_command('tail -25 /tmp/expand_var_tmp_20g.log; echo ---; df -h /var /tmp /home; systemctl is-failed expand-var-tmp.service 2>/dev/null')
        print(f'\n=== poll {sec}s ===\n'+o.read().decode('utf-8','replace'))
        c2.close()
    except Exception as e:
        print('reconexão:', e)
