"""Aumenta memoria, CPU e rede do BI no Debian (gunicorn, postgres, nginx, rq)."""
from __future__ import annotations

import re
import sys
import textwrap
from pathlib import Path

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
BI = "/home/oitamar/dashboard-financeiro-web"
NFE = "/opt/nfe-web"


def run(c, cmd: str, timeout: int = 120) -> str:
    _, o, e = c.exec_command(cmd, timeout=timeout)
    o.channel.settimeout(timeout)
    return (o.read() + e.read()).decode("utf-8", "replace")


def sudo(c, cmd: str, timeout: int = 180) -> str:
    i, o, _ = c.exec_command(f"sudo -S bash -lc {repr(cmd)}", get_pty=True, timeout=timeout)
    i.write(PASS + "\n")
    i.flush()
    o.channel.settimeout(timeout)
    return o.read().decode("utf-8", "replace")


def detect_workers(c) -> int:
    ncpu = int(run(c, "nproc").strip() or "2")
    # gevent: mais workers sem explodir RAM (pandas em restore usa outro processo)
    return min(8, max(4, ncpu * 2))


def detect_memory_mb(c) -> int:
    txt = run(c, "grep -i MemTotal /proc/meminfo | awk '{print int($2/1024)}'").strip()
    try:
        total = int(txt)
    except ValueError:
        total = 4096
    return total


