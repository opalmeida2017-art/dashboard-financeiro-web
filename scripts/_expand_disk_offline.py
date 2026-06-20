"""Expande /var e /tmp para 20G — desmonta /home offline (nohup no servidor)."""
import paramiko
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
REMOTE = "/tmp/expand_var_tmp_20g.sh"
LOG = "/tmp/expand_var_tmp_20g.log"

SCRIPT = r"""#!/bin/bash
set -e
exec > /tmp/expand_var_tmp_20g.log 2>&1
echo "=== INICIO $(date) ==="
df -h /var /tmp /home

systemctl stop gunicorn 2>/dev/null || true
systemctl stop nginx 2>/dev/null || true
# postgres em /var — manter rodando

sync
fuser -km /home 2>/dev/null || true
sleep 3
umount /home || umount -l /home
sleep 1

e2fsck -fp /dev/servidor-vg/home
resize2fs /dev/servidor-vg/home 52G
lvreduce -L 52G -y /dev/servidor-vg/home

lvextend -L 20G -r -y /dev/servidor-vg/var
lvextend -L 20G -r -y /dev/servidor-vg/tmp

mount /home
systemctl start nginx 2>/dev/null || true
systemctl start gunicorn 2>/dev/null || true

echo "=== FIM $(date) ==="
df -h /var /tmp /home
vgs servidor-vg
lvs servidor-vg
echo DISK_EXPAND_OK
"""


def run(c, cmd, t=60):
    _, o, e = c.exec_command(cmd, timeout=t)
    o.channel.settimeout(t)
    return (o.read() + e.read()).decode("utf-8", "replace")


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=30)

    sftp = c.open_sftp()
    with sftp.open(REMOTE, "w") as f:
        f.write(SCRIPT)
    sftp.close()

    run(c, f"chmod +x {REMOTE}")
    # dispara com sudo em background (sobrevive se /home cair)
    i, o, _ = c.exec_command(
        f"echo '{PASS}' | sudo -S nohup bash {REMOTE} &", get_pty=True
    )
    time.sleep(3)
    print("Script disparado em background no servidor.")
    print(run(c, f"head -5 {LOG} 2>/dev/null || echo aguardando..."))

    c.close()

    # Reconectar e aguardar conclusão
    for i in range(40):
        time.sleep(15)
        try:
            c2 = paramiko.SSHClient()
            c2.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c2.connect(HOST, username=USER, password=PASS, timeout=20)
            tail = run(c2, f"tail -25 {LOG}", 30)
            c2.close()
            print(f"--- poll {i+1} ---")
            print(tail)
            if "DISK_EXPAND_OK" in tail:
                print("\nExpansão concluída!")
                return
            if "ERRO" in tail or "error" in tail.lower():
                if "Cannot continue" not in tail:
                    pass
        except Exception as exc:
            print(f"reconexão {i+1}: {exc}")

    print("\nVerifique manualmente:", LOG)


if __name__ == "__main__":
    main()
