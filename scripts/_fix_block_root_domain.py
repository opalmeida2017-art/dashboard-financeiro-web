"""Bloqueia raiz do domínio sem /biweb/slug/ no Debian + deploy Flask."""
import paramiko
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
BI = "/home/oitamar/dashboard-financeiro-web"
LOCAL = r"c:\python\BIWEB"

NGINX_SNIPPET = r"""
    # BIWEB: raiz sem transportadora -> 403
    location = / {
        default_type text/html;
        return 403 '<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><title>Acesso restrito</title></head><body style="font-family:system-ui;background:#0f1419;color:#e7ecf3;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0"><div style="max-width:480px;padding:2rem;background:#1a2332;border-radius:12px"><h1>Link da transportadora obrigatório</h1><p>Use o link exclusivo, por exemplo:</p><code style="display:block;margin-top:1rem;padding:.75rem;background:#0d1117;border-radius:8px;color:#7dd3fc">https://dadosfrete.duckdns.org:8443/biweb/sua-transportadora/</code></div></body></html>';
    }
"""


def run(c, cmd, t=90):
    _, o, e = c.exec_command(cmd, timeout=t)
    o.channel.settimeout(t)
    return (o.read() + e.read()).decode("utf-8", "replace")


def sudo(c, cmd, t=90):
    i, o, _ = c.exec_command(f"sudo -S bash -lc {repr(cmd)}", get_pty=True)
    i.write(PASS + "\n")
    i.flush()
    o.channel.settimeout(t)
    return o.read().decode("utf-8", "replace")


def patch_nginx(c):
    cfg = "/etc/nginx/sites-enabled/default"
    check = run(c, f"grep -q 'location = /' {cfg} && echo HAS_ROOT_BLOCK || echo MISSING")
    if "MISSING" in check:
        # Inserir após server_name dadosfrete no bloco 443
        sudo(
            c,
            f"sed -i '/server_name dadosfrete.duckdns.org;/a\\{NGINX_SNIPPET}' {cfg}",
        )
        sudo(c, "nginx -t && systemctl reload nginx")
    else:
        print("nginx: location = / já existe")


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)

    sftp = c.open_sftp()
    files = [
        ("bi_tenant_runtime.py", f"{BI}/bi_tenant_runtime.py"),
        ("blueprints/auth.py", f"{BI}/blueprints/auth.py"),
        ("templates/acesso_negado.html", f"{BI}/templates/acesso_negado.html"),
    ]
    for rel, remote in files:
        sftp.put(f"{LOCAL}\\{rel.replace('/', chr(92))}", remote)
        print(f"Upload {remote}")
    sftp.close()

    print(run(c, f"grep -q BIWEB_REQUIRE_TENANT_LINK=1 {BI}/.env || echo BIWEB_REQUIRE_TENANT_LINK=1 >> {BI}/.env"))
    patch_nginx(c)

    print("\n=== Testes HTTP ===")
    for url in (
        "https://dadosfrete.duckdns.org/",
        "https://dadosfrete.duckdns.org:8443/",
        "https://dadosfrete.duckdns.org:8443/biweb/wcarlos/",
    ):
        print(run(c, f'curl -sS -o /dev/null -w "{url} -> %{{http_code}}\\n" -k --max-time 15 "{url}"'))

    print(run(c, "pkill -HUP -f 'gunicorn.*127.0.0.1:8000' 2>/dev/null || true"))
    c.close()
    print("Concluído.")


if __name__ == "__main__":
    main()
