"""
Vínculo comprovante de descarga (Painel SATI) ↔ CT-e (conhecimento).

No Painel de Documentos o arquivo aparece como:
  2026/COMPROVANTEDEDESCARGA/2COMPROVANT_7965.pdf
O número após 2COMPROVANT_ é o campo conhecimento.numero (chave interna),
não o numeroconhecimento impresso no CT-e (ex.: 23323).
"""
from __future__ import annotations

import re
from typing import Any

# Tipo doc. 69 no Painel SATI = comprovante de descarga (amostra c3332)
COD_TIPO_DOC_COMPROVANTE_DESCARGA = 69

RE_COMPROVANT_NUMERO = re.compile(r"2COMPROVANT_(\d+)", re.IGNORECASE)
RE_COMPROVANT_PATH = re.compile(
    r"(?:^|[\\/])(?:\d{4}[\\/])?(?:COMPROVANTEDEDESCARGA[\\/])?"
    r"(?:DESCARGA[\\/])?2COMPROVANT_(\d+)\.(pdf|jpe?g|png)$",
    re.IGNORECASE,
)


def normalizar_nome_arquivo(nomearq: str | None) -> str:
    if not nomearq:
        return ""
    return str(nomearq).strip().replace("\\", "/")


def extrair_numero_conhecimento(nomearq: str | None) -> int | None:
    """
    Extrai conhecimento.numero a partir do nome do arquivo SATI.
    Ex.: 2026/COMPROVANTEDEDESCARGA/2COMPROVANT_7965.pdf → 7965
    """
    path = normalizar_nome_arquivo(nomearq)
    if not path:
        return None
    m = RE_COMPROVANT_PATH.search(path) or RE_COMPROVANT_NUMERO.search(path)
    if not m:
        return None
    try:
        return int(m.group(1))
    except (TypeError, ValueError):
        return None


def eh_comprovante_descarga(
    nomearq: str | None = None,
    codtipodoc: Any = None,
    nome_base: str | None = None,
) -> bool:
    path = normalizar_nome_arquivo(nomearq).upper()
    if "COMPROVANT" in path or (nome_base and "COMPROVANT" in str(nome_base).upper()):
        return True
    try:
        return int(codtipodoc) == COD_TIPO_DOC_COMPROVANTE_DESCARGA
    except (TypeError, ValueError):
        return False


def resolver_vinculo_cte(
    nomearq: str | None,
    chavetabela: int | None = None,
) -> dict[str, Any]:
    """
    Retorna vínculo esperado entre arquivo e CT-e.
    chavetabela no banco = conhecimento.numero quando nometabela='CONHECIMENTO'.
    """
    numero_arquivo = extrair_numero_conhecimento(nomearq)
    chave = None
    if chavetabela is not None:
        try:
            chave = int(chavetabela)
        except (TypeError, ValueError):
            chave = None
    consistente = (
        numero_arquivo is not None
        and chave is not None
        and numero_arquivo == chave
    )
    return {
        "numero_conhecimento": numero_arquivo,
        "chavetabela": chave,
        "consistente": consistente if chave is not None else numero_arquivo is not None,
        "nomearq": normalizar_nome_arquivo(nomearq),
    }
