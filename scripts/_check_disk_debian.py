"""Verifica layout LVM/disco no Debian."""
import paramiko
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"


def run(c, cmd, t=60):
    _, o, e = c.exec_command(cmd, timeout=t)
    o.channel.settimeout(t)
    return (o.read() + e.read()).decode("utf-8", "replace")


def sudo(c, cmd, t=60):
    i, o, _ = c.exec_command(f"sudo -S {cmd}", get_pty=True)
    i.write(PASS + "\n")
    i.flush()
    o.channel.settimeout(t)
    return o.read().decode("utf-8", "replace")


c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=20)

cmds = [
    "df -h",
    "lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINT",
    "sudo -S vgs 2>/dev/null || true",
    "sudo -S lvs 2>/dev/null || true",
    "sudo -S pvs 2>/dev/null || true",
]
for cmd in cmds:
    print(f"\n=== {cmd} ===")
    if cmd.startswith("sudo"):
        print(sudo(c, cmd.replace("sudo -S ", "")))
    else:
        print(run(c, cmd))

c.close()