def postgres_tuning(total_mb: int) -> dict[str, str]:
    shared = max(256, min(2048, total_mb // 4))
    cache = max(512, min(4096, total_mb // 2))
    work = max(16, min(128, total_mb // 64))
    maint = max(128, min(1024, total_mb // 8))
    return {
        "shared_buffers": f"{shared}MB",
        "effective_cache_size": f"{cache}MB",
        "work_mem": f"{work}MB",
        "maintenance_work_mem": f"{maint}MB",
        "max_connections": "100",
        "random_page_cost": "1.1",
        "effective_io_concurrency": "200",
    }


def patch_postgresql_conf(c, values: dict[str, str]) -> None:
    conf = "/etc/postgresql/17/main/postgresql.conf"
    if "No such file" in run(c, f"test -f {conf} && echo OK || echo MISSING"):
        conf = run(c, "ls /etc/postgresql/*/main/postgresql.conf 2>/dev/null | head -1").strip()
    if not conf:
        print("PostgreSQL conf nao encontrado — pulando.")
        return
    snippet = "\n".join(f"{k} = {v}" for k, v in values.items())
    block = textwrap.dedent(
        f"""
        # --- BIWEB tune {Path(__file__).name} ---
        {snippet}
        # --- fim BIWEB tune ---
        """
    ).strip()
    run(c, f"cat > /tmp/biweb_pg_tune.conf <<'EOF'\n{block}\nEOF")
    sudo(
        c,
        "python3 - <<'PY'\n"
        "import re\n"
        "from pathlib import Path\n"
        f"conf = Path({conf!r})\n"
        "text = conf.read_text(encoding='utf-8')\n"
        "text = re.sub(r'\\n# --- BIWEB tune.*?# --- fim BIWEB tune ---\\n', '\\n', text, flags=re.S)\n"
        f"block = Path('/tmp/biweb_pg_tune.conf').read_text(encoding='utf-8')\n"
        "conf.write_text(text.rstrip() + '\\n\\n' + block + '\\n', encoding='utf-8')\n"
        "print('pg conf ok')\n"
        "PY",
    )
    print(f"PostgreSQL ajustado: {conf}")


def gunicorn_unit(workers: int, mem_max: str) -> str:
    return textwrap.dedent(
        f"""
        [Unit]
        Description=Gunicorn BIWEB (dashboard-financeiro-web)
        After=network.target postgresql.service redis-server.service
        Wants=postgresql.service redis-server.service

        [Service]
        User=oitamar
        Group=www-data
        WorkingDirectory={BI}
        EnvironmentFile={BI}/.env
        Environment="PATH={BI}/venv/bin"
        Environment="PYTHONUNBUFFERED=1"
        ExecStart={BI}/venv/bin/gunicorn wsgi:application \\
          --workers {workers} \\
          --worker-class gevent \\
          --worker-connections 1000 \\
          --bind 127.0.0.1:8000 \\
          --timeout 300 \\
          --graceful-timeout 60 \\
          --keep-alive 5 \\
          --max-requests 2000 \\
          --max-requests-jitter 200 \\
          --log-level info
        Restart=always
        RestartSec=5
        LimitNOFILE=65535
        MemoryMax={mem_max}
        CPUQuota=400%

        [Install]
        WantedBy=multi-user.target
        """
    ).strip() + "\n"


def nginx_snippet() -> str:
    return textwrap.dedent(
        """
        # BIWEB tune — buffers e timeouts para internet lenta
        client_max_body_size 512m;
        client_body_buffer_size 16m;
        proxy_buffer_size 128k;
        proxy_buffers 8 256k;
        proxy_busy_buffers_size 512k;
        proxy_read_timeout 600s;
        proxy_connect_timeout 120s;
        proxy_send_timeout 600s;
        send_timeout 600s;
        keepalive_timeout 75s;
        """
    ).strip()


def patch_nginx(c) -> None:
    sites = [
        "/etc/nginx/sites-enabled/default",
        "/etc/nginx/sites-available/default",
    ]
    site = next((s for s in sites if "OK" in run(c, f"test -f {s} && echo OK")), "")
    if not site:
        print("nginx default nao encontrado — pulando.")
        return
    snippet = nginx_snippet()
    run(c, f"cat > /tmp/biweb_nginx_tune.conf <<'EOF'\n{snippet}\nEOF")
    sudo(
        c,
        "python3 - <<'PY'\n"
        "import re\n"
        "from pathlib import Path\n"
        f"p = Path({site!r})\n"
        "text = p.read_text(encoding='utf-8')\n"
        "block = Path('/tmp/biweb_nginx_tune.conf').read_text(encoding='utf-8')\n"
        "wrapped = '# BIWEB tune\\n' + block + '\\n# fim BIWEB tune\\n'\n"
        "if '# BIWEB tune' in text:\n"
        "    text = re.sub(r'# BIWEB tune.*?# fim BIWEB tune\\n', wrapped, text, flags=re.S)\n"
        "elif 'server {' in text:\n"
        "    text = text.replace('server {', 'server {\\n' + wrapped, 1)\n"
        "p.write_text(text, encoding='utf-8')\n"
        "print('nginx ok')\n"
        "PY",
    )
    print(sudo(c, "nginx -t && systemctl reload nginx"))


def rq_worker_unit() -> str:
    return textwrap.dedent(
        f"""
        [Unit]
        Description=RQ worker BIWEB
        After=network.target redis-server.service
        Wants=redis-server.service

        [Service]
        User=oitamar
        WorkingDirectory={BI}
        EnvironmentFile={BI}/.env
        Environment="PATH={BI}/venv/bin"
        ExecStart={BI}/venv/bin/rq worker default --url redis://localhost:6379
        Restart=always
        RestartSec=5
        MemoryMax=2G
        CPUQuota=300%

        [Install]
        WantedBy=multi-user.target
        """
    ).strip() + "\n"


def nfe_unit_patch(mem_max: str) -> str:
    return textwrap.dedent(
        f"""
        [Service]
        MemoryMax={mem_max}
        CPUQuota=300%
        LimitNOFILE=65535
        """
    ).strip()


def upload_unit(c, local_content: str, remote_tmp: str, remote_final: str) -> None:
    sftp = c.open_sftp()
    with sftp.open(remote_tmp, "w") as f:
        f.write(local_content)
    sftp.close()
    print(sudo(c, f"cp {remote_tmp} {remote_final} && systemctl daemon-reload"))


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)

    print("=== Recursos atuais ===")
    print(run(c, "nproc; free -h; df -h / /var /home | head -5"))

    workers = detect_workers(c)
    total_mb = detect_memory_mb(c)
    gunicorn_mem = f"{max(3, min(8, total_mb // 1024))}G"
    nfe_mem = f"{max(1, min(4, total_mb // 2048))}G"

    print(f"\n=== Plano: workers={workers}, RAM total={total_mb}MB, gunicorn MemoryMax={gunicorn_mem} ===")

    print("\n=== PostgreSQL ===")
    patch_postgresql_conf(c, postgres_tuning(total_mb))
    print(sudo(c, "systemctl restart postgresql@17-main 2>/dev/null || systemctl restart postgresql"))

    print("\n=== Gunicorn ===")
    upload_unit(
        c,
        gunicorn_unit(workers, gunicorn_mem),
        "/tmp/gunicorn.service.biweb",
        "/etc/systemd/system/gunicorn.service",
    )
    print(sudo(c, "systemctl enable gunicorn && systemctl restart gunicorn"))
    print(run(c, "systemctl is-active gunicorn; pgrep -af 'gunicorn.*8000' | head -2"))

    print("\n=== RQ worker (systemd) ===")
    run(c, "pkill -f 'rq worker default' || true")
    upload_unit(
        c,
        rq_worker_unit(),
        "/tmp/rq-biweb.service",
        "/etc/systemd/system/rq-biweb.service",
    )
    print(sudo(c, "systemctl enable rq-biweb && systemctl restart rq-biweb"))
    print(run(c, "systemctl is-active rq-biweb; pgrep -af 'rq worker' | head -2"))

    print("\n=== Nginx (internet / uploads grandes) ===")
    patch_nginx(c)

    print("\n=== nfe-web limits ===")
    nfe_drop = "/etc/systemd/system/nfe-web.service.d/biweb-tune.conf"
    print(sudo(c, "mkdir -p /etc/systemd/system/nfe-web.service.d"))
    upload_unit(
        c,
        nfe_unit_patch(nfe_mem),
        "/tmp/nfe-web-tune.conf",
        nfe_drop,
    )
    print(sudo(c, "systemctl restart nfe-web 2>/dev/null || true"))

    print("\n=== cloudflared ===")
    print(sudo(c, "systemctl restart cloudflared-biweb 2>/dev/null || systemctl restart cloudflared 2>/dev/null || true"))

    print("\n=== Health ===")
    for url in ("http://127.0.0.1:8000/", "https://dadosfrete.duckdns.org/"):
        print(run(c, f"curl -sS -o /dev/null -w '{url} -> %{{http_code}} t=%{{time_total}}\\n' --max-time 45 -k '{url}'"))

    print("\n=== Memoria pos-ajuste ===")
    print(run(c, "free -h; systemctl show gunicorn -p MemoryMax -p CPUQuota"))

    c.close()
    print("\nTune BIWEB Debian concluido.")


if __name__ == "__main__":
    main()
