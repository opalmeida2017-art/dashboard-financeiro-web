"""Instala script Python de atualização DuckDNS no Debian."""
import paramiko

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
LOCAL_SCRIPT = r"C:\python\BIWEB\scripts\atualiza_duckdns.py"
REMOTE_SCRIPT = "/home/oitamar/scripts/atualiza_duckdns.py"
REMOTE_ENV = "/home/oitamar/scripts/duckdns.env"
# Token que já funciona no cron atual do servidor
DUCKDNS_TOKEN = "ad7dc87e-dd2a-41d5-98ea-1b77b23b4ce1"


def run(c, cmd, timeout=90):
    _, o, e = c.exec_command(cmd, timeout=timeout)
    return (o.read() + e.read()).decode("utf-8", "replace")


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=20)

    sftp = c.open_sftp()
    sftp.put(LOCAL_SCRIPT, REMOTE_SCRIPT)
    # env no servidor (não versionar token no git)
    env_content = (
        f"DUCKDNS_TOKEN={DUCKDNS_TOKEN}\n"
        "DUCKDNS_DOMAIN=dadosfrete\n"
        "DUCKDNS_STATE_FILE=/var/log/duckdns/ultimo_ip.txt\n"
    )
    with sftp.open(REMOTE_ENV, "w") as f:
        f.write(env_content)
    sftp.close()

    cron_line = (
        f"*/5 * * * * /usr/bin/python3 {REMOTE_SCRIPT} "
        ">> /var/log/duckdns/atualiza.log 2>&1"
    )
    cmds = [
        f"chmod +x {REMOTE_SCRIPT}",
        "mkdir -p /var/log/duckdns",
        f"(crontab -l 2>/dev/null | grep -v duck.sh | grep -v duckdns.org | grep -v atualiza_duckdns.py || true; "
        f"echo '{cron_line}') | crontab -",
        f"python3 {REMOTE_SCRIPT}",
        "echo PUBLIC=$(curl -4 -sS --max-time 8 ifconfig.me); "
        "echo DUCK=$(dig +short dadosfrete.duckdns.org @8.8.8.8 | tail -1)",
        "crontab -l | grep duck",
    ]
    for cmd in cmds:
        print("=" * 50)
        print(run(c, cmd))
    c.close()
    print("Instalação concluída.")


if __name__ == "__main__":
    main()
