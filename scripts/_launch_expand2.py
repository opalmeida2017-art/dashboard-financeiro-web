import paramiko, sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HOST,USER,PASS='192.168.100.12','oitamar','oitapere'
REMOTE='/tmp/expand_var_tmp_20g.sh'
LOG='/tmp/expand_var_tmp_20g.log'

SCRIPT = r'''#!/bin/bash
set -e
exec > /tmp/expand_var_tmp_20g.log 2>&1
echo "=== INICIO $(date) ==="
df -h /var /tmp /home

systemctl stop gunicorn nginx 2>/dev/null || true
systemctl stop cloudflared 2>/dev/null || true
systemctl stop 'user@1000' 2>/dev/null || true

sync
sleep 2

# Encerra processos do usuário que seguram /home (script roda como root)
pkill -9 -u oitamar 2>/dev/null || true
fuser -km /home 2>/dev/null || true
sleep 5

if mountpoint -q /home; then
  umount /home || umount -f /home
fi
sleep 1

if mountpoint -q /home; then
  echo "ERRO: /home ainda montado"; mount | grep home; fuser -vm /home; exit 1
fi

e2fsck -fy /dev/servidor-vg/home
resize2fs /dev/servidor-vg/home 52G
lvreduce -L 52G -y /dev/servidor-vg/home

lvextend -L 20G -r -y /dev/servidor-vg/var
lvextend -L 20G -r -y /dev/servidor-vg/tmp

mount /home
systemctl start nginx gunicorn cloudflared 2>/dev/null || true
systemctl start 'user@1000' 2>/dev/null || true

echo "=== FIM $(date) ==="
df -h /var /tmp /home
vgs servidor-vg
lvs servidor-vg
echo DISK_EXPAND_OK
'''

c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,username=USER,password=PASS,timeout=30)
sftp=c.open_sftp()
with sftp.open(REMOTE,'w') as f: f.write(SCRIPT)
sftp.close()
c.exec_command(f'chmod +x {REMOTE}')
i,o,e=c.exec_command(f'sudo -S bash -c "nohup {REMOTE} &"', get_pty=True)
i.write(PASS+'\n'); i.flush(); i.channel.shutdown_write()
time.sleep(2)
print('disparado')
c.close()

for wait in [30, 60, 90, 120]:
    time.sleep(wait)
    try:
        c2=paramiko.SSHClient(); c2.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c2.connect(HOST,username=USER,password=PASS,timeout=30)
        _,o,_=c2.exec_command(f'tail -20 {LOG}; echo ---; df -h /var /tmp /home')
        out=o.read().decode('utf-8','replace')
        c2.close()
        print(f'--- após {wait}s ---\n', out)
        if 'DISK_EXPAND_OK' in out:
            break
        if 'ERRO:' in out:
            break
    except Exception as ex:
        print(f'reconexão falhou ({wait}s):', ex)
