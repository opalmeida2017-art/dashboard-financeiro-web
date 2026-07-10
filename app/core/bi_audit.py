"""Auditoria de métricas BI — rastreio até CT-e e itens de nota."""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd

from app.data import data_manager as dm
from app.core import dre_viagem as dre
from app.core.gestao_comercial import _base_viagens_fat
from app.utils.dre_tenant_config import obter_dre_opts

METRICAS: dict[str, dict[str, str]] = {
    "receita_frete": {
        "titulo": "Receita de frete",
        "formula": (
            "freteempresa quando permitefaturar = S; com codProprietario no painel, "
            "usa fretemotorista (regras DRE do conhecimento)."
        ),
        "listagem": "cte",
    },
    "custo_operacional": {
        "titulo": "Custos operacionais",
        "formula": (
            "Custo prévia CT-e (pagarConhecimento) + custos em notas (ved=V, grupo=custo) "
            "+ despesas gerais (ved=V, grupo=despesa) + tipo D (ved=D, grupo marcado)."
        ),
        "listagem": "misto",
    },
    "custo_viagem": {
        "titulo": "Custo de viagem",
        "formula": "Custo prévia CT-e (DRE) + itens de nota ved=V classificados como custo de viagem.",
        "listagem": "misto",
    },
    "custo_previa_conhecimento": {
        "titulo": "Custo prévia CT-e",
        "formula": (
            "Frota: vlcomissao do acerto; Frete (agenc./terceiro): frete mot. − quebra − descontos − "
            "pedágio − seguro mot.; + ICMS embutido + seguro empresa, quando pagarConhecimento = S."
        ),
        "listagem": "cte",
    },
    "custo_nota_itemnota": {
        "titulo": "Custo em notas (itemnota)",
        "formula": "nota despesa=S, ved=V, grupo com is_custo_viagem = S.",
        "listagem": "nota",
    },
    "despesas_gerais": {
        "titulo": "Despesas gerais",
        "formula": (
            "nota despesa=S + tiponfe=0 (ou série RQ com tiponfe vazio), ved=V; "
            "padrão despesa; grupo pode mudar para custo. ved=E não entra."
        ),
        "listagem": "nota",
    },
    "despesas_tipo_d": {
        "titulo": "Despesas tipo D (diversos)",
        "formula": "nota despesa=S, itemnota.ved = D e grupo com incluir_em_tipo_d marcado.",
        "listagem": "nota",
    },
    "receita_comercio": {
        "titulo": "Receita comércio",
        "formula": "Ramo COMERCIO + nota despesa=N + (tiponfe=0 ou série RQ) + tipo=0 (venda). VED=D não exclui.",
        "listagem": "nota",
    },
    "despesa_comercio": {
        "titulo": "Despesa comércio",
        "formula": "Ramo COMERCIO + nota despesa=S + (tiponfe=0 ou série RQ). VED=D não exclui.",
        "listagem": "nota",
    },
    "investimento": {
        "titulo": "Investimento",
        "formula": (
            "nota despesa=S (tiponfe=0 ou RQ) e item.investimento=S. "
            "Os valores já entram em custo de viagem, despesas gerais ou tipo D."
        ),
        "listagem": "nota",
    },
    "investimento_estoque": {
        "titulo": "Investimento estoque",
        "formula": (
            "Cadastro item: investimento=S e saldo>0. "
            "Valor = saldo × custo (ou custoultcompra). Posição atual — não entra na despesa."
        ),
        "listagem": "estoque",
    },
    "resultado_liquido": {
        "titulo": "Resultado líquido",
        "formula": "Receita de frete − custos operacionais (composição abaixo).",
        "listagem": "resumo",
    },
    "margem_frete": {
        "titulo": "Margem sobre frete",
        "formula": "Resultado líquido ÷ receita de frete × 100.",
        "listagem": "resumo",
    },
    "margem_cliente": {
        "titulo": "Composição da margem por cliente",
        "formula": "Receita, custo prévia e margem por CT-e do cliente no período.",
        "listagem": "misto",
    },
    "contas_pagar": {
        "titulo": "Contas a pagar pendentes",
        "formula": (
            "Duplicatas AP sem codtransacao e sem datapagamento; "
            "vencimento de 01/01/2000 até ontem. Valores com vencimento futuro "
            "aparecem em «A vencer»."
        ),
        "listagem": "financeiro",
    },
    "contas_receber": {
        "titulo": "Contas a receber pendentes",
        "formula": (
            "Duplicatas AR sem codtransacao e sem datapagamento; "
            "vencimento de 01/01/2000 até ontem. Valores com vencimento futuro "
            "aparecem em «A vencer»."
        ),
        "listagem": "financeiro",
    },
}


