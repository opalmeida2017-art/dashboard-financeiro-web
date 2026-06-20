"""Status postgres e recursos no Debian."""
import paramiko
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"


def run(c, cmd, t=60):
    _, o, e = c.exec_command(cmd, timeout=t)
    o.channel.settimeout(t)
    return (o.read() + e.read()).decode("utf-8", errors="replace")


def sudo(c, cmd, t=60):
    i, o, _ = c.exec_command(f"sudo -S {cmd}", get_pty=True)
    i.write(PASS + "\n")
    i.flush()
    o.channel.settimeout(t)
    return o.read().decode("utf-8", errors="replace")


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=20)

    print("=== memória ===")
    print(run(c, "free -h"))
    print("=== disco ===")
    print(run(c, "df -h"))
    print("=== postgres status ===")
    print(sudo(c, "systemctl status postgresql --no-pager -l | head -30"))
    print("=== postgres log tail ===")
    print(sudo(c, "tail -40 /var/log/postgresql/postgresql-17-main.log 2>/dev/null || tail -40 /var/log/postgresql/*.log"))
    print("=== conhecimento rows? ===")
    print(sudo(c, "-u postgres psql -d sat1_sati_is -tAc \"SELECT COUNT(*) FROM c2910.conhecimento\" 2>&1"))
    c.close()


if __name__ == "__main__":
    main()
