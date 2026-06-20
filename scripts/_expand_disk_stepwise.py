"""Expande /var e /tmp para 20G — comandos individuais."""
import paramiko
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"


def run(c, cmd, t=120):
    print(f"\n>>> {cmd}")
    _, o, e = c.exec_command(cmd, timeout=t)
    o.channel.settimeout(t)
    out = (o.read() + e.read()).decode("utf-8", "replace")
    print(out[-3000:] if len(out) > 3000 else out)
    return out


def sudo(c, cmd, t=600):
    print(f"\n>>> sudo {cmd}")
    i, o, e = c.exec_command(f"sudo -S {cmd}", get_pty=True, timeout=t)
    i.write(PASS + "\n")
    i.flush()
    i.channel.shutdown_write()
    o.channel.settimeout(t)
    err = e.read().decode("utf-8", "replace")
    out = o.read().decode("utf-8", "replace")
    combined = out + err
    print(combined[-4000:] if len(combined) > 4000 else combined)
    return combined


c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=30)

run(c, "df -h /var /tmp /home")
run(c, "sudo vgs && sudo lvs", 30)

steps = [
    "e2fsck -fp /dev/servidor-vg/home",
    "resize2fs /dev/servidor-vg/home 52G",
    "lvreduce -L 52G -y /dev/servidor-vg/home",
    "lvextend -L 20G -r -y /dev/servidor-vg/var",
    "lvextend -L 20G -r -y /dev/servidor-vg/tmp",
]

for step in steps:
    sudo(c, step, t=900)

run(c, "df -h /var /tmp /home")
run(c, "sudo vgs && sudo lvs", 30)

c.close()
print("\nFIM")
