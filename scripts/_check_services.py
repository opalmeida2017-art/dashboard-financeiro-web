import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.100.12", username="oitamar", password="oitapere", timeout=20)
i, o, _ = c.exec_command(
    'sudo -S systemctl is-active nginx gunicorn postgresql cloudflared 2>&1; '
    'curl -s -o /dev/null -w "HTTP %{http_code}" -H "X-BI-Tenant-Slug: w-carlos" http://127.0.0.1:8000/',
    get_pty=True,
)
i.write("oitapere\n")
i.flush()
print(o.read().decode("utf-8", "replace"))
c.close()
