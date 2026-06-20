"""Expande /var e /tmp para 20G cada (espaço vindo de /home)."""
import paramiko
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"

REMOTE_SH = r"""#!/bin/bash
set -e
export PATH=/sbin:/usr/sbin:$PATH

echo "=== ANTES ==="
df -h /var /tmp /home
vgs servidor-vg
lvs servidor-vg

# home usa ~5G; sobra 52G após emprestar ~35G para var+tmp
NEW_HOME=52G

echo "=== e2fsck home ==="
e2fsck -fp /dev/servidor-vg/home || true

echo "=== Reduzindo filesystem home para $NEW_HOME ==="
resize2fs /dev/servidor-vg/home $NEW_HOME

echo "=== Reduzindo LV home ==="
lvreduce -L $NEW_HOME -y /dev/servidor-vg/home

echo "=== Expandindo var para 20G ==="
lvextend -L 20G -r -y /dev/servidor-vg/var

echo "=== Expandindo tmp para 20G ==="
lvextend -L 20G -r -y /dev/servidor-vg/tmp

echo "=== DEPOIS ==="
df -h /var /tmp /home
vgs servidor-vg
lvs servidor-vg
echo "DISK_EXPAND_OK"
"""


def sudo_script(c, script, timeout=600):
    i, o, _ = c.exec_command(f"sudo -S bash -s", get_pty=True)
    i.write(PASS + "\n")
    i.flush()
    i.write(script)
    i.flush()
    i.channel.shutdown_write()
    o.channel.settimeout(timeout)
    out = ""
    while True:
        try:
            chunk = o.read(4096)
            if not chunk:
                break
            out += chunk.decode("utf-8", "replace")
            print(chunk.decode("utf-8", "replace"), end="", flush=True)
        except Exception:
            break
    return out


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=20)

    # Para restore preso e libera locks
    c.exec_command("pkill -f restore_manual || true")
    c.exec_command("pkill -f processar_arquivo_zip_sati || true")
    time.sleep(2)

    print("Executando expansão LVM no servidor...")
    out = sudo_script(c, REMOTE_SH, timeout=900)

    if "DISK_EXPAND_OK" in out:
        print("\nExpansão concluída com sucesso.")
    else:
        print("\nVerifique a saída acima — pode ter falhado parcialmente.")

    c.close()


if __name__ == "__main__":
    main()
