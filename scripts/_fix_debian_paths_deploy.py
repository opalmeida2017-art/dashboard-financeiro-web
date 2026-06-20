"""Corrige paths com backslash no Debian e reinicia gunicorn."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
BI = "/home/oitamar/dashboard-financeiro-web"
EXT = "https://dadosfrete.duckdns.org:8443"


def run(c, cmd, t=180):
    _, o, e = c.exec_command(cmd, timeout=t)
    o.channel.settimeout(t)
    return (o.read() + e.read()).decode("utf-8", errors="replace")


def main():
    if "--confirmar-deploy" not in sys.argv:
        from scripts._deploy_guard import exigir_confirmacao_deploy

        exigir_confirmacao_deploy("_fix_debian_paths_deploy")

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)

    # Move arquivos enviados com barra invertida no nome
    fix = f'''
cd {BI}
for f in $(find . -name '*\\\\*' 2>/dev/null); do
  dest=$(echo "$f" | tr '\\\\' '/')
  mkdir -p "$(dirname "$dest")"
  mv -f "$f" "$dest" 2>/dev/null || true
done
# Pastas literais com backslash (SFTP)
for d in app sati_integration infra frontend migrations; do
  if [ -d "$d\\\\" ] 2>/dev/null; then
    mkdir -p "$d"
    cp -a "$d\\\\"/* "$d/" 2>/dev/null || true
    rm -rf "$d\\\\" 2>/dev/null || true
  fi
done
ls -la app/__init__.py wsgi.py 2>&1 | head -5
'''
    print("=== Corrigir paths ===")
    print(run(c, fix, t=120))

    print("\n=== Deploy limpo ===")
    from scripts._deploy_debian_atual import main as deploy_main

    deploy_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
