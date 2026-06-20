"""Deploy alterações BIWEB + painel para Debian (SCP + reinício serviços).

NÃO execute este arquivo diretamente.
Use: python scripts/deploy_debian.py --confirmar-deploy
"""
import sys
import time
from pathlib import Path

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

if __name__ == "__main__":
    _root = Path(__file__).resolve().parents[1]
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))
    from scripts._deploy_guard import exigir_confirmacao_deploy

    exigir_confirmacao_deploy("_deploy_debian_atual")

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
BI = "/home/oitamar/dashboard-financeiro-web"
NFE = "/opt/nfe-web"
LOCAL = r"c:\python\BIWEB"

BI_DIRS = [
    "app",
    "sati_integration",
    "infra",
    "frontend",
    "migrations",
]
BI_FILES = [
    "wsgi.py",
    "worker.py",
    "requirements.txt",
]

NFE_FILES = [
    (f"{LOCAL}\\scripts\\_server_painel.js", f"{NFE}/frontend/painel/painel.js"),
]


def run(c, cmd, t=180, read_output=True):
    _, o, e = c.exec_command(cmd, timeout=t)
    if not read_output:
        return ""
    o.channel.settimeout(t)
    return (o.read() + e.read()).decode("utf-8", errors="replace")


def sudo(c, cmd, t=120):
    i, o, _ = c.exec_command(f"sudo -S bash -lc {repr(cmd)}", get_pty=True)
    i.write(PASS + "\n")
    i.flush()
    o.channel.settimeout(t)
    return o.read().decode("utf-8", errors="replace")


def patch_painel_api(c):
    """Oculta transportes-brasil-ltda na API da aba BI."""
    painel_py = f"{NFE}/backend/app/routers/painel.py"
    marker = 'BRASIL_SLUG = "transportes-brasil-ltda"'
    check = run(c, f"grep -n '{marker}' {painel_py} || true")
    if marker in check:
        print("painel.py: filtro Brasil já presente")
        return
    snippet = (
        'BRASIL_SLUG = "transportes-brasil-ltda"\n'
        'BI_SLUGS_OCULTOS = {BRASIL_SLUG}\n'
    )
    run(
        c,
        f"python3 - <<'PY'\n"
        f"from pathlib import Path\n"
        f"p = Path({painel_py!r})\n"
        f"text = p.read_text(encoding='utf-8')\n"
        f"if 'BI_SLUGS_OCULTOS' not in text:\n"
        f"    if 'BRASIL_SLUG' not in text:\n"
        f"        text = {snippet!r} + text\n"
        f"    old = 'tenants = [registry.enrich_tenant(t) for t in registry.list_tenants()]'\n"
        f"    new = ('tenants = [registry.enrich_tenant(t) for t in registry.list_tenants() '\n"
        f"             'if str(t.get(\\\"slug\\\") or \\\"\\\").lower() not in BI_SLUGS_OCULTOS]')\n"
        f"    if old in text:\n"
        f"        text = text.replace(old, new)\n"
        f"        p.write_text(text, encoding='utf-8')\n"
        f"        print('patched listar_bi_tenants')\n"
        f"    else:\n"
        f"        print('WARN: padrão listar_bi_tenants não encontrado')\n"
        f"PY",
    )


def _ensure_remote_dir(sftp, remote_dir: str) -> None:
    remote_dir = remote_dir.replace("\\", "/").rstrip("/")
    if not remote_dir:
        return
    parts = remote_dir.split("/")
    cur = ""
    for part in parts:
        if not part:
            continue
        cur = f"{cur}/{part}"
        try:
            sftp.stat(cur)
        except OSError:
            sftp.mkdir(cur)


def _remote_path(remote_base: str, rel: str) -> str:
    rel_posix = (rel or "").replace("\\", "/")
    if not rel_posix:
        return remote_base
    return f"{remote_base}/{rel_posix}".replace("\\", "/")


