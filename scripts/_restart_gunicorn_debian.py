"""Atualiza gunicorn.service para wsgi:application e reinicia."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts._deploy_debian_atual import HOST, PASS, USER, paramiko, restart_gunicorn_bi

if __name__ == "__main__":
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)
    restart_gunicorn_bi(c)
    c.close()
