"""Versão do BIWEB (servidor web / painel)."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _ler_arquivo_version() -> str:
    for base in (_project_root(), Path(__file__).resolve().parent):
        p = base / "VERSION"
        if p.is_file():
            linha = p.read_text(encoding="utf-8").strip().splitlines()
            if linha:
                return linha[0].strip()
    return ""


__version__ = (
    os.getenv("BIWEB_VERSION", "").strip()
    or _ler_arquivo_version()
    or "1.0.0"
)


def versao_exibicao() -> str:
    return __version__