def narrow_dates_by_periodo_label(
    periodo_label: str | None,
    start_date,
    end_date,
):
    """Restringe o intervalo ao mês/dia clicado no gráfico (ex.: Jun/2026)."""
    if not periodo_label or not str(periodo_label).strip():
        return start_date, end_date
    label = str(periodo_label).strip()
    ref_year = pd.Timestamp(end_date).year if end_date is not None else pd.Timestamp.now().year

    parsed = pd.to_datetime(label, format="%b/%Y", errors="coerce")
    parts = label.split("/")
    is_month = pd.notna(parsed) or (len(parts) == 2 and not parts[0].strip().isdigit())
    if not pd.notna(parsed):
        parsed = pd.to_datetime(label, format="%d/%m/%Y", errors="coerce")
    if not pd.notna(parsed):
        parsed = pd.to_datetime(f"{label}/{ref_year}", format="%d/%m/%Y", errors="coerce")
    if not pd.notna(parsed):
        parsed = pd.to_datetime(label, dayfirst=True, errors="coerce")
    if not pd.notna(parsed):
        return start_date, end_date

    parsed = pd.Timestamp(parsed).normalize()
    if is_month:
        pstart = parsed.to_period("M").start_time.normalize()
        pend = parsed.to_period("M").end_time.normalize()
    else:
        pstart = pend = parsed

    if start_date is not None:
        pstart = max(pstart, pd.Timestamp(start_date).normalize())
    if end_date is not None:
        pend = min(pend, pd.Timestamp(end_date).normalize())
    return pstart.to_pydatetime(), pend.to_pydatetime()


def _display_cte(numero: Any, num_conhec: Any = None) -> str:
    base = str(int(numero)) if pd.notna(numero) else str(numero)
    if num_conhec is None or (isinstance(num_conhec, float) and pd.isna(num_conhec)):
        return base
    try:
        nc = int(float(num_conhec))
        if nc != 0:
            return f"{base} ({nc})"
    except (TypeError, ValueError):
        pass
    return base


def _fmt_data(val: Any) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    try:
        return pd.to_datetime(val, errors="coerce").strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return str(val)


def _merge_num_conhec(df: pd.DataFrame, df_fat: pd.DataFrame) -> pd.DataFrame:
    if df.empty or df_fat is None or df_fat.empty:
        return df
    cm_fat = dm._get_case_insensitive_column_map(df_fat.columns)
    col_num = cm_fat.get("numero")
    col_nc = cm_fat.get("numconhec")
    if not col_num or not col_nc:
        return df
    nc = df_fat[[col_num, col_nc]].drop_duplicates(subset=[col_num])
    nc = nc.rename(columns={col_num: "numero", col_nc: "_num_conhec"})
    return df.merge(nc, on="numero", how="left")


