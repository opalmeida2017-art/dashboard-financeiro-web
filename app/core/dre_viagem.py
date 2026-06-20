"""
DRE por viagem (conhecimento) — regras de prévia de custo e receita.

Receita:
  freteempresa somente se permitefaturar = S.

Pedágio (pedagioembutidofrete = N):
  Não entra na receita nem na prévia de custo — fatura ao cliente e pagamento via contas a pagar
  (despesa real nas notas quando lançado).

Custos prévia (conhecimento) — somente se pagarConhecimento = S (não vão para contas a pagar):
  - Terceiro/agenciamento (tipofrete A/S): fretemotorista integral.
  - Frota própria (P): fretemotorista − comissão (acerto motorista ou % no CT-e).
  - ICMS embutido (icmsembutido = S): valoricms (despesa real depois em CP).
  - Seguro não embutido (descsegurosaldo = N): premioseguro (+ premioseguro2).
  - Quebra: valorquebra.

Despesas reais (itemnota / contas a pagar) somam além da prévia, sem duplicar quebra/comissão.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

import pandas as pd

GRUPOS_DRE_CONHECIMENTO = frozenset({"VALOR QUEBRA", "COMISSÃO DE MOTORISTA"})


def _num(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        if pd.isna(val):
            return default
    except (TypeError, ValueError):
        pass
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _str_flag(val: Any, default: str = "S") -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return default.upper()
    s = str(val).strip().upper()
    return s if s in ("S", "N") else default.upper()


def _get_ci(mapping: Mapping, *keys: str, default=None):
    if not mapping:
        return default
    lower = {str(k).lower(): k for k in mapping.keys()}
    for key in keys:
        orig = lower.get(key.lower())
        if orig is not None:
            val = mapping[orig]
            if val is None or (isinstance(val, float) and pd.isna(val)):
                continue
            return val
    return default


def comissao_acerto_por_numero(df_acerto: pd.DataFrame) -> dict:
    """Soma vlcomissao do acerto por numero de conhecimento."""
    if df_acerto is None or df_acerto.empty or "numero" not in df_acerto.columns:
        return {}
    cm = {str(c).lower(): c for c in df_acerto.columns}
    col_vl = cm.get("vlcomissao") or cm.get("vlbasecomissao") or cm.get("vlbasecomissaocalc")
    if not col_vl:
        return {}
    tmp = df_acerto.copy()
    tmp["_vl"] = pd.to_numeric(tmp[col_vl], errors="coerce").fillna(0.0)
    agg = tmp.groupby("numero", dropna=False)["_vl"].sum()
    return {int(k) if pd.notna(k) else k: float(v) for k, v in agg.items() if v > 0}


def calcular_dre_viagem(
    viagem: Mapping[str, Any],
    comissao_acerto: float = 0.0,
) -> dict[str, float]:
    """Calcula receita e custos prévia de uma viagem a partir do conhecimento."""
    frete_empresa = _num(_get_ci(viagem, "freteempresa", "freteEmpresa"))
    fretemotorista = _num(_get_ci(viagem, "fretemotorista", "freteMotorista"))
    valor_pedagio = _num(_get_ci(viagem, "valorpedagio", "valorPedagio"))
    pedagio_emb = _str_flag(_get_ci(viagem, "pedagioembutidofrete", "pedagioEmbutidoFrete"), "S")
    valor_icms = _num(_get_ci(viagem, "valoricms", "valorICMS", "vlicms", "vlIcms"))
    icms_emb = _str_flag(_get_ci(viagem, "icmsembutido", "icmsEmbutido"), "N")
    valor_seguro = _num(_get_ci(viagem, "premioseguro", "premioSeguro", "valorseguro", "valorSeguro"))
    valor_seguro2 = _num(_get_ci(viagem, "premioseguro2", "premioSeguro2", "valorseguro2", "valorSeguro2"))
    desc_seguro = _str_flag(_get_ci(viagem, "descsegurosaldo", "descSeguroSaldo"), "S")
    valor_quebra = _num(_get_ci(viagem, "valorquebra", "valorQuebra"))
    tipo_frete = str(_get_ci(viagem, "tipofrete", "tipoFrete", default="") or "").strip().upper()
    comissao_pct = _num(_get_ci(viagem, "comissao"))

    permite_faturar_flag = _str_flag(_get_ci(viagem, "permitefaturar", "permiteFaturar"), "N")
    pagar_flag = _str_flag(
        _get_ci(viagem, "pagarConhecimento", "pagarconhecimento", "pagar", "fretePago"),
        "N",
    )
    permite_faturar = permite_faturar_flag == "S"
    pagar_conhecimento = pagar_flag == "S"

    receita = frete_empresa if permite_faturar else 0.0
    pedagio_reembolso = valor_pedagio if pedagio_emb == "N" and valor_pedagio > 0 else 0.0

    comissao_pot = max(0.0, float(comissao_acerto or 0))
    if comissao_pot <= 0 and tipo_frete == "P" and comissao_pct > 0 and fretemotorista > 0:
        comissao_pot = fretemotorista * comissao_pct / 100.0

    if tipo_frete in ("A", "S"):
        motorista_pot = fretemotorista
    elif tipo_frete == "P":
        motorista_pot = max(0.0, fretemotorista - comissao_pot) if fretemotorista > 0 else 0.0
    else:
        motorista_pot = fretemotorista

    icms_pot = valor_icms if icms_emb == "S" and valor_icms > 0 else 0.0
    seguro_pot = (valor_seguro + valor_seguro2) if desc_seguro == "N" else 0.0
    quebra_pot = valor_quebra if valor_quebra > 0 else 0.0
    custo_previa_pot = motorista_pot + icms_pot + seguro_pot + quebra_pot

    if pagar_conhecimento:
        custo_motorista = motorista_pot
        comissao_valor = comissao_pot
        custo_icms = icms_pot
        custo_seguro = seguro_pot
        custo_quebra = quebra_pot
    else:
        custo_motorista = comissao_valor = custo_icms = custo_seguro = custo_quebra = 0.0

    custo_previa = custo_motorista + custo_icms + custo_seguro + custo_quebra

    return {
        "receita": receita,
        "frete_empresa": frete_empresa if permite_faturar else 0.0,
        "frete_empresa_bruto": frete_empresa,
        "permite_faturar": permite_faturar,
        "pagar_conhecimento": pagar_conhecimento,
        "permite_faturar_flag": permite_faturar_flag,
        "pagar_flag": pagar_flag,
        "pedagio_reembolso": pedagio_reembolso,
        "pedagio_fatura_cliente": pedagio_reembolso,
        "valor_pedagio": valor_pedagio,
        "pedagio_embutido": pedagio_emb,
        "custo_motorista": custo_motorista,
        "comissao_motorista": comissao_valor,
        "custo_icms": custo_icms,
        "custo_seguro": custo_seguro,
        "custo_quebra": custo_quebra,
        "custo_motorista_potencial": motorista_pot,
        "comissao_motorista_potencial": comissao_pot,
        "custo_icms_potencial": icms_pot,
        "custo_seguro_potencial": seguro_pot,
        "custo_quebra_potencial": quebra_pot,
        "custo_previa_potencial": custo_previa_pot,
        "custo_previa_conhecimento": custo_previa,
        "tipo_frete": tipo_frete,
    }


def label_tipofrete_dre(tipofrete: str) -> str:
    """Agrupa conhecimento.tipofrete: P=frota; agregado/terceiro=frete agenciamento."""
    tf = str(tipofrete or "").strip().upper()
    if tf == "P":
        return "Frota própria"
    return "Frete/Agenciamento"


def soma_itemnota_sem_grupos_conhecimento(df: pd.DataFrame) -> float:
    """Soma valor_calculado excluindo grupos já contabilizados no conhecimento."""
    if df is None or df.empty or "valor_calculado" not in df.columns:
        return 0.0
    cm = {str(c).lower(): c for c in df.columns}
    grupo_col = cm.get("descgrupod") or cm.get("descGrupoD")
    if not grupo_col:
        return float(pd.to_numeric(df["valor_calculado"], errors="coerce").fillna(0).sum())
    mask = ~df[grupo_col].astype(str).str.upper().isin(GRUPOS_DRE_CONHECIMENTO)
    return float(pd.to_numeric(df.loc[mask, "valor_calculado"], errors="coerce").fillna(0).sum())


def calcular_lucro_viagem(
    dre: Mapping[str, float],
    custos_itemnota: float = 0.0,
    despesas_itemnota: float = 0.0,
    outros_descontos: float = 0.0,
) -> dict[str, float]:
    """Lucro = receita − prévia conhecimento − despesas reais itemnota."""
    receita = float(dre.get("receita", 0))
    custo_total = (
        float(dre.get("custo_previa_conhecimento", 0))
        + float(custos_itemnota or 0)
        + float(despesas_itemnota or 0)
        + float(outros_descontos or 0)
    )
    lucro = receita - custo_total
    margem = (lucro / receita * 100.0) if receita > 0 else 0.0
    return {
        "custo_itemnota": float(custos_itemnota or 0),
        "despesas_itemnota": float(despesas_itemnota or 0),
        "outros_descontos": float(outros_descontos or 0),
        "custo_total": custo_total,
        "lucro": lucro,
        "margem_pct": margem,
    }


def aplicar_dre_em_dataframe(
    df: pd.DataFrame,
    df_acerto: Optional[pd.DataFrame] = None,
    numero_col: str = "numero",
) -> pd.DataFrame:
    """Adiciona colunas de DRE por linha de viagem."""
    if df.empty:
        return df
    comissao_map = comissao_acerto_por_numero(df_acerto) if df_acerto is not None else {}
    rows = []
    for _, row in df.iterrows():
        num = row.get(numero_col)
        try:
            num_key = int(num)
        except (TypeError, ValueError):
            num_key = num
        dre = calcular_dre_viagem(row.to_dict(), comissao_map.get(num_key, 0.0))
        rows.append(dre)
    dre_df = pd.DataFrame(rows, index=df.index)
    out = pd.concat([df.reset_index(drop=True), dre_df.reset_index(drop=True)], axis=1)
    return out


def agrupar_dre(df_com_dre: pd.DataFrame, dim_col: str) -> pd.DataFrame:
    """Agrega receita, custos e margem por dimensão (cliente, rota, etc.)."""
    if df_com_dre.empty or dim_col not in df_com_dre.columns:
        return pd.DataFrame()
    grp = (
        df_com_dre.groupby(dim_col, dropna=False)
        .agg(
            receita=("receita", "sum"),
            custo_previa_conhecimento=("custo_previa_conhecimento", "sum"),
            viagens=("receita", "count"),
        )
        .reset_index()
    )
    grp[dim_col] = grp[dim_col].fillna("(sem nome)").astype(str).str.strip()
    grp = grp[grp[dim_col] != ""]
    grp["lucro"] = grp["receita"] - grp["custo_previa_conhecimento"]
    grp["custo_alocado"] = grp["custo_previa_conhecimento"]
    grp["margem_pct"] = grp.apply(
        lambda r: (r["lucro"] / r["receita"] * 100.0) if r["receita"] > 0 else 0.0,
        axis=1,
    )
    return grp.sort_values("receita", ascending=False)
