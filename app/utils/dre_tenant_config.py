"""Regras DRE quando há filtro de proprietário no painel (BI_COD_PROPRIETARIO)."""
from __future__ import annotations


def tem_filtro_proprietario(apartamento_id: int) -> bool:
    """True quando codProprietario está configurado no painel de licenças."""
    try:
        from app.data.data_manager import obter_cod_proprietario_filtro
    except ImportError:
        from data_manager import obter_cod_proprietario_filtro  # type: ignore

    return obter_cod_proprietario_filtro(apartamento_id) is not None


def obter_dre_opts(apartamento_id: int) -> dict:
    """
    Modo proprietário (cod_proprietario no painel):
      - receita = fretemotorista (não freteempresa)
      - frete motorista e ICMS não entram no custo prévia (são receita, não custo)
    """
    modo_prop = tem_filtro_proprietario(apartamento_id)
    return {
        "campo_receita": "fretemotorista" if modo_prop else "freteempresa",
        "incluir_icms_custo": not modo_prop,
    }