def _linhas_margem_cliente(df_dre: pd.DataFrame, cv: dict) -> list[dict[str, Any]]:
    if df_dre.empty:
        return []
    col_num = cv.get("numero", "numero")
    col_cli = cv.get("nomecliente")
    col_dt = cv.get("dataviagemmotorista")
    linhas: list[dict[str, Any]] = []
    for _, row in df_dre.iterrows():
        receita = float(row.get("receita", 0) or 0)
        custo = float(row.get("custo_previa_conhecimento", 0) or 0)
        lucro = receita - custo
        margem = (lucro / receita * 100) if receita > 0 else 0.0
        numero = row.get(col_num)
        try:
            numero_int = int(numero)
        except (TypeError, ValueError):
            numero_int = numero
        linhas.append(
            {
                "numero": numero_int,
                "display": _display_cte(numero, row.get("_num_conhec")),
                "cliente": str(row[col_cli]).strip() if col_cli and pd.notna(row.get(col_cli)) else "",
                "data_viagem": _fmt_data(row.get(col_dt) if col_dt else None),
                "receita": round(receita, 2),
                "custo_previa": round(custo, 2),
                "lucro": round(lucro, 2),
                "margem_pct": round(margem, 1),
            }
        )
    linhas.sort(key=lambda x: (x.get("margem_pct", 0), -x.get("receita", 0)))
    return linhas


def _linhas_cte(df_dre: pd.DataFrame, cv: dict, metric: str) -> list[dict[str, Any]]:
    if df_dre.empty:
        return []
    col_num = cv.get("numero", "numero")
    col_cli = cv.get("nomecliente")
    col_dt = cv.get("dataviagemmotorista")
    linhas: list[dict[str, Any]] = []

    for _, row in df_dre.iterrows():
        receita = float(row.get("receita", 0) or 0)
        custo_previa = float(row.get("custo_previa_conhecimento", 0) or 0)
        frete_bruto = float(row.get("frete_empresa_bruto", 0) or 0)
        custo_pot = float(row.get("custo_previa_potencial", 0) or 0)

        if metric == "receita_frete" and receita <= 0:
            continue
        if metric in ("custo_previa", "custo_previa_conhecimento") and custo_pot <= 0 and custo_previa <= 0:
            continue
        if metric == "custo_operacional" and custo_previa <= 0:
            continue

        numero = row.get(col_num)
        try:
            numero_int = int(numero)
        except (TypeError, ValueError):
            numero_int = numero

        linhas.append(
            {
                "numero": numero_int,
                "display": _display_cte(numero, row.get("_num_conhec")),
                "cliente": str(row[col_cli]).strip() if col_cli and pd.notna(row.get(col_cli)) else "",
                "data_viagem": _fmt_data(row.get(col_dt) if col_dt else None),
                "receita": round(receita, 2),
                "frete_empresa_bruto": round(frete_bruto, 2),
                "custo_previa": round(custo_previa, 2),
                "custo_previa_potencial": round(custo_pot, 2),
                "permite_faturar": str(row.get("permite_faturar_flag", "")),
                "pagarConhecimento": str(row.get("pagar_flag", "")),
            }
        )

    linhas.sort(key=lambda x: (-x.get("receita", 0), str(x.get("data_viagem", ""))))
    return linhas


