"""Visão comercial — análises 1–6 (BD SATI via data_manager)."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from app.data import data_manager as dm
from app.core import dre_viagem as dre

ANALISES = {
    1: {
        "titulo": "Margem por cliente",
        "subtitulo": "Rentabilidade da carteira",
        "pergunta": (
            "Quais clientes faturam muito mas deixam pouco lucro? "
            "Vale renegociar tabela ou reduzir atendimento?"
        ),
        "icone": "purple",
        "emoji": "👥",
    },
    2: {
        "titulo": "Receita vs custo por rota",
        "subtitulo": "Origem → destino",
        "pergunta": (
            "Quais rotas precisam de reajuste de frete ou não devem ser aceitas no agenciamento?"
        ),
        "icone": "blue",
        "emoji": "🗺️",
    },
    3: {
        "titulo": "Ticket médio por cliente",
        "subtitulo": "Evolução no período",
        "pergunta": (
            "O cliente está crescendo em volume com frete menor (pressão de preço) ou em valor real?"
        ),
        "icone": "green",
        "emoji": "🎫",
    },
    4: {
        "titulo": "Concentração de receita",
        "subtitulo": "Curva de Pareto (80/20)",
        "pergunta": (
            "Dependemos demais de 2–3 clientes? Qual o risco se perdermos um contrato?"
        ),
        "icone": "red",
        "emoji": "📊",
    },
    5: {
        "titulo": "Frota própria vs agenciamento",
        "subtitulo": "Comparativo por tipo de frete",
        "pergunta": (
            "Vale mais investir em frota própria ou manter terceiros nesta rota/cliente?"
        ),
        "icone": "blue",
        "emoji": "🚛",
    },
    6: {
        "titulo": "Spread frete empresa × motorista",
        "subtitulo": "Margem operacional do frete",
        "pergunta": (
            "O spread cobre custo fixo e margem desejada? Há motorista ou rota com spread negativo?"
        ),
        "icone": "purple",
        "emoji": "💰",
    },
    7: {
        "titulo": "Comércio",
        "subtitulo": "Receita e despesa do ramo COMERCIO",
        "pergunta": (
            "Quanto o braço comercial fatura (NFe Venda) versus entradas sem tipo NFe? "
            "O resultado do comércio está positivo no período?"
        ),
        "icone": "green",
        "emoji": "🏪",
    },
}

ANALISES_LIST = [{"id": k, **v} for k, v in sorted(ANALISES.items())]


def _fmt_brl(val: float) -> str:
    return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_pct(val: float) -> str:
    return f"{val:.1f}%".replace(".", ",")


def _num(series):
    return pd.to_numeric(series, errors="coerce").fillna(0.0)


def _custo_operacional_total(
    filtered_data: dict,
    apartamento_id: int,
    placa_filter: str,
    start_date: datetime,
    end_date: datetime,
    filial_filter: list,
    tipo_negocio_filter: str,
) -> float:
    df_viagens = filtered_data["df_viagens_cliente"]
    df_despesas_filtrado = filtered_data["df_despesas_filtrado"]
    df_flags = filtered_data["df_flags"]
    df_acerto = filtered_data["df_acerto_motorista_raw"]
    df_despesas_raw = filtered_data["df_despesas_raw"]

    expense = dm._get_final_expense_dataframes(
        df_viagens, df_despesas_filtrado, df_flags, df_acerto
    )
    custo_viagem = (
        expense["custos"]["valor_calculado"].sum()
        if not expense["custos"].empty
        else 0.0
    )
    despesas_gerais = (
        expense["despesas"]["valor_calculado"].sum()
        if not expense["despesas"].empty
        else 0.0
    )
    df_tipo_d = dm._calcular_df_tipo_d(
        df_despesas_raw, df_flags, start_date, end_date, filial_filter, tipo_negocio_filter
    )
    tipo_d = dm._total_tipo_d_com_rateio(df_tipo_d, placa_filter, apartamento_id)
    return float(custo_viagem + despesas_gerais + tipo_d)


def _base_viagens_fat(filtered_data: dict) -> pd.DataFrame:
    """Viagens com campos do conhecimento para DRE (flags permitefaturar / pagarConhecimento)."""
    df_v = filtered_data["df_viagens_cliente"]
    if df_v.empty:
        return pd.DataFrame()
    cv = dm._get_case_insensitive_column_map(df_v.columns)
    if "numero" not in cv or "freteempresa" not in cv:
        return pd.DataFrame()
    cols_v = [cv["numero"], cv["freteempresa"]]
    for key in (
        "nomecliente",
        "cidorigemformat",
        "ciddestinoformat",
        "dataviagemmotorista",
        "tipofrete",
        "nomemotorista",
        "fretemotorista",
        "permitefaturar",
        "pagarconhecimento",
        "valorpedagio",
        "pedagioembutidofrete",
        "valoricms",
        "icmsembutido",
        "premioseguro",
        "premioseguro2",
        "descsegurosaldo",
        "valorquebra",
        "comissao",
    ):
        if key in cv:
            cols_v.append(cv[key])
    df = df_v[cols_v].drop_duplicates(subset=[cv["numero"]]).copy()
    fe_col = cv["freteempresa"]
    df = df[pd.to_numeric(df[fe_col], errors="coerce").fillna(0) > 0]
    return df


def _alocar_custo_proporcional(df: pd.DataFrame, dim_col: str, custo_total: float) -> pd.DataFrame:
    if df.empty or dim_col not in df.columns:
        return pd.DataFrame()
    grp = (
        df.groupby(dim_col, dropna=False)
        .agg(receita=("receita", "sum"), viagens=("receita", "count"))
        .reset_index()
    )
    grp[dim_col] = grp[dim_col].fillna("(sem nome)").astype(str).str.strip()
    grp = grp[grp[dim_col] != ""]
    total_rec = grp["receita"].sum()
    if total_rec <= 0:
        grp["custo_alocado"] = 0.0
        grp["lucro"] = 0.0
        grp["margem_pct"] = 0.0
        return grp
    grp["custo_alocado"] = custo_total * (grp["receita"] / total_rec)
    grp["lucro"] = grp["receita"] - grp["custo_alocado"]
    grp["margem_pct"] = np.where(grp["receita"] > 0, grp["lucro"] / grp["receita"] * 100, 0)
    return grp.sort_values("receita", ascending=False)


def _kpis_margem(grp: pd.DataFrame, dim_label: str) -> list:
    if grp.empty:
        return [
            {"label": f"Total {dim_label}", "value": "0", "hint": "Sem dados no período"},
            {"label": "Receita total", "value": "R$ 0", "hint": ""},
            {"label": "Margem média", "value": "0%", "hint": ""},
        ]
    neg = int((grp["margem_pct"] < 0).sum())
    rec_total = grp["receita"].sum()
    margem_media = (grp["lucro"].sum() / rec_total * 100) if rec_total > 0 else 0
    pior = grp.sort_values("margem_pct").iloc[0]
    dim_col = grp.columns[0]
    return [
        {"label": f"Total {dim_label}", "value": str(len(grp)), "hint": f"{neg} com margem negativa"},
        {"label": "Receita total", "value": _fmt_brl(rec_total), "hint": "permitefaturar = S"},
        {"label": "Margem média", "value": _fmt_pct(margem_media), "hint": "DRE: receita se permitefaturar; custo se pagarConhecimento = S"},
        {
            "label": "Menor margem",
            "value": _fmt_pct(float(pior["margem_pct"])),
            "hint": str(pior[dim_col])[:40],
        },
    ]


def _kpis_receita_custo(grp: pd.DataFrame, dim_label: str) -> list:
    if grp.empty:
        return _kpis_margem(grp, dim_label)
    neg = int((grp["lucro"] < 0).sum())
    pior = grp.sort_values("lucro").iloc[0]
    dim_col = grp.columns[0]
    rec_total = grp["receita"].sum()
    custo_total = grp["custo_alocado"].sum()
    return [
        {"label": f"Total {dim_label}", "value": str(len(grp)), "hint": f"{neg} com prejuízo estimado"},
        {"label": "Receita total", "value": _fmt_brl(rec_total), "hint": ""},
        {"label": "Custo prévia", "value": _fmt_brl(custo_total), "hint": "Motorista, ICMS, seguro e quebra por CT-e"},
        {
            "label": "Pior resultado",
            "value": _fmt_brl(float(pior["lucro"])),
            "hint": str(pior[dim_col])[:40],
        },
    ]


def _chart_hbar_margem(grp: pd.DataFrame, dim_col: str, top: int = 12) -> dict:
    top_df = grp.head(top).sort_values("margem_pct", ascending=True)
    return {
        "mode": "margem_hbar",
        "type": "bar",
        "indexAxis": "y",
        "labels": [str(x)[:42] for x in top_df[dim_col]],
        "datasets": [
            {
                "label": "Margem %",
                "unit": "percent",
                "data": [round(float(x), 1) for x in top_df["margem_pct"]],
            },
        ],
    }


def _chart_hbar_receita_custo(grp: pd.DataFrame, dim_col: str, top: int = 12) -> dict:
    top_df = grp.head(top).sort_values("receita", ascending=True)
    return {
        "mode": "receita_custo_hbar",
        "type": "bar",
        "indexAxis": "y",
        "labels": [str(x)[:42] for x in top_df[dim_col]],
        "datasets": [
            {
                "label": "Receita (R$)",
                "unit": "currency",
                "data": [round(float(x), 2) for x in top_df["receita"]],
            },
            {
                "label": "Custo prévia (R$)",
                "unit": "currency",
                "data": [round(float(x), 2) for x in top_df["custo_alocado"]],
            },
        ],
    }


def _chart_receita_custo_bar(grp: pd.DataFrame, dim_col: str) -> dict:
    return {
        "mode": "receita_custo_bar",
        "type": "bar",
        "labels": [str(x) for x in grp[dim_col]],
        "datasets": [
            {
                "label": "Receita (R$)",
                "unit": "currency",
                "data": [round(float(x), 2) for x in grp["receita"]],
            },
            {
                "label": "Custo prévia (R$)",
                "unit": "currency",
                "data": [round(float(x), 2) for x in grp["custo_alocado"]],
            },
        ],
    }


def _chart_pareto(grp: pd.DataFrame, dim_col: str, top: int = 15) -> dict:
    top_df = grp.head(top)
    return {
        "mode": "pareto",
        "type": "bar",
        "labels": [str(x)[:30] for x in top_df[dim_col]],
        "datasets": [
            {
                "label": "Faturamento (R$)",
                "unit": "currency",
                "data": [round(float(x), 2) for x in top_df["receita"]],
            },
            {
                "label": "% acumulado",
                "unit": "percent",
                "yAxis": "percent",
                "data": [round(float(x), 1) for x in top_df["pct_acum"]],
            },
        ],
    }


def _chart_spread_hbar(grp: pd.DataFrame, dim_col: str) -> dict:
    top_df = grp.sort_values("spread", ascending=True)
    return {
        "mode": "spread_hbar",
        "type": "bar",
        "indexAxis": "y",
        "labels": [str(x)[:35] for x in top_df[dim_col]],
        "datasets": [
            {
                "label": "Spread total (R$)",
                "unit": "currency",
                "data": [round(float(x), 2) for x in top_df["spread"]],
            },
        ],
    }


def _chart_comercio_mensal(mensal: pd.DataFrame) -> dict | None:
    if mensal.empty:
        return None
    labels = [
        pd.Period(p).to_timestamp().strftime("%b/%Y")
        for p in mensal["periodo"]
    ]
    return {
        "mode": "receita_custo_bar",
        "type": "bar",
        "labels": labels,
        "datasets": [
            {
                "label": "Receita comércio (R$)",
                "unit": "currency",
                "data": [round(float(x), 2) for x in mensal["receita"]],
            },
            {
                "label": "Despesa comércio (R$)",
                "unit": "currency",
                "data": [round(float(x), 2) for x in mensal["despesa"]],
            },
        ],
    }


def _count_notas_comercio(
    df_raw: pd.DataFrame,
    start_date,
    end_date,
    filial_filter,
    tiponfe_mode: str,
) -> int:
    if df_raw.empty:
        return 0
    df = dm.apply_filters_to_df(df_raw, start_date, end_date, "Todos", filial_filter)
    col_map = dm._get_case_insensitive_column_map(df.columns)
    if tiponfe_mode == "venda":
        df = dm._filtrar_itens_receita_comercio(df, col_map)
    else:
        df = dm._filtrar_itens_despesa_comercio(df, col_map)
    cod_nota = col_map.get("codnota")
    if not cod_nota or df.empty:
        return 0
    return int(df[cod_nota].nunique())


def _analise_comercio(
    meta: dict,
    filtered: dict,
    start_date,
    end_date,
    filial_filter: list,
) -> dict:
    df_raw = filtered["df_despesas_raw"]
    receita = dm._total_itens_comercio(df_raw, start_date, end_date, filial_filter, "venda")
    despesa = dm._total_itens_comercio(df_raw, start_date, end_date, filial_filter, "null")
    resultado = receita - despesa
    mensal = dm.get_comercio_mensal(df_raw, start_date, end_date, filial_filter)
    notas_rec = _count_notas_comercio(df_raw, start_date, end_date, filial_filter, "venda")
    notas_desp = _count_notas_comercio(df_raw, start_date, end_date, filial_filter, "null")
    return {
        "analise": meta,
        "kpis": [
            {
                "label": "Receita comércio",
                "value": _fmt_brl(receita),
                "hint": "COMERCIO · despesa=N · tiponfe=0 · tipo=0",
                "audit_metric": "receita_comercio",
            },
            {
                "label": "Despesa comércio",
                "value": _fmt_brl(despesa),
                "hint": "COMERCIO · despesa=S · tiponfe=0",
                "audit_metric": "despesa_comercio",
            },
            {
                "label": "Resultado comércio",
                "value": _fmt_brl(resultado),
                "hint": "Receita − despesa",
            },
            {
                "label": "Notas no período",
                "value": f"{notas_rec} vendas · {notas_desp} despesas",
                "hint": "Distintas por codnota",
            },
        ],
        "audit_pills": [
            {"label": "Receita comércio", "metric": "receita_comercio", "pill": "receita"},
            {"label": "Despesa comércio", "metric": "despesa_comercio", "pill": "geral"},
        ],
        "chart": _chart_comercio_mensal(mensal),
        "chart_title": "Receita vs despesa comércio por mês",
        "chart_subtitle": (
            "Ramo COMERCIO — receita: despesa=N + tiponfe=0 + tipo=0; "
            "despesa: despesa=S + tiponfe=0. Entrada estoque (tipo vazio) não entra."
        ),
    }


def get_gestao_comercial_data(
    apartamento_id: int,
    analise_id: int,
    start_date,
    end_date,
    placa_filter: str,
    filial_filter: list,
    tipo_negocio_filter: str,
) -> dict:
    if analise_id not in ANALISES:
        return {"error": "Análise inválida"}

    dm.sync_expense_groups_if_needed(apartamento_id)
    start_date, end_date = dm.resolver_intervalo_consulta(apartamento_id, start_date, end_date)
    filtered = dm._obter_dados_filtrados_mestre(
        apartamento_id, start_date, end_date, placa_filter, filial_filter, tipo_negocio_filter
    )
    meta = dict(ANALISES[analise_id])
    meta["id"] = analise_id

    if analise_id == 7:
        return _analise_comercio(meta, filtered, start_date, end_date, filial_filter)

    df = _base_viagens_fat(filtered)

    if df.empty:
        return {
            "analise": meta,
            "kpis": [{"label": "Dados", "value": "—", "hint": "Nenhuma viagem faturada no período"}],
            "chart": None,
            "chart_secondary": None,
        }

    cv = dm._get_case_insensitive_column_map(df.columns)
    df_dre = dre.aplicar_dre_em_dataframe(df, filtered.get("df_acerto_motorista_raw"))

    if analise_id == 1:
        col = cv.get("nomecliente", "nomecliente")
        grp = dre.agrupar_dre(df_dre, col)
        return {
            "analise": meta,
            "kpis": _kpis_margem(grp, "clientes"),
            "chart": _chart_hbar_margem(grp, col),
            "chart_title": "Margem por cliente (DRE conhecimento)",
        }

    if analise_id == 2:
        orig = cv.get("cidorigemformat", "cidorigemformat")
        dest = cv.get("ciddestinoformat", "ciddestinoformat")
        df_dre = df_dre.copy()
        df_dre["rota"] = (
            df_dre[orig].fillna("?").astype(str).str.strip()
            + " → "
            + df_dre[dest].fillna("?").astype(str).str.strip()
        )
        grp = dre.agrupar_dre(df_dre, "rota")
        return {
            "analise": meta,
            "kpis": _kpis_receita_custo(grp, "rotas"),
            "chart": _chart_hbar_receita_custo(grp, "rota"),
            "chart_title": "Receita vs custo prévia por rota",
        }

    if analise_id == 3:
        col_cli = cv.get("nomecliente", "nomecliente")
        col_dt = cv.get("dataviagemmotorista", "dataviagemmotorista")
        df = df_dre.copy()
        df[col_dt] = pd.to_datetime(df[col_dt], errors="coerce")
        df = df.dropna(subset=[col_dt])
        periodo = "M" if (end_date - start_date).days > 62 else "W"
        df["periodo"] = df[col_dt].dt.to_period(periodo)
        top_clientes = (
            df.groupby(col_cli)["receita"].sum().sort_values(ascending=False).head(5).index.tolist()
        )
        labels = sorted(df["periodo"].unique())
        fmt = "%b/%Y" if periodo == "M" else "%d/%m"
        label_str = [pd.Period(p).to_timestamp().strftime(fmt) for p in labels]
        datasets = []
        for cli in top_clientes:
            sub = df[df[col_cli] == cli]
            por_periodo = sub.groupby("periodo")["receita"].agg(["sum", "count"])
            por_periodo["ticket"] = por_periodo["sum"] / por_periodo["count"].clip(lower=1)
            tickets = por_periodo["ticket"]
            datasets.append(
                {
                    "label": str(cli)[:35],
                    "data": [round(float(tickets.get(p, 0)), 2) for p in labels],
                }
            )
        ticket_geral = df["receita"].sum() / max(len(df), 1)
        variacao = 0.0
        if len(labels) >= 2 and top_clientes:
            cli0 = top_clientes[0]
            sub0 = df[df[col_cli] == cli0]
            por_p = sub0.groupby("periodo")["receita"].agg(["sum", "count"])
            por_p["ticket"] = por_p["sum"] / por_p["count"].clip(lower=1)
            vals = [float(por_p["ticket"].get(p, 0)) for p in labels if por_p["ticket"].get(p, 0) > 0]
            if len(vals) >= 2:
                variacao = (vals[-1] - vals[0]) / vals[0] * 100 if vals[0] else 0
        return {
            "analise": meta,
            "kpis": [
                {"label": "Ticket médio geral", "value": _fmt_brl(ticket_geral), "hint": "Por CT-e no período"},
                {"label": "Top clientes no gráfico", "value": str(len(top_clientes)), "hint": "5 maiores faturamentos"},
                {"label": "CT-es analisados", "value": str(len(df)), "hint": ""},
                {
                    "label": "Variação ticket #1",
                    "value": _fmt_pct(variacao),
                    "hint": str(top_clientes[0])[:35] if top_clientes else "—",
                },
            ],
            "chart": {
                "mode": "line_ticket",
                "type": "line",
                "labels": label_str,
                "datasets": datasets,
            },
            "chart_title": "Ticket médio por cliente ao longo do tempo",
        }

    if analise_id == 4:
        col = cv.get("nomecliente", "nomecliente")
        grp = df_dre.groupby(col)["receita"].sum().sort_values(ascending=False).reset_index()
        grp.columns = ["cliente", "receita"]
        total = grp["receita"].sum()
        grp["pct"] = grp["receita"] / total * 100 if total > 0 else 0
        grp["pct_acum"] = grp["pct"].cumsum()
        top3 = grp.head(3)["pct"].sum()
        top5 = grp.head(5)["pct"].sum()
        return {
            "analise": meta,
            "kpis": [
                {"label": "Clientes ativos", "value": str(len(grp)), "hint": ""},
                {"label": "Top 3 concentram", "value": _fmt_pct(top3), "hint": "do faturamento"},
                {"label": "Top 5 concentram", "value": _fmt_pct(top5), "hint": "do faturamento"},
                {
                    "label": "Cliente #1",
                    "value": _fmt_pct(float(grp.iloc[0]["pct"])),
                    "hint": str(grp.iloc[0]["cliente"])[:40],
                },
            ],
            "chart": _chart_pareto(grp, "cliente"),
            "chart_title": "Pareto — concentração de receita por cliente",
        }

    if analise_id == 5:
        col_tf = cv.get("tipofrete", "tipofrete")
        df_dre = df_dre.copy()
        df_dre["tipo_operacao"] = df_dre[col_tf].apply(dre.label_tipofrete_dre)
        grp = dre.agrupar_dre(df_dre, "tipo_operacao")
        melhor = grp.sort_values("margem_pct", ascending=False).iloc[0] if not grp.empty else None
        maior_rec = grp.sort_values("receita", ascending=False).iloc[0] if not grp.empty else None
        return {
            "analise": meta,
            "kpis": [
                {"label": "Tipos de operação", "value": str(len(grp)), "hint": ""},
                {
                    "label": "Maior receita",
                    "value": str(maior_rec["tipo_operacao"]) if maior_rec is not None else "—",
                    "hint": _fmt_brl(float(maior_rec["receita"])) if maior_rec is not None else "",
                },
                {
                    "label": "Melhor margem",
                    "value": _fmt_pct(float(melhor["margem_pct"])) if melhor is not None else "—",
                    "hint": str(melhor["tipo_operacao"]) if melhor is not None else "",
                },
                {
                    "label": "Lucro estimado total",
                    "value": _fmt_brl(float(grp["lucro"].sum())) if not grp.empty else "—",
                    "hint": "Receita − custo prévia conhecimento",
                },
            ],
            "chart": _chart_receita_custo_bar(grp, "tipo_operacao"),
            "chart_title": "Receita vs custo prévia por tipo de operação",
        }

    if analise_id == 6:
        col_mot = cv.get("nomemotorista", "nomemotorista")
        col_fm = cv.get("fretemotorista", "fretemotorista")
        df = df_dre.copy()
        if col_fm in df.columns:
            df["spread"] = df["receita"] - _num(df[col_fm])
        else:
            cf = dm._get_case_insensitive_column_map(filtered["df_fat_filtrado"].columns)
            if "fretemotorista" in cf:
                df = pd.merge(
                    df,
                    filtered["df_fat_filtrado"][[cf["numero"], cf["fretemotorista"]]],
                    on=cv.get("numero", "numero"),
                    how="left",
                )
                df["spread"] = df["receita"] - _num(df[cf["fretemotorista"]])
            else:
                df["spread"] = df["receita"]
        grp = (
            df.groupby(col_mot, dropna=False)
            .agg(
                receita=("receita", "sum"),
                spread=("spread", "sum"),
                viagens=("receita", "count"),
            )
            .reset_index()
        )
        grp[col_mot] = grp[col_mot].fillna("(sem motorista)").astype(str)
        grp["spread_medio"] = np.where(grp["viagens"] > 0, grp["spread"] / grp["viagens"], 0)
        grp = grp.sort_values("receita", ascending=False).head(12)
        spread_medio = df["spread"].sum() / max(len(df), 1)
        neg_spread = int((grp["spread"] < 0).sum())
        pior = grp.sort_values("spread").iloc[0] if not grp.empty else None
        return {
            "analise": meta,
            "kpis": [
                {"label": "Spread médio / CT-e", "value": _fmt_brl(spread_medio), "hint": "freteempresa - fretemotorista"},
                {"label": "Motoristas no top", "value": str(len(grp)), "hint": f"{neg_spread} com spread negativo"},
                {"label": "Spread total período", "value": _fmt_brl(float(df["spread"].sum())), "hint": ""},
                {
                    "label": "Menor spread",
                    "value": _fmt_brl(float(pior["spread"])) if pior is not None else "—",
                    "hint": str(pior[col_mot])[:35] if pior is not None else "",
                },
            ],
            "chart": _chart_spread_hbar(grp, col_mot),
            "chart_title": "Spread frete empresa menos motorista (top motoristas)",
        }

    return {"error": "Análise não implementada"}
