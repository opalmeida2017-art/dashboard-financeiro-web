"""
DRE por viagem (conhecimento) — regras de prévia de custo e receita.

Receita:
  freteempresa somente se permitefaturar = S.
  Com BI_COD_PROPRIETARIO no painel: fretemotorista (não freteempresa).

Pedágio (pedagioembutidofrete = N):
  Não entra na receita nem na prévia de custo — fatura ao cliente e pagamento via contas a pagar
  (despesa real nas notas quando lançado).

Frete motorista líquido (regra universal — calcular_frete_motorista_liquido):
  Próprio (P):
    líquido = vlcomissao do acerto motorista, quando existir; senão 0 (sem estimar %).
  Terceiro / Agregado (A/S):
    líquido = fretemotorista − quebra − outros descontos mot.
              − pedágio motorista (se pedagioembfretemot = N)
              − seguro (se descsegurosaldomot = S)

Custos prévia (conhecimento) — somente se pagarConhecimento = S:
  frete motorista líquido + ICMS embutido + seguro não embutido no saldo empresa.
  Com filtro de proprietário no painel: receita = fretemotorista — frete motorista
  e ICMS não entram no custo prévia (são receita, não custo).

Despesas reais (itemnota) somam além da prévia, sem duplicar quebra/comissão.
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


def extrair_dados_frete_motorista(viagem: Mapping[str, Any]) -> dict[str, Any]:
    """Extrai campos do conhecimento para o cálculo universal do frete motorista líquido."""
    valor_pedagio_mot = _num(
        _get_ci(viagem, "valorpedagiomot", "valorPedagioMot", "valorpedagio", "valorPedagio")
    )
    valor_seguro = _num(_get_ci(viagem, "premioseguro", "premioSeguro", "valorseguro", "valorSeguro"))
    valor_seguro2 = _num(_get_ci(viagem, "premioseguro2", "premioSeguro2", "valorseguro2", "valorSeguro2"))
    return {
        "fretemotorista": _num(_get_ci(viagem, "fretemotorista", "freteMotorista")),
        "valor_quebra": _num(_get_ci(viagem, "valorquebra", "valorQuebra")),
        "tipo_frete": str(_get_ci(viagem, "tipofrete", "tipoFrete", default="") or "").strip().upper(),
        "comissao_pct": _num(_get_ci(viagem, "comissao")),
        "valor_pedagio_mot": valor_pedagio_mot,
        "pedagio_emb_mot": _str_flag(_get_ci(viagem, "pedagioembfretemot", "pedagioEmbFretMot"), "N"),
        "valor_seguro": valor_seguro,
        "valor_seguro2": valor_seguro2,
        "desc_seguro_mot": _str_flag(_get_ci(viagem, "descsegurosaldomot", "descSeguroSaldoMot"), "N"),
        "outros_descontos_mot": (
            _num(_get_ci(viagem, "outrosdescontosmot", "outrosDescontosMot"))
            + _num(_get_ci(viagem, "outrosdescontosmot2", "outrosDescontosMot2"))
        ),
        "seguro_motorista": (
            (valor_seguro + valor_seguro2)
            if _str_flag(_get_ci(viagem, "descsegurosaldomot", "descSeguroSaldoMot"), "N") == "S"
            else 0.0
        ),
    }


def calcular_frete_motorista_liquido(
    fretemotorista: float,
    valor_quebra: float,
    tipo_frete: str,
    comissao_pct: float,
    comissao_acerto: float = 0.0,
    valor_pedagio_mot: float = 0.0,
    pedagio_emb_mot: str = "N",
    valor_seguro: float = 0.0,
    valor_seguro2: float = 0.0,
    desc_seguro_mot: str = "N",
    outros_descontos_mot: float = 0.0,
    *,
    detalhar: bool = True,
) -> dict[str, Any]:
    """
    Regra universal do valor pago ao motorista (frete motorista líquido).

    Próprio (P): vlcomissao do acerto motorista; sem acerto → 0 (não estima %).
    Terceiro/Agregado (A/S): fretemotorista − quebra − outros − pedágio não embutido − seguro mot.
    """
    detalhe: list[dict[str, Any]] = []
    quebra = max(0.0, float(valor_quebra or 0))
    seg_mot = (float(valor_seguro or 0) + float(valor_seguro2 or 0)) if desc_seguro_mot == "S" else 0.0
    tf = str(tipo_frete or "").strip().upper()
    base_comissao = 0.0
    comissao_valor = 0.0

    def _linha(label: str, valor: float, tipo: str) -> None:
        if detalhar:
            detalhe.append({"label": label, "valor": valor, "tipo": tipo})

    if fretemotorista > 0:
        _linha("Frete motorista (CT-e)", fretemotorista, "base")

    if tf == "P":
        acerto_val = max(0.0, float(comissao_acerto or 0))
        if acerto_val > 0:
            comissao_valor = acerto_val
            liquido = acerto_val
            _linha("Comissão (acerto motorista — vlcomissao)", comissao_valor, "comissao")
        else:
            if detalhar and fretemotorista > 0:
                detalhe.append({
                    "label": "Sem vlcomissao no acerto — não entra na prévia",
                    "valor": 0.0,
                    "tipo": "info",
                })
            liquido = 0.0
            comissao_valor = 0.0
    else:
        liquido = max(0.0, float(fretemotorista or 0))
        if quebra > 0:
            _linha("(-) Valor quebra", quebra, "desconto")
            liquido = max(0.0, liquido - quebra)
        if outros_descontos_mot > 0:
            _linha("(-) Outros descontos motorista", outros_descontos_mot, "desconto")
            liquido = max(0.0, liquido - outros_descontos_mot)
        ped_nao_emb = float(valor_pedagio_mot or 0) if pedagio_emb_mot == "N" else 0.0
        if ped_nao_emb > 0:
            _linha("(-) Pedágio (não embutido frete mot.)", ped_nao_emb, "desconto")
            liquido = max(0.0, liquido - ped_nao_emb)
        if seg_mot > 0:
            _linha("(-) Seguro (desconto motorista)", seg_mot, "desconto")
            liquido = max(0.0, liquido - seg_mot)

    if detalhar and (liquido > 0 or fretemotorista > 0):
        _linha("= Frete motorista líquido", liquido, "resultado")

    return {
        "liquido": liquido,
        "base_comissao": base_comissao,
        "comissao_valor": comissao_valor,
        "composicao": detalhe,
        "tipo_frete": tf,
    }


def _composicao_frete_motorista(
    fretemotorista: float,
    valor_quebra: float,
    tipo_frete: str,
    comissao_acerto: float,
    comissao_pct: float,
    valor_pedagio_mot: float,
    pedagio_emb_mot: str,
    valor_seguro: float,
    valor_seguro2: float,
    desc_seguro_mot: str,
    outros_descontos_mot: float,
) -> tuple[float, float, list[dict[str, Any]]]:
    """Wrapper legado — delega para calcular_frete_motorista_liquido."""
    r = calcular_frete_motorista_liquido(
        fretemotorista=fretemotorista,
        valor_quebra=valor_quebra,
        tipo_frete=tipo_frete,
        comissao_pct=comissao_pct,
        comissao_acerto=comissao_acerto,
        valor_pedagio_mot=valor_pedagio_mot,
        pedagio_emb_mot=pedagio_emb_mot,
        valor_seguro=valor_seguro,
        valor_seguro2=valor_seguro2,
        desc_seguro_mot=desc_seguro_mot,
        outros_descontos_mot=outros_descontos_mot,
    )
    return r["liquido"], r["comissao_valor"], r["composicao"]


def _campo_receita_cfg(campo: str) -> str:
    c = str(campo or "freteempresa").strip().lower()
    return "fretemotorista" if c in ("fretemotorista", "frete_motorista") else "freteempresa"


def calcular_dre_viagem(
    viagem: Mapping[str, Any],
    comissao_acerto: float = 0.0,
    *,
    incluir_composicao: bool = True,
    campo_receita: str = "freteempresa",
    incluir_icms_custo: bool = True,
) -> dict[str, float]:
    """Calcula receita e custos prévia de uma viagem a partir do conhecimento."""
    frete_empresa = _num(_get_ci(viagem, "freteempresa", "freteEmpresa"))
    dados_mot = extrair_dados_frete_motorista(viagem)
    fretemotorista = dados_mot["fretemotorista"]
    valor_pedagio = _num(_get_ci(viagem, "valorpedagio", "valorPedagio"))
    pedagio_emb = _str_flag(_get_ci(viagem, "pedagioembutidofrete", "pedagioEmbutidoFrete"), "S")
    valor_icms = _num(_get_ci(viagem, "valoricms", "valorICMS", "vlicms", "vlIcms"))
    icms_emb = _str_flag(_get_ci(viagem, "icmsembutido", "icmsEmbutido"), "N")
    valor_seguro = dados_mot["valor_seguro"]
    valor_seguro2 = dados_mot["valor_seguro2"]
    desc_seguro = _str_flag(_get_ci(viagem, "descsegurosaldo", "descSeguroSaldo"), "S")
    valor_quebra = dados_mot["valor_quebra"]
    tipo_frete = dados_mot["tipo_frete"]
    comissao_pct = dados_mot["comissao_pct"]

    permite_faturar_flag = _str_flag(_get_ci(viagem, "permitefaturar", "permiteFaturar"), "N")
    pagar_flag = _str_flag(
        _get_ci(viagem, "pagarConhecimento", "pagarconhecimento", "pagar", "fretePago"),
        "N",
    )
    permite_faturar = permite_faturar_flag == "S"
    pagar_conhecimento = pagar_flag == "S"

    campo_rec = _campo_receita_cfg(campo_receita)
    base_receita = fretemotorista if campo_rec == "fretemotorista" else frete_empresa
    receita = base_receita if permite_faturar else 0.0
    pedagio_reembolso = valor_pedagio if pedagio_emb == "N" and valor_pedagio > 0 else 0.0

    mot = calcular_frete_motorista_liquido(
        fretemotorista=fretemotorista,
        valor_quebra=valor_quebra,
        tipo_frete=tipo_frete,
        comissao_pct=comissao_pct,
        comissao_acerto=comissao_acerto,
        valor_pedagio_mot=dados_mot["valor_pedagio_mot"],
        pedagio_emb_mot=dados_mot["pedagio_emb_mot"],
        valor_seguro=valor_seguro,
        valor_seguro2=valor_seguro2,
        desc_seguro_mot=dados_mot["desc_seguro_mot"],
        outros_descontos_mot=dados_mot["outros_descontos_mot"],
        detalhar=incluir_composicao,
    )
    motorista_pot = mot["liquido"]
    comissao_pot = mot["comissao_valor"]
    composicao_motorista = mot["composicao"]
    base_comissao = mot["base_comissao"]

    modo_receita_motorista = campo_rec == "fretemotorista"
    motorista_para_custo = 0.0 if modo_receita_motorista else motorista_pot
    comissao_para_custo = 0.0 if modo_receita_motorista else comissao_pot

    icms_pot = (
        valor_icms
        if incluir_icms_custo and icms_emb == "S" and valor_icms > 0
        else 0.0
    )
    seguro_pot = (valor_seguro + valor_seguro2) if desc_seguro == "N" else 0.0
    # Quebra já compõe o frete motorista líquido — não somar de novo na prévia.
    quebra_pot = 0.0
    custo_previa_pot = motorista_para_custo + icms_pot + seguro_pot + quebra_pot

    if pagar_conhecimento:
        custo_motorista = motorista_para_custo
        comissao_valor = comissao_para_custo
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
        "pedagio_embutido_motorista": dados_mot["pedagio_emb_mot"],
        "fretemotorista_bruto": fretemotorista,
        "valor_quebra_bruto": valor_quebra,
        "base_comissao": base_comissao,
        "composicao_motorista": composicao_motorista,
        "custo_motorista": custo_motorista,
        "comissao_motorista": comissao_valor,
        "custo_icms": custo_icms,
        "custo_seguro": custo_seguro,
        "custo_quebra": custo_quebra,
        "custo_motorista_potencial": motorista_pot,
        "comissao_motorista_potencial": comissao_pot,
        "custo_icms_potencial": icms_pot,
        "custo_seguro_potencial": seguro_pot,
        "custo_quebra_potencial": valor_quebra,
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


def label_tipofrete_relatorio(tipofrete: str) -> str:
    """Rótulo para relatório de viagem: Próprio, Agregado ou Terceiro."""
    tf = str(tipofrete or "").strip().upper()
    if tf == "P":
        return "Próprio"
    if tf == "A":
        return "Agregado"
    if tf == "S":
        return "Terceiro"
    return tf or "—"


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


def agregar_componentes_custo_previa(df_dre: pd.DataFrame) -> list[dict[str, Any]]:
    """Composição do custo prévia CT-e: motorista (frota × frete) + ICMS + seguro + total."""
    if df_dre is None or df_dre.empty:
        return []

    mot = pd.to_numeric(df_dre.get("custo_motorista", 0), errors="coerce").fillna(0.0)
    if "tipo_frete" in df_dre.columns:
        tf = df_dre["tipo_frete"].astype(str).str.strip().str.upper()
    else:
        cm = {str(c).lower(): c for c in df_dre.columns}
        col_tf = cm.get("tipofrete")
        tf = (
            df_dre[col_tf].astype(str).str.strip().str.upper()
            if col_tf and col_tf in df_dre.columns
            else pd.Series("", index=df_dre.index)
        )

    linhas: list[dict[str, Any]] = [
        {
            "componente": "Frete motorista líquido — Frota",
            "valor": round(float(mot[tf == "P"].sum()), 2),
        },
        {
            "componente": "Frete motorista líquido — Frete (agenc./terceiro)",
            "valor": round(float(mot[tf != "P"].sum()), 2),
        },
    ]
    for label, col in (
        ("ICMS embutido", "custo_icms"),
        ("Seguro empresa", "custo_seguro"),
    ):
        if col in df_dre.columns:
            val = float(pd.to_numeric(df_dre[col], errors="coerce").fillna(0).sum())
            linhas.append({"componente": label, "valor": round(val, 2)})

    if "custo_previa_conhecimento" in df_dre.columns:
        total_prev = float(
            pd.to_numeric(df_dre["custo_previa_conhecimento"], errors="coerce").fillna(0).sum()
        )
    else:
        total_prev = sum(float(x["valor"]) for x in linhas)
    linhas.append(
        {
            "componente": "Total custo prévia CT-e (painel)",
            "valor": round(total_prev, 2),
            "destaque": True,
        }
    )
    return linhas


def aplicar_dre_em_dataframe(
    df: pd.DataFrame,
    df_acerto: Optional[pd.DataFrame] = None,
    numero_col: str = "numero",
    dre_opts: dict | None = None,
) -> pd.DataFrame:
    """Adiciona colunas de DRE por linha de viagem."""
    if df.empty:
        return df
    opts = dre_opts or {}
    campo_receita = opts.get("campo_receita", "freteempresa")
    incluir_icms_custo = opts.get("incluir_icms_custo", True)
    comissao_map = comissao_acerto_por_numero(df_acerto) if df_acerto is not None else {}
    cm = {str(c).lower(): c for c in df.columns}
    num_col = cm.get(numero_col.lower()) or numero_col
    if num_col not in df.columns:
        num_col = next(iter(df.columns))

    records = df.to_dict("records")
    numeros = df[num_col].tolist()
    rows = []
    for row, num in zip(records, numeros):
        try:
            num_key = int(num)
        except (TypeError, ValueError):
            num_key = num
        rows.append(
            calcular_dre_viagem(
                row,
                comissao_map.get(num_key, 0.0),
                incluir_composicao=False,
                campo_receita=campo_receita,
                incluir_icms_custo=incluir_icms_custo,
            )
        )

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
