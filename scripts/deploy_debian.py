"""
Deploy BIWEB → servidor Debian (produção).

Só roda com confirmação explícita — não é chamado automaticamente.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts._deploy_guard import exigir_confirmacao_deploy

if __name__ == "__main__":
    exigir_confirmacao_deploy("deploy_debian")
    from scripts._deploy_debian_atual import main

    main()
