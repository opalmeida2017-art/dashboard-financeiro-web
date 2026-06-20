import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.100.12", username="oitamar", password="oitapere", timeout=12)
_, o, _ = c.exec_command('sudo -n -u postgres psql -tAc "SELECT 1" 2>&1', timeout=10)
print(o.read().decode())
c.close()
