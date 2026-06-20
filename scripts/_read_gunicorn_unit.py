"""Lê unit gunicorn no Debian."""
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.100.12", username="oitamar", password="oitapere", timeout=25)
for cmd in [
    "systemctl cat gunicorn.service 2>/dev/null",
    "ls -la /etc/systemd/system/gunicorn.service 2>/dev/null",
    "grep -r gunicorn /home/oitamar/dashboard-financeiro-web/*.sh 2>/dev/null | head -5",
]:
    _, o, e = c.exec_command(cmd, timeout=30)
    o.channel.settimeout(30)
    print("===", cmd[:50], "===")
    print((o.read() + e.read()).decode("utf-8", errors="replace"))
c.close()
