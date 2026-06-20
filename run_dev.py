"""
Servidor de desenvolvimento local (Windows).

Uso:
    python run_dev.py

Abre em http://127.0.0.1:5000 — sem link /acesso/slug.
Deploy para Debian: só quando você pedir — python scripts/deploy_debian.py --confirmar-deploy
"""
from __future__ import annotations

import os

os.environ.setdefault("BIWEB_LOCAL_DEV", "1")
os.environ.setdefault("BIWEB_DESKTOP", "1")
os.environ.setdefault("BIWEB_REQUIRE_TENANT_LINK", "0")
os.environ.setdefault("BIWEB_SKIP_LOGIN", "true")
os.environ.setdefault("BIWEB_IDLE_MONITOR", "false")
os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("ROBO_HEADLESS", "false")

from app import create_app

app = create_app()

if __name__ == "__main__":
    print("BIWEB dev: http://127.0.0.1:5000")
    print("(Deploy Debian: python scripts/deploy_debian.py --confirmar-deploy)")
    app.run(host="127.0.0.1", port=5000, debug=True)
