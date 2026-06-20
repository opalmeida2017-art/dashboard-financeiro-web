"""Bloqueia deploy acidental no servidor Debian."""

from __future__ import annotations

import os
import sys


def deploy_confirmado(argv: list[str] | None = None) -> bool:
    if os.getenv("BIWEB_DEPLOY_CONFIRM", "").strip() == "1":
        return True
    args = argv if argv is not None else sys.argv[1:]
    return "--confirmar-deploy" in args


def exigir_confirmacao_deploy(script: str = "deploy") -> None:
    if deploy_confirmado():
        return
    print(
        f"\n[{script}] Deploy para Debian BLOQUEADO.\n"
        "Este ambiente é só para teste local (run_dev.py).\n"
        "Quando quiser enviar para produção, execute explicitamente:\n\n"
        "  python scripts/deploy_debian.py --confirmar-deploy\n"
    )
    sys.exit(2)
