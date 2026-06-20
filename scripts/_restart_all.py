import paramiko
import time
import re

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"


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


def run(c, cmd, timeout=40):
    _, o, e = c.exec_command(cmd, timeout=timeout)
    return (o.read() + e.read()).decode(errors="replace")


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=20)

    print("=== Antes ===")
    print(run(c, "systemctl is-active nginx; pgrep -c gunicorn; systemctl is-active cloudflared-biweb 2>/dev/null"))
    print(run(c, "curl -sI --max-time 5 http://127.0.0.1:8000/ | head -3"))

    print("\n=== Reiniciar BIWEB + nginx ===")
    print(
        run(
            c,
            "cd /home/oitamar/dashboard-financeiro-web && "
            "pkill -f 'gunicorn.*127.0.0.1:8000.*app:app' || true; sleep 3; "
            "./venv/bin/gunicorn --workers 3 --worker-class gevent --bind 127.0.0.1:8000 "
            "--timeout 120 --log-level info --daemon --pid /tmp/gunicorn-dashboard.pid app:app; sleep 3",
            timeout=60,
        )
    )
    print(sudo(c, "nginx -t && systemctl restart nginx"))

    print("\n=== Cloudflared ===")
    print(sudo(c, "systemctl restart cloudflared-biweb"))
    time.sleep(12)

    print("\n=== Depois ===")
    for u in [
        "http://127.0.0.1:8000/",
        "http://dadosfrete.duckdns.org/",
        "https://dadosfrete.duckdns.org/",
    ]:
        print(u, "->", run(c, f"curl -sI --max-time 10 {u} 2>&1 | head -2").strip())

    log = run(c, "grep -o 'https://[a-z0-9-]*\\.trycloudflare\\.com' "
                  "/home/oitamar/cloudflared-tunnel.log | tail -1")
    url = log.strip()
    if url:
        print("Tunel:", url, "->", run(c, f"curl -sI --max-time 12 {url}/ | head -2"))

    print(run(c, "free -h | head -2; uptime"))
    c.close()


if __name__ == "__main__":
    main()
