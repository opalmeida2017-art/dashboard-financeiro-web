"""Move arquivos com backslash no nome para paths Unix no Debian."""
from __future__ import annotations

import base64
import sys

import paramiko

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
BI = "/home/oitamar/dashboard-financeiro-web"

FIX_PY = b"""import os
from pathlib import Path
root = Path(".")
moved = 0
for p in sorted(root.rglob("*"), key=lambda x: len(str(x)), reverse=True):
    if not p.exists():
        continue
    rel = str(p.relative_to(root))
    if "\\\\" not in rel:
        continue
    dest = root / rel.replace("\\\\", "/")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if p.is_dir():
        continue
    if dest.exists():
        dest.unlink()
    p.rename(dest)
    moved += 1
    print("mv", rel, "->", dest)
print("moved", moved)
print("app_init", (root / "app" / "__init__.py").is_file())
print("wsgi", (root / "wsgi.py").is_file())
"""


def run(c, cmd, t=120):
    _, o, e = c.exec_command(cmd, timeout=t)
    o.channel.settimeout(t)
    return (o.read() + e.read()).decode("utf-8", errors="replace")


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)
    b64 = base64.b64encode(FIX_PY).decode("ascii")
    cmd = f"cd {BI} && echo {b64} | base64 -d | ./venv/bin/python"
    print(run(c, cmd, t=180))
    c.close()


if __name__ == "__main__":
    main()