def _linhas_itemnota(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    cm = dm._get_case_insensitive_column_map(df.columns)
    col_grupo = cm.get("descgrupod")
    col_item = cm.get("descitemd")
    col_ved = cm.get("ved")
    col_dt = cm.get("datacontrole") or cm.get("dataemissao")
    col_serie = cm.get("serie")
    col_placa = cm.get("placaveiculo")
    col_codnota = cm.get("codnota")
    col_coditem = cm.get("coditemnota")
    col_numnota = cm.get("numnota") or cm.get("numeronota")
    col_forn = cm.get("nomefornecedor")

    linhas: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        if "valor_calculado" in df.columns:
            valor = float(pd.to_numeric(row.get("valor_calculado"), errors="coerce") or 0)
        elif cm.get("valor"):
            valor = float(pd.to_numeric(row[cm["valor"]], errors="coerce") or 0)
        elif cm.get("liquido"):
            valor = float(pd.to_numeric(row[cm["liquido"]], errors="coerce") or 0)
        else:
            valor = 0.0
        if valor == 0:
            continue
        codnota = row.get(col_codnota) if col_codnota else None
        coditem = row.get(col_coditem) if col_coditem else None
        numnota = row.get(col_numnota) if col_numnota else None
        linhas.append(
            {
                "codnota": int(codnota) if pd.notna(codnota) else codnota,
                "cod_itemnota": int(coditem) if pd.notna(coditem) else coditem,
                "nota": f"{numnota}/{row[col_serie]}" if col_serie and pd.notna(numnota) else str(numnota or codnota or "—"),
                "data": _fmt_data(row.get(col_dt) if col_dt else None),
                "grupo": str(row[col_grupo]).strip() if col_grupo and pd.notna(row.get(col_grupo)) else "",
                "item": str(row[col_item]).strip() if col_item and pd.notna(row.get(col_item)) else "",
                "ved": str(row[col_ved]).strip().upper() if col_ved and pd.notna(row.get(col_ved)) else "",
                "placa": str(row[col_placa]).strip() if col_placa and pd.notna(row.get(col_placa)) else "",
                "fornecedor": str(row[col_forn]).strip() if col_forn and pd.notna(row.get(col_forn)) else "",
                "valor": round(valor, 2),
            }
        )
    linhas.sort(key=lambda x: -x["valor"])
    return linhas


def _linhas_investimento_estoque(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    cm = dm._get_case_insensitive_column_map(df.columns)
    col_item = cm.get("descitemd")
    col_grupo = cm.get("descgrupod")
    col_cod = cm.get("coditem")
    col_saldo = cm.get("saldo")
    col_val = cm.get("valor_estoque")
    linhas: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        valor = float(pd.to_numeric(row.get(col_val), errors="coerce") or 0) if col_val else 0.0
        if valor == 0:
            continue
        saldo = float(pd.to_numeric(row.get(col_saldo), errors="coerce") or 0) if col_saldo else 0.0
        coditem = row.get(col_cod) if col_cod else None
        linhas.append(
            {
                "coditem": int(coditem) if col_cod and pd.notna(coditem) else coditem,
                "item": str(row[col_item]).strip() if col_item and pd.notna(row.get(col_item)) else "",
                "grupo": str(row[col_grupo]).strip() if col_grupo and pd.notna(row.get(col_grupo)) else "",
                "saldo": round(saldo, 4),
                "valor": round(valor, 2),
            }
        )
    linhas.sort(key=lambda x: -x["valor"])
    return linhas


def _status_vencimento_financeiro(data_venc) -> str:
    if data_venc is None or (isinstance(data_venc, float) and pd.isna(data_venc)):
        return "Sem data"
    try:
        venc = pd.Timestamp(data_venc).normalize()
    except Exception:
        return "Sem data"
    hoje = pd.Timestamp.now().normalize()
    ontem = hoje - pd.Timedelta(days=1)
    if venc < hoje:
        return "Vencido"
    if venc > ontem:
        return "A vencer"
    return "No prazo"


def _linhas_financeiro_pagar(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    cm = dm._get_case_insensitive_column_map(df.columns)
    df_ab = dm._filtrar_financeiro_linhas_periodo(df, "pagar")
    if df_ab.empty:
        return []
    linhas = []
    for _, row in df_ab.iterrows():
        val = float(pd.to_numeric(row.get(cm.get("liquidoitemnota", "liquidoitemnota")), errors="coerce") or 0)
        if val == 0:
            continue
        venc_raw = row.get(cm.get("datavenc", "datavenc"))
        status = _status_vencimento_financeiro(venc_raw)
        linhas.append(
            {
                "documento": f"NF {row.get(cm.get('numnota', 'numnota'), '—')}/{row.get(cm.get('serie', 'serie'), '')}".strip("/"),
                "codnota": row.get(cm.get("codnota")),
                "vencimento": _fmt_data(venc_raw),
                "filial": str(row.get(cm.get("nomefilial", "nomefilial"), "")).strip(),
                "fornecedor": str(row.get(cm.get("nomefornecedor", "nomefornecedor"), "")).strip(),
                "status": status,
                "valor": round(val, 2),
                "tipo": "AP",
            }
        )
    linhas.sort(key=lambda x: -x["valor"])
    return linhas


def _linhas_financeiro_receber(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    cm = dm._get_case_insensitive_column_map(df.columns)
    df_ab = dm._filtrar_financeiro_linhas_periodo(df, "receber")
    if df_ab.empty:
        return []
    linhas = []
    for _, row in df_ab.iterrows():
        val = float(pd.to_numeric(row.get(cm.get("valorvenc", "valorvenc")), errors="coerce") or 0)
        if val == 0:
            continue
        venc_raw = row.get(cm.get("datavenc", "datavenc"))
        status = _status_vencimento_financeiro(venc_raw)
        linhas.append(
            {
                "documento": f"Dup. {row.get(cm.get('codduplicatareceber', 'codduplicatareceber'), '—')}",
                "codnota": row.get(cm.get("codfatura")),
                "vencimento": _fmt_data(venc_raw),
                "filial": "",
                "cliente": str(row.get(cm.get("nomecliente", "nomecliente"), "")).strip(),
                "status": status,
                "valor": round(val, 2),
                "tipo": "AR",
            }
        )
    linhas.sort(key=lambda x: -x["valor"])
    return linhas


def _expense_data(filtered: dict) -> dict:
    return dm._get_final_expense_dataframes(
        filtered["df_viagens_cliente"],
        filtered["df_despesas_filtrado"],
        filtered["df_flags"],
        filtered["df_acerto_motorista_raw"],
    )


def _resumo_custo_operacional(
    filtered: dict,
    apartamento_id: int,
    placa_filter: str,
    start_date,
    end_date,
    filial_filter: list,
    tipo_negocio_filter: str,
    unidade_embarque_filter: list | None = None,
) -> list[dict[str, Any]]:
    expense_data = _expense_data(filtered)
    df_custo_previa = expense_data.get("custo_previa", pd.DataFrame())
    df_custo_nota = expense_data.get("custo_nota", pd.DataFrame())
    df_despesas_gerais = expense_data.get("despesas", pd.DataFrame())
    df_tipo_d = dm._calcular_df_tipo_d(
        filtered["df_despesas_raw"],
        filtered["df_flags"],
        start_date,
        end_date,
        filial_filter,
        tipo_negocio_filter,
        unidade_embarque_filter,
    )

    custo_previa = float(df_custo_previa["valor_calculado"].sum()) if not df_custo_previa.empty else 0.0
    custo_nota = float(df_custo_nota["valor_calculado"].sum()) if not df_custo_nota.empty else 0.0
    custo_viagem = custo_previa + custo_nota
    despesas_gerais = float(df_despesas_gerais["valor_calculado"].sum()) if not df_despesas_gerais.empty else 0.0
    tipo_d = float(dm._total_tipo_d_com_rateio(df_tipo_d, placa_filter, apartamento_id))

    return [
        {"label": "Custo prévia (CT-e)", "valor": round(custo_previa, 2)},
        {"label": "Custo notas (itemnota)", "valor": round(custo_nota, 2)},
        {"label": "Custo de viagem (total)", "valor": round(custo_viagem, 2)},
        {"label": "Despesas gerais (nota)", "valor": round(despesas_gerais, 2)},
        {"label": "Despesas tipo D", "valor": round(tipo_d, 2)},
        {"label": "Total custos operacionais", "valor": round(custo_viagem + despesas_gerais + tipo_d, 2)},
    ]


def _resumo_resultado(
    filtered: dict,
    apartamento_id: int,
    placa_filter: str,
    start_date,
    end_date,
    filial_filter: list,
    tipo_negocio_filter: str,
    unidade_embarque_filter: list | None = None,
) -> list[dict[str, Any]]:
    df_base = _base_viagens_fat(filtered)
    if df_base.empty:
        receita = 0.0
    else:
        cv = dm._get_case_insensitive_column_map(df_base.columns)
        if "receita" in cv:
            receita = float(pd.to_numeric(df_base[cv["receita"]], errors="coerce").fillna(0).sum())
        elif cv.get("freteempresa"):
            receita = float(
                pd.to_numeric(df_base[cv["freteempresa"]], errors="coerce").fillna(0).sum()
            )
        else:
            receita = 0.0
    custos = _resumo_custo_operacional(
        filtered,
        apartamento_id,
        placa_filter,
        start_date,
        end_date,
        filial_filter,
        tipo_negocio_filter,
        unidade_embarque_filter,
    )
    total_custos = custos[-1]["valor"] if custos else 0.0
    resultado = receita - total_custos
    margem = (resultado / receita * 100) if receita > 0 else 0.0
    return [
        {"label": "Receita de frete", "valor": round(receita, 2)},
        *custos,
        {"label": "Resultado líquido", "valor": round(resultado, 2)},
        {"label": "Margem sobre frete (%)", "valor": round(margem, 2)},
    ]


def _dre_filtrado(
    filtered: dict,
    cliente: Optional[str],
    rota: Optional[str],
    numero_cte: Optional[str] = None,
    apartamento_id: int | None = None,
) -> tuple[pd.DataFrame, dict]:
    aid = apartamento_id or 0
    df_dre = dm._df_viagens_com_receita(
        filtered.get("df_viagens_cliente", pd.DataFrame()),
        aid,
        filtered.get("df_acerto_motorista_raw"),
    )
    if df_dre.empty:
        df_base = _base_viagens_fat(filtered)
        if df_base.empty:
            return pd.DataFrame(), {}
        df_dre = dre.aplicar_dre_em_dataframe(
            df_base,
            filtered.get("df_acerto_motorista_raw"),
            dre_opts=obter_dre_opts(aid),
        )
    cv = dm._get_case_insensitive_column_map(df_dre.columns)
    df_dre = _merge_num_conhec(df_dre, filtered.get("df_fat_filtrado"))

    if numero_cte:
        col_num = cv.get("numero")
        if col_num:
            try:
                n_alvo = int(str(numero_cte).strip())
                nums = pd.to_numeric(df_dre[col_num], errors="coerce")
                df_dre = df_dre[nums == n_alvo]
            except (TypeError, ValueError):
                pass

    if cliente and cv.get("nomecliente"):
        col = cv["nomecliente"]
        serie = df_dre[col].astype(str).str.strip()
        mask = serie.str.upper() == cliente.strip().upper()
        if not mask.any():
            prefix = cliente.strip().upper()[:40]
            mask = serie.str.upper().str.startswith(prefix)
        df_dre = df_dre[mask]

    if rota:
        orig = cv.get("cidorigemformat")
        dest = cv.get("ciddestinoformat")
        if orig and dest:
            df_dre = df_dre.copy()
            df_dre["_rota"] = (
                df_dre[orig].fillna("?").astype(str).str.strip()
                + " → "
                + df_dre[dest].fillna("?").astype(str).str.strip()
            )
            df_dre = df_dre[df_dre["_rota"] == rota.strip()]

    return df_dre, cv


def get_bi_audit_data(
    apartamento_id: int,
    metric: str,
    start_date,
    end_date,
    placa_filter: str,
    filial_filter: list,
    tipo_negocio_filter: str,
    cliente: Optional[str] = None,
    rota: Optional[str] = None,
    periodo_label: Optional[str] = None,
    numero_cte: Optional[str] = None,
    unidade_embarque_filter: list | None = None,
    embarcador_filter: str = "Todos",
) -> dict[str, Any]:
    metric = (metric or "").strip().lower()
    if metric not in METRICAS:
        return {"error": f"Métrica inválida: {metric}"}

    dm.sync_expense_groups_if_needed(apartamento_id)
    start_date, end_date = dm.resolver_intervalo_consulta(apartamento_id, start_date, end_date)
    if periodo_label:
        start_date, end_date = narrow_dates_by_periodo_label(periodo_label, start_date, end_date)
    filtered = dm._obter_dados_filtrados_mestre(
        apartamento_id,
        start_date,
        end_date,
        placa_filter,
        filial_filter,
        tipo_negocio_filter,
        unidade_embarque_filter,
        embarcador_filter,
    )

    meta = METRICAS[metric]
    from app.utils.helpers import format_date_br

    filtros = {
        "start_date": format_date_br(start_date) if start_date else "",
        "end_date": format_date_br(end_date) if end_date else "",
        "placa": placa_filter,
        "filial": filial_filter or [],
        "unidade_embarque": unidade_embarque_filter or [],
        "embarcador": embarcador_filter,
        "tipo_negocio": tipo_negocio_filter,
    }
    if cliente:
        filtros["cliente"] = cliente
    if rota:
        filtros["rota"] = rota
    if periodo_label:
        filtros["periodo"] = periodo_label
    if numero_cte:
        filtros["numero_cte"] = numero_cte

    expense_data = _expense_data(filtered)
    df_dre, cv = _dre_filtrado(filtered, cliente, rota, numero_cte, apartamento_id)

    linhas: list[dict[str, Any]] = []
    linhas_notas: list[dict[str, Any]] = []
    resumo: list[dict[str, Any]] = []
    total_calculado = 0.0

    if metric == "receita_frete":
        linhas = _linhas_cte(df_dre, cv, metric)
        total_calculado = round(sum(x["receita"] for x in linhas), 2)

    elif metric == "custo_previa_conhecimento":
        linhas = _linhas_cte(df_dre, cv, "custo_previa_conhecimento")
        total_calculado = round(sum(x["custo_previa"] for x in linhas), 2)

    elif metric == "custo_nota_itemnota":
        linhas_notas = _linhas_itemnota(expense_data.get("custo_nota", pd.DataFrame()))
        total_calculado = round(sum(x["valor"] for x in linhas_notas), 2)

    elif metric == "despesas_gerais":
        linhas_notas = _linhas_itemnota(expense_data.get("despesas", pd.DataFrame()))
        total_calculado = round(sum(x["valor"] for x in linhas_notas), 2)

    elif metric == "despesas_tipo_d":
        df_tipo_d = dm._calcular_df_tipo_d(
            filtered["df_despesas_raw"],
            filtered["df_flags"],
            start_date,
            end_date,
            filial_filter,
            tipo_negocio_filter,
            unidade_embarque_filter,
        )
        fator = dm._fator_rateio_placas_proprias(placa_filter, apartamento_id)
        linhas_notas = _linhas_itemnota(df_tipo_d)
        if fator != 1.0:
            for ln in linhas_notas:
                ln["valor"] = round(ln["valor"] * fator, 2)
        total_calculado = round(sum(x["valor"] for x in linhas_notas), 2)

    elif metric == "custo_viagem":
        linhas = _linhas_cte(df_dre, cv, "custo_previa_conhecimento")
        linhas_notas = _linhas_itemnota(expense_data.get("custo_nota", pd.DataFrame()))
        cp = round(sum(x["custo_previa"] for x in linhas), 2)
        cn = round(sum(x["valor"] for x in linhas_notas), 2)
        resumo = [
            {"label": "Custo prévia CT-e", "valor": cp},
            {"label": "Custo notas", "valor": cn},
            {"label": "Total custo viagem", "valor": round(cp + cn, 2)},
        ]
        total_calculado = resumo[-1]["valor"]

    elif metric == "custo_operacional":
        resumo = _resumo_custo_operacional(
            filtered,
            apartamento_id,
            placa_filter,
            start_date,
            end_date,
            filial_filter,
            tipo_negocio_filter,
            unidade_embarque_filter,
        )
        total_calculado = resumo[-1]["valor"] if resumo else 0.0
        linhas = _linhas_cte(df_dre, cv, "custo_operacional")
        linhas_notas = (
            _linhas_itemnota(expense_data.get("custo_nota", pd.DataFrame()))
            + _linhas_itemnota(expense_data.get("despesas", pd.DataFrame()))
            + _linhas_itemnota(expense_data.get("tipo_d", pd.DataFrame()))
        )

    elif metric == "receita_comercio":
        df_c = dm.get_itens_comercio_df(
            filtered["df_despesas_raw"],
            start_date,
            end_date,
            filial_filter,
            "venda",
            unidade_embarque_filter,
        )
        linhas_notas = _linhas_itemnota(df_c)
        total_calculado = round(sum(x["valor"] for x in linhas_notas), 2)

    elif metric == "despesa_comercio":
        df_c = dm.get_itens_comercio_df(
            filtered["df_despesas_raw"],
            start_date,
            end_date,
            filial_filter,
            "null",
            unidade_embarque_filter,
        )
        linhas_notas = _linhas_itemnota(df_c)
        total_calculado = round(sum(x["valor"] for x in linhas_notas), 2)

    elif metric == "investimento":
        df_inv = dm.get_itens_investimento_df(
            filtered["df_despesas_raw"],
            start_date,
            end_date,
            filial_filter,
            unidade_embarque_filter,
        )
        linhas_notas = _linhas_itemnota(df_inv)
        total_calculado = round(sum(x["valor"] for x in linhas_notas), 2)

    elif metric == "investimento_estoque":
        df_est = dm.get_investimento_estoque_df(apartamento_id)
        linhas_notas = _linhas_investimento_estoque(df_est)
        total_calculado = round(sum(x["valor"] for x in linhas_notas), 2)

    elif metric == "resultado_liquido":
        resumo = _resumo_resultado(
            filtered,
            apartamento_id,
            placa_filter,
            start_date,
            end_date,
            filial_filter,
            tipo_negocio_filter,
            unidade_embarque_filter,
        )
        total_calculado = next((r["valor"] for r in resumo if r["label"] == "Resultado líquido"), 0.0)

    elif metric == "margem_frete":
        resumo = _resumo_resultado(
            filtered,
            apartamento_id,
            placa_filter,
            start_date,
            end_date,
            filial_filter,
            tipo_negocio_filter,
            unidade_embarque_filter,
        )
        total_calculado = next((r["valor"] for r in resumo if "Margem" in r["label"]), 0.0)

    elif metric == "margem_cliente":
        if not cliente:
            return {"error": "Informe o cliente (clique na barra do gráfico)."}
        linhas = _linhas_margem_cliente(df_dre, cv)
        rec = sum(x["receita"] for x in linhas)
        custo = sum(x["custo_previa"] for x in linhas)
        lucro = rec - custo
        margem = (lucro / rec * 100) if rec > 0 else 0.0
        resumo = [
            {"label": f"Cliente — {cliente}", "valor": 0},
            {"label": "Receita total", "valor": round(rec, 2)},
            {"label": "Custo prévia total", "valor": round(custo, 2)},
            {"label": "Lucro estimado", "valor": round(lucro, 2)},
            {"label": "Margem %", "valor": round(margem, 2)},
        ]
        total_calculado = round(margem, 2)

    elif metric == "contas_pagar":
        linhas_notas = _linhas_financeiro_pagar(filtered["df_contas_pagar_raw"])
        total_calculado = round(sum(x["valor"] for x in linhas_notas), 2)

    elif metric == "contas_receber":
        linhas_notas = _linhas_financeiro_receber(filtered["df_contas_receber_raw"])
        total_calculado = round(sum(x["valor"] for x in linhas_notas), 2)

    return {
        "metric": metric,
        "titulo": meta["titulo"],
        "formula": meta["formula"],
        "listagem": meta.get("listagem", "cte"),
        "total_calculado": total_calculado,
        "filtros": filtros,
        "resumo": resumo,
        "linhas": linhas,
        "linhas_notas": linhas_notas,
        "qtd_ctes": len(linhas),
        "qtd_notas": len(linhas_notas),
    }
