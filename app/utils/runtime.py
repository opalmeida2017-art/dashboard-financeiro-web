"""Detecta ambiente local (Windows/dev) vs produção (Debian/SaaS)."""

from __future__ import annotations

import os
import sys


def is_local_dev() -> bool:
    if os.getenv("BIWEB_LOCAL_DEV", "").strip().lower() in ("1", "true", "yes", "on"):
        return True
    if sys.platform == "win32" and os.getenv("FLASK_ENV", "").strip().lower() == "development":
        return True
    return False


def is_production_server() -> bool:
    if is_local_dev():
        return False
    flag = os.getenv("BIWEB_PRODUCTION", "").strip().lower()
    if flag in ("1", "true", "yes", "on"):
        return True
    tenants = os.getenv("BI_TENANTS_ROOT", "/opt/biweb/tenants")
    return os.path.isdir(tenants)


def apply_runtime_defaults() -> None:
    """Defaults para teste local — não afeta Debian quando FLASK_ENV=production."""
    if not is_local_dev():
        return
    os.environ.setdefault("BIWEB_REQUIRE_TENANT_LINK", "0")
    os.environ.setdefault("BIWEB_SKIP_LOGIN", "true")
    os.environ.setdefault("BIWEB_IDLE_MONITOR", "false")
    os.environ.setdefault("BIWEB_COLETA_COMPROVANTE_AUTO", "false")
