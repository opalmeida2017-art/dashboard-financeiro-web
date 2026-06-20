import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.100.12", username="oitamar", password="oitapere", timeout=20)
_, o, e = c.exec_command("curl -s http://127.0.0.1:8000/ | head -30")
print((o.read() + e.read()).decode(errors="replace"))
c.close()
