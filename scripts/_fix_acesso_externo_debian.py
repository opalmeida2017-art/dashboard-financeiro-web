"""Corrige lentidão e estabiliza acesso externo no Debian."""
import paramiko

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
GUNICORN_UNIT = """[Unit]
Description=Gunicorn instance to serve Flask application
After=network.target

[Service]
User=oitamar
Group=www-data
WorkingDirectory=/home/oitamar/dashboard-financeiro-web
EnvironmentFile=/home/oitamar/dashboard-financeiro-web/.env
Environment="PATH=/home/oitamar/dashboard-financeiro-web/venv/bin"
ExecStart=/home/oitamar/dashboard-financeiro-web/venv/bin/gunicorn --workers 4 --worker-class gevent --bind 127.0.0.1:8000 --timeout 180 --log-level info app:app
Restart=always
StandardOutput=append:/var/log/gunicorn-access.log
StandardError=append:/var/log/gunicorn-error.log

[Install]
WantedBy=multi-user.target
"""


def run(c, cmd, timeout=120):
    _, o, e = c.exec_command(cmd, timeout=timeout)
    return (o.read() + e.read()).decode("utf-8", "replace")


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=20)
    sftp = c.open_sftp()
    with sftp.open("/tmp/gunicorn.service.new", "w") as f:
        f.write(GUNICORN_UNIT)
    sftp.close()

    cmds = [
        "sudo -n cp /tmp/gunicorn.service.new /etc/systemd/system/gunicorn.service "
        "&& sudo -n systemctl daemon-reload "
        "&& sudo -n systemctl restart gunicorn nginx cloudflared-biweb "
        "&& echo SERVICES_OK || echo SERVICES_NEED_SUDO",
        "(crontab -l 2>/dev/null | grep -v duck.sh | grep -v duckdns.org || true; "
        "echo \"*/5 * * * * curl -fsS 'https://www.duckdns.org/update?domains=dadosfrete"
        "&token=ad7dc87e-dd2a-41d5-98ea-1b77b23b4ce1&ip=' -o /tmp/duckdns.log 2>/dev/null\") "
        "| crontab -",
        "curl -fsS 'https://www.duckdns.org/update?domains=dadosfrete"
        "&token=ad7dc87e-dd2a-41d5-98ea-1b77b23b4ce1&ip=' && echo DUCK_OK",
        "pgrep -af 'gunicorn.*8000' | head -2",
        "for u in https://dadosfrete.duckdns.org/ https://dadosfrete.duckdns.org/biweb/transportes-brasil-ltda/; do "
        "curl -sS -o /dev/null -w \"$u -> %{http_code} t=%{time_total}\\n\" --max-time 30 -k \"$u\"; done",
        "grep -oE 'https://[a-z0-9-]+\\.trycloudflare\\.com' /home/oitamar/cloudflared-tunnel.log | tail -1",
    ]
    for cmd in cmds:
        print("=" * 50)
        print(run(c, cmd))
    c.close()


if __name__ == "__main__":
    main()
