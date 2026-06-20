import paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.100.12", username="oitamar", password="oitapere", timeout=20)

def sudo(cmd, t=60):
    i, o, _ = c.exec_command("sudo -S " + cmd, get_pty=True)
    i.write("oitapere\n")
    i.flush()
    o.channel.settimeout(t)
    return o.read().decode("utf-8", "replace")

def dig(s):
    d = "".join(ch for ch in s if ch.isdigit())
    return int(d) if d else 0

checks = [
    ("tabelas w_carlos", "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='w_carlos'"),
    ("conhecimento", "SELECT COUNT(*) FROM w_carlos.conhecimento"),
    ("nota", "SELECT COUNT(*) FROM w_carlos.nota"),
    ("cliente", "SELECT COUNT(*) FROM w_carlos.cliente"),
]
for label, q in checks:
    print(label + ":", dig(sudo("-u postgres psql -d sat1_sati_is -tAc \"" + q + "\"")))

print("gunicorn:", sudo("systemctl is-active gunicorn").strip()[-20:])
print("postgres:", sudo("systemctl is-active postgresql@17-main").strip()[-20:])
c.close()
