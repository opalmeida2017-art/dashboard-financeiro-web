import paramiko, sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HOST,USER,PASS='192.168.100.12','oitamar','oitapere'

RESIZE_SH = r'''#!/bin/bash
set -e
exec >> /var/log/resize-home-lv.log 2>&1
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
'''

UNIT = r'''[Unit]
Description=Shrink home LV and expand var/tmp (one-shot before mount)
DefaultDependencies=no
Before=local-fs-pre.target
After=systemd-remount-fs.service
ConditionPathExists=/root/do_resize_home_once

[Service]
Type=oneshot
ExecStart=/root/resize_home_lv.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
'''

c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,username=USER,password=PASS,timeout=30)
sftp=c.open_sftp()
with sftp.open('/tmp/resize_home_lv.sh','w') as f: f.write(RESIZE_SH)
with sftp.open('/tmp/resize-home-lv.service','w') as f: f.write(UNIT)
sftp.close()

def sudo(cmd,t=60):
 i,o,_=c.exec_command('sudo -S '+cmd,get_pty=True); i.write(PASS+'\n'); i.flush(); o.channel.settimeout(t); return o.read().decode('utf-8','replace')

sudo('cp /tmp/resize_home_lv.sh /root/resize_home_lv.sh')
sudo('chmod +x /root/resize_home_lv.sh')
sudo('cp /tmp/resize-home-lv.service /etc/systemd/system/resize-home-lv.service')
sudo('touch /root/do_resize_home_once')
sudo('systemctl daemon-reload')
sudo('systemctl enable resize-home-lv.service')
print('Serviço de boot instalado. Reiniciando servidor em 5s...')
sudo('bash -c "sleep 5 && reboot"', t=15)
c.close()
print('Reboot enviado. Aguardando servidor voltar (~2 min)...')
time.sleep(120)
for i in range(20):
    time.sleep(15)
    try:
        c2=paramiko.SSHClient(); c2.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c2.connect(HOST,username=USER,password=PASS,timeout=15)
        _,o,_=c2.exec_command('df -h /var /tmp /home; echo ---; sudo cat /var/log/resize-home-lv.log 2>/dev/null | tail -20')
        i2,o2,e2=c2.exec_command('sudo -S cat /var/log/resize-home-lv.log',get_pty=True)
        i2.write(PASS+'\n'); i2.flush()
        print(f'\n=== tentativa {i+1} ===\n'+o2.read().decode('utf-8','replace')+o.read().decode('utf-8','replace'))
        out=o.read().decode('utf-8','replace')
        if '20G' in out or '20G' in o2.read().decode('utf-8','replace'):
            pass
        c2.close()
        if '20G' in out:
            break
    except Exception as e:
        print(f'aguardando... ({e})')
