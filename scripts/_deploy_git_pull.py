"""git pull no Debian + reinício gunicorn/nginx."""
import paramiko
import time

HOST, USER, PASS = "192.168.100.15", "oitamar", "oitapere"
APP = "/home/oitamar/dashboard-financeiro-web"


def sudo(c, cmd, timeout=120):
    i, o, _ = c.exec_command(f"sudo -S bash -lc {repr(cmd)}", get_pty=True)
    i.write(PASS + "\n")
    i.flush()
    deadline = time.time() + timeout
    buf = []
    while time.time() < deadline:
        if o.channel.recv_ready():
            buf.append(o.channel.recv(8192).decode(errors="replace"))
        if o.channel.exit_status_ready():
            break
        time.sleep(0.15)
    if o.channel.recv_ready():
        buf.append(o.channel.recv(65536).decode(errors="replace"))
    return "".join(buf)


def run(c, cmd, timeout=180):
    _, o, e = c.exec_command(cmd, timeout=timeout)
    return (o.read() + e.read()).decode(errors="replace")


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=20)

    print("=== git pull (descarta alteracoes locais no servidor) ===")
    print(
        run(
            c,
            f"cd {APP} && git fetch origin main && "
            "git reset --hard origin/main && "
            "git clean -fd -e .env -e downloads -e pgdata -e data -e tenants",
        )
    )

    print("=== pip ===")
    print(run(c, f"cd {APP} && ./venv/bin/pip install -q -r requirements.txt 2>&1 | tail -8"))

    print("=== reiniciar gunicorn (systemd wsgi:application) ===")
    print(sudo(c, "systemctl restart gunicorn && systemctl is-active gunicorn", timeout=90))
    time.sleep(2)
    print(run(c, "pgrep -af 'gunicorn.*127.0.0.1:8000' | head -3 || true"))
    print(run(c, "systemctl restart rq-biweb 2>/dev/null || true"))

    print("=== nginx ===")
    print(sudo(c, "nginx -t && systemctl restart nginx"))

    print("=== health ===")
    for url in ("http://127.0.0.1:8000/", "http://192.168.100.15/biweb/"):
        out = run(c, f"curl -sI --max-time 10 {url} 2>&1 | head -2")
        print(url, "->", out.strip())

    print(run(c, f"cd {APP} && git log -1 --oneline"))
    c.close()
    print("Deploy Debian concluido.")


if __name__ == "__main__":
    main()
