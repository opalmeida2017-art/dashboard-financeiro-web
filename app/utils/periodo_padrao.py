"""Período padrão do BI ao abrir sem filtro de datas na URL."""
from __future__ import annotations

from datetime import datetime

PERIODO_MES_ATUAL = "mes_atual"
PERIODO_ULTIMOS_3_MESES = "ultimos_3_meses"
PERIODO_ANO_ATUAL = "ano_atual"
PERIODOS_VALIDOS = frozenset(
    {PERIODO_MES_ATUAL, PERIODO_ULTIMOS_3_MESES, PERIODO_ANO_ATUAL}
)
CHAVE_CONFIG = "BI_PERIODO_PADRAO"
PERIODO_PADRAO_DEFAULT = PERIODO_MES_ATUAL

LABELS = {
    PERIODO_MES_ATUAL: "Mês atual",
    PERIODO_ULTIMOS_3_MESES: "Últimos 3 meses",
    PERIODO_ANO_ATUAL: "Ano atual",
}


def normalizar_periodo_padrao(valor: str | None) -> str:
    p = str(valor or "").strip().lower()
    if p in PERIODOS_VALIDOS:
        return p
    return PERIODO_PADRAO_DEFAULT


def calcular_intervalo_periodo_padrao(
    periodo: str | None, ref: datetime | None = None
) -> tuple[datetime, datetime]:
    """Calcula início/fim conforme preset escolhido no painel."""
    hoje = ref or datetime.now()
    fim = hoje.replace(hour=23, minute=59, second=59, microsecond=0)
    p = normalizar_periodo_padrao(periodo)

    if p == PERIODO_ULTIMOS_3_MESES:
        y, m = hoje.year, hoje.month - 2
        while m <= 0:
            m += 12
            y -= 1
        inicio = datetime(y, m, 1)
    elif p == PERIODO_ANO_ATUAL:
        inicio = datetime(hoje.year, 1, 1)
    else:
        inicio = datetime(hoje.year, hoje.month, 1)
    return inicio, fim
