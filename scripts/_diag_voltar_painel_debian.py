"""Testa Voltar ao painel e filtro data 2025 no Debian externo."""
from __future__ import annotations

import paramiko

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
EXT = "https://dadosfrete.duckdns.org:8443"
SLUG = "wcarlos"
BI = "/home/oitamar/dashboard-financeiro-web"


def run(c, cmd, t=120):
    _, o, e = c.exec_command(cmd, timeout=t)
    o.channel.settimeout(t)
    return (o.read() + e.read()).decode("utf-8", errors="replace")


def curl_code(c, url, cookie, extra=""):
    cmd = (
        f'curl -sk --max-time 60 {extra} -b {cookie} -c {cookie} '
        f'-o /tmp/curl_out.txt -w "%{{http_code}}" "{url}"'
    )
    code = run(c, cmd, t=70).strip()
    body_head = run(c, "head -c 400 /tmp/curl_out.txt 2>/dev/null | tr '\\n' ' '", t=15)
    return code, body_head


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)
    cookie = "/tmp/biweb_diag.cookie"
    run(c, f"rm -f {cookie}", t=10)

    tests = [
        ("entrada", f"{EXT}/biweb/{SLUG}/"),
        ("painel raiz /", f"{EXT}/?start_date=2026-01-01&end_date=2026-06-20"),
        ("painel data 2025", f"{EXT}/?start_date=2025-01-01&end_date=2026-06-20"),
        ("visao comercial", f"{EXT}/visao_comercial?start_date=2025-01-01&end_date=2026-06-20"),
        ("voltar painel link", f"{EXT}/?start_date=2025-01-01&end_date=2026-06-20"),
    ]

    for name, url in tests:
        code, body = curl_code(c, url, cookie)
        print(f"\n=== {name} ===")
        print(f"URL: {url}")
        print(f"HTTP: {code}")
        print(f"body: {body[:300]}")

    print("\n=== gunicorn error tail ===")
    print(run(c, "tail -25 /var/log/gunicorn-error.log 2>/dev/null", t=30))
    print("\n=== nginx error tail ===")
    print(run(c, "sudo tail -15 /var/log/nginx/error.log 2>/dev/null", t=30))
    c.close()


if __name__ == "__main__":
    main()