def upload_tree(sftp, local_base: str, remote_base: str, rel: str = ""):
    import os

    local_path = os.path.join(local_base, rel) if rel else local_base
    remote_path = _remote_path(remote_base, rel)
    if os.path.isfile(local_path):
        _ensure_remote_dir(sftp, os.path.dirname(remote_path).replace("\\", "/"))
        sftp.put(local_path, remote_path)
        print(f"Upload {remote_path}")
        return
    for name in os.listdir(local_path):
        if name in ("__pycache__", ".git", "downloads", "venv"):
            continue
        upload_tree(sftp, local_base, remote_base, os.path.join(rel, name) if rel else name)


def patch_gunicorn_unit(c):
    unit = "/etc/systemd/system/gunicorn.service"
    check = run(c, f"grep -F 'wsgi:application' {unit} 2>/dev/null || true", t=20)
    changed = False
    if "wsgi:application" not in check:
        print(sudo(c, f"sudo sed -i 's/app:app/wsgi:application/g' {unit}", t=60))
        changed = True
    if "--timeout" not in run(c, f"grep timeout {unit} || true", t=15):
        print(
            sudo(
                c,
                "sudo sed -i 's|--log-level=debug|--timeout 120 --log-level=info|g' "
                f"{unit} || sudo sed -i 's|wsgi:application|wsgi:application --timeout 120|g' {unit}",
                t=60,
            )
        )
        changed = True
    if changed:
        print(sudo(c, "sudo systemctl daemon-reload", t=30))
    print(run(c, f"grep ExecStart {unit}", t=15))


def restart_gunicorn_bi(c):
    patch_gunicorn_unit(c)
    print(sudo(c, "systemctl restart gunicorn && systemctl is-active gunicorn", t=90))
    time.sleep(2)
    print(run(c, "pgrep -af 'gunicorn.*127.0.0.1:8000' | head -3 || true", t=30))
    print(run(c, "tail -8 /var/log/gunicorn-error.log 2>/dev/null || true", t=20))


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)

    sftp = c.open_sftp()
    for rel in BI_DIRS:
        upload_tree(sftp, LOCAL, BI, rel)
    for rel in BI_FILES:
        src = f"{LOCAL}\\{rel.replace('/', chr(92))}"
        dst = f"{BI}/{rel}"
        print(f"Upload {dst}")
        sftp.put(src, dst)

    for src, dst in NFE_FILES:
        print(f"Upload {dst}")
        sftp.put(src, dst)
    sftp.close()

    print("\n=== Patch API painel (ocultar Brasil na aba BI) ===")
    print(patch_painel_api(c))

    print("\n=== Reiniciar gunicorn BI ===")
    restart_gunicorn_bi(c)

    print("\n=== Reiniciar nfe-web (painel licenças) ===")
    print(sudo(c, "systemctl restart nfe-web || true"))
    time.sleep(2)
    print(run(c, "systemctl is-active nfe-web || true"))

    print("\n=== Reiniciar rq worker ===")
    run(c, "pkill -f 'rq worker default' || true", t=30)
    time.sleep(1)
    run(
        c,
        f"cd {BI} && nohup ./venv/bin/rq worker default -u redis://localhost:6379 "
        f">> rq_worker.log 2>&1 </dev/null &",
        t=10,
        read_output=False,
    )
    time.sleep(2)
    print(run(c, "pgrep -af 'rq worker' | head -2 || echo 'rq worker nao encontrado'", t=30))

    print("\n=== nginx ===")
    print(sudo(c, "nginx -t && systemctl restart nginx"))

    print("\n=== Testes HTTP ===")
    tests = [
        "https://dadosfrete.duckdns.org/",
        "https://dadosfrete.duckdns.org/acesso/w-carlos",
        "https://dadosfrete.duckdns.org/painel_licenca/",
    ]
    for url in tests:
        out = run(c, f"curl -sI --max-time 15 -k {url} 2>&1 | head -3")
        print(url, "->", out.strip())

    c.close()
    print("\nDeploy Debian concluído.")


if __name__ == "__main__":
    main()
