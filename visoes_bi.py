"""Visões BI adicionais — financeira, frota, operacional e cruzamentos estratégicos."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

import data_manager as dm
from gestao_comercial import (
    _alocar_custo_proporcional,
    _base_viagens_fat,
    _custo_operacional_total,
    _fmt_brl,
    _fmt_pct,
)
from visao_exploratorio import EXPLORATORIO_VISOES, get_exploratorio_data

VISOES = {
    "financeira": {
        "titulo": "Visão financeira",
        "subtitulo": "Caixa, inadimplência e contas a pagar",
        "badge": "Financeiro",
        "badge_class": "despesa",
        "analises": {
            1: {
                "titulo": "Aging de contas a receber",
                "subtitulo": "Títulos em aberto por faixa de vencimento",
                "pergunta": "Quanto está preso no cliente? Quem bloquear para nova carga?",
                "icone": "red",
                "emoji": "📅",
            },
            2: {
                "titulo": "Fluxo de caixa projetado",
                "subtitulo": "Entradas e saídas — próximos 90 dias",
                "pergunta": "Na semana que vem fecho folha e pedágio — o caixa aguenta?",
                "icone": "blue",
                "emoji": "💳",
            },
            3: {
                "titulo": "Prazo médio de recebimento",
                "subtitulo": "Atraso médio por fatura (títulos quitados)",
                "pergunta": "Qual cliente financia a operação da transportadora?",
                "icone": "purple",
                "emoji": "⏱️",
            },
            4: {
                "titulo": "Contas a pagar por vencimento",
                "subtitulo": "Duplicatas AP em aberto",
                "pergunta": "Quais pagamentos priorizar nesta semana?",
                "icone": "red",
                "emoji": "📤",
            },
        },
    },
    "frota": {
        "titulo": "Visão de frota",
        "subtitulo": "Eficiência e custo por km",
        "badge": "Frota",
        "badge_class": "receita",
        "analises": {
            1: {
                "titulo": "Custo por km rodado",
                "subtitulo": "R$/km por placa no período",
                "pergunta": "Qual veículo come a margem mesmo faturando bem?",
                "icone": "blue",
                "emoji": "🛣️",
            },
            2: {
                "titulo": "Consumo km/l por placa",
                "subtitulo": "Combustível × km rodado",
                "pergunta": "Há desvio de consumo — fraude, pneu ou manutenção?",
                "icone": "green",
                "emoji": "⛽",
            },
            3: {
                "titulo": "Manutenção por 1.000 km",
                "subtitulo": "Custo de manutenção normalizado",
                "pergunta": "Vale manter o veículo ou trocar antes que a manutenção destrua a margem?",
                "icone": "red",
                "emoji": "🔧",
            },
            4: {
                "titulo": "Utilização da frota",
                "subtitulo": "% dias com viagem no período",
                "pergunta": "Quantos caminhões pagam fixo parados?",
                "icone": "purple",
                "emoji": "📊",
            },
        },
    },
    "operacional": {
        "titulo": "Visão operacional",
        "subtitulo": "Entrega, documentos e quebra",
        "badge": "Operação",
        "badge_class": "receita",
        "analises": {
            1: {
                "titulo": "Saúde fiscal CT-e",
                "subtitulo": "Status de autorização no fluxo",
                "pergunta": "Estamos perdendo faturamento por rejeição SEFAZ?",
                "icone": "blue",
                "emoji": "📋",
            },
            2: {
                "titulo": "Índice de quebra de carga",
                "subtitulo": "Valor financeiro por mercadoria",
                "pergunta": "Há tipo de carga ou rota com sinistro recorrente?",
                "icone": "red",
                "emoji": "📦",
            },
            3: {
                "titulo": "Tempo emissão → viagem",
                "subtitulo": "Média de dias no fluxo documental",
                "pergunta": "O gargalo é fiscal, pedágio ou comprovante de descarga?",
                "icone": "green",
                "emoji": "⏳",
            },
            4: {
                "titulo": "Conclusão MDF-e",
                "subtitulo": "Manifestos encerrados vs pendentes",
                "pergunta": "Há risco de multa por manifesto não encerrado?",
                "icone": "purple",
                "emoji": "🚛",
            },
        },
    },
    "estrategica": {
        "titulo": "Cruzamentos estratégicos",
        "subtitulo": "Painéis 360 para decisão integrada",
        "badge": "Estratégico",
        "badge_class": "receita",
        "analises": {
            1: {
                "titulo": "Comercial 360",
                "subtitulo": "Cliente × receita × margem",
                "pergunta": "Onde ajustar precificação e política comercial?",
                "icone": "purple",
                "emoji": "🎯",
            },
            2: {
                "titulo": "Rentabilidade por viagem",
                "subtitulo": "CT-es com pior margem estimada",
                "pergunta": "Quais viagens microgerenciar ou recusar?",
                "icone": "red",
                "emoji": "📉",
            },
            3: {
                "titulo": "Performance do motorista",
                "subtitulo": "Faturamento × spread × quebra",
                "pergunta": "Quem bonificar ou treinar?",
                "icone": "blue",
                "emoji": "👤",
            },
            4: {
                "titulo": "Caixa transportadora",
                "subtitulo": "AR aging + projeção de saldo",
                "pergunta": "Tesouraria e crédito ao cliente — onde está o risco?",
                "icone": "green",
                "emoji": "🏦",
            },
            5: {
                "titulo": "Eficiência de frota",
                "subtitulo": "R$/km × km/l integrados",
                "pergunta": "Renovar frota ou realocar ativos?",
                "icone": "blue",
                "emoji": "⚙️",
            },
            6: {
                "titulo": "Compliance operacional",
                "subtitulo": "Documentos e prazos do fluxo",
                "pergunta": "Como reduzir multa, atraso e glosa?",
                "icone": "purple",
                "emoji": "✅",
            },
        },
    },
}
VISOES.update(EXPLORATORIO_VISOES)


def list_visoes():
    return [
        {
            "key": key,
            "titulo": v["titulo"],
            "subtitulo": v["subtitulo"],
            "analises_count": len(v["analises"]),
        }
        for key, v in VISOES.items()
    ]


def list_analises(visao_key: str):
    visao = VISOES.get(visao_key)
    if not visao:
        return []
    return [{"id": k, **meta} for k, meta in sorted(visao["analises"].items())]


def get_visao_meta(visao_key: str, analise_id: int):
    visao = VISOES.get(visao_key)
    if not visao or analise_id not in visao["analises"]:
        return None
    meta = dict(visao["analises"][analise_id])
    meta["id"] = analise_id
    meta["visao_key"] = visao_key
    meta["visao_titulo"] = visao["titulo"]
    meta["badge"] = visao["badge"]
    meta["badge_class"] = visao["badge_class"]
    return meta


def _num(series):
    return pd.to_numeric(series, errors="coerce").fillna(0.0)


def _norm_txt(series):
    return series.astype(str).str.normalize("NFKD").str.encode("ascii", "ignore").str.decode("ascii").str.upper()


def _empty(meta, hint="Sem dados no período"):
    return {
        "analise": meta,
        "kpis": [{"label": "Dados", "value": "—", "hint": hint}],
        "chart": None,
        "chart_title": "Sem dados",
    }


def _cr_abertas(df_cr: pd.DataFrame) -> pd.DataFrame:
    if df_cr.empty:
        return df_cr
    cm = dm._get_case_insensitive_column_map(df_cr.columns)
    df = df_cr.copy()
    trans = cm.get("codtransacao")
    pag = cm.get("datapagto")
    if trans and trans in df.columns:
        df = df[pd.to_numeric(df[trans], errors="coerce").isna()]
    if pag and pag in df.columns:
        df = df[df[pag].isna()]
    return df


def _cp_abertas(df_cp: pd.DataFrame) -> pd.DataFrame:
    if df_cp.empty:
        return df_cp
    cm = dm._get_case_insensitive_column_map(df_cp.columns)
    dup = cm.get("codduplicatapagar")
    trans = cm.get("codtransacao")
    pag = cm.get("datapagamento")
    liq = cm.get("liquidoitemnota")
    if not dup:
        return pd.DataFrame()
    df = df_cp[df_cp[dup].notna()].copy()
    if trans and trans in df.columns:
        df = df[pd.to_numeric(df[trans], errors="coerce").isna()]
    if pag and pag in df.columns:
        df = df[df[pag].isna()]
    return df


def _faixa_aging(dias: int) -> str:
    if dias <= 30:
        return "0–30 dias"
    if dias <= 60:
        return "31–60 dias"
    if dias <= 90:
        return "61–90 dias"
    return "90+ dias"


def _custos_por_placa(filtered: dict, apartamento_id, placa_filter, start_date, end_date, filial_filter, tipo_negocio_filter):
    df_v = filtered["df_viagens_cliente"]
    df_d = filtered["df_despesas_filtrado"]
    df_flags = filtered["df_flags"]
    df_ac = filtered["df_acerto_motorista_raw"]
    expense = dm._get_final_expense_dataframes(df_v, df_d, df_flags, df_ac)
    custos = expense["custos"]
    despesas = expense["despesas"]
    placa_col = None
    for df in (custos, despesas):
        if df.empty:
            continue
        cm = dm._get_case_insensitive_column_map(df.columns)
        placa_col = cm.get("placaveiculo")
        if placa_col:
            break
    frames = []
    for df, label in ((custos, "custo"), (despesas, "despesa")):
        if df.empty or not placa_col or placa_col not in df.columns:
            continue
        g = df.groupby(placa_col)["valor_calculado"].sum().reset_index()
        g.columns = ["placa", label]
        frames.append(g)
    if not frames:
        return pd.DataFrame(columns=["placa", "custo_total"])
    out = frames[0]
    for f in frames[1:]:
        out = out.merge(f, on="placa", how="outer")
    for c in out.columns:
        if c != "placa":
            out[c] = out[c].fillna(0)
    out["custo_total"] = out.drop(columns=["placa"]).sum(axis=1)
    return out


def _km_por_placa(filtered: dict) -> pd.DataFrame:
    df_ac = filtered["df_acerto_motorista_raw"]
    if df_ac.empty:
        df_v = filtered["df_viagens_cliente"]
        if df_v.empty:
            return pd.DataFrame(columns=["placa", "km"])
        cm = dm._get_case_insensitive_column_map(df_v.columns)
        placa = cm.get("placaveiculo")
        if not placa:
            return pd.DataFrame(columns=["placa", "km"])
        return df_v.groupby(placa).size().reset_index(name="viagens").rename(columns={placa: "placa"}).assign(km=0.0)
    cm = dm._get_case_insensitive_column_map(df_ac.columns)
    placa = cm.get("placaveiculo")
    km_col = cm.get("kmparc") or cm.get("kmrodado")
    if not placa or not km_col:
        return pd.DataFrame(columns=["placa", "km"])
    g = df_ac.groupby(placa)[km_col].apply(lambda s: _num(s).sum()).reset_index()
    g.columns = ["placa", "km"]
    return g


def _despesas_grupo_por_placa(filtered: dict, grupo_contains: str) -> pd.DataFrame:
    df = filtered["df_despesas_filtrado"]
    if df.empty:
        return pd.DataFrame(columns=["placa", "valor"])
    cm = dm._get_case_insensitive_column_map(df.columns)
    grp_col = cm.get("descgrupod")
    placa = cm.get("placaveiculo")
    val_col = "valor_calculado" if "valor_calculado" in df.columns else cm.get("liquido", "liquido")
    if not grp_col or not placa:
        return pd.DataFrame(columns=["placa", "valor"])
    sub = df[_norm_txt(df[grp_col]).str.contains(grupo_contains, na=False)]
    if sub.empty:
        return pd.DataFrame(columns=["placa", "valor"])
    if val_col not in sub.columns:
        sub = sub.assign(valor_calculado=_num(sub[cm.get("liquido", "liquido")]))
        val_col = "valor_calculado"
    g = sub.groupby(placa)[val_col].sum().reset_index()
    g.columns = ["placa", "valor"]
    return g


def _carregar_fluxo(apartamento_id, start_date, end_date):
    try:
        return dm._fetch_fluxo_viagem_sati(apartamento_id, start_date, end_date)
    except Exception:
        return pd.DataFrame()


def _financeira(meta, filtered, analise_id):
    df_cr = filtered["df_contas_receber_raw"]
    df_cp = filtered["df_contas_pagar_raw"]
    hoje = pd.Timestamp.now().normalize()

    if analise_id == 1:
        ab = _cr_abertas(df_cr)
        if ab.empty:
            return _empty(meta)
        cm = dm._get_case_insensitive_column_map(ab.columns)
        venc = cm.get("datavenc")
        val = cm.get("valorvenc")
        fat = cm.get("codfatura")
        if not venc or not val:
            return _empty(meta)
        ab = ab.copy()
        ab["venc"] = pd.to_datetime(ab[venc], errors="coerce")
        ab["valor"] = _num(ab[val])
        ab = ab.dropna(subset=["venc"])
        ab["dias"] = (hoje - ab["venc"].dt.normalize()).dt.days.clip(lower=0)
        ab["faixa"] = ab["dias"].map(_faixa_aging)
        por_faixa = ab.groupby("faixa")["valor"].sum()
        ordem = ["0–30 dias", "31–60 dias", "61–90 dias", "90+ dias"]
        labels = [f for f in ordem if f in por_faixa.index]
        top = (
            ab.groupby(fat if fat else ab.columns[0])["valor"]
            .sum()
            .sort_values(ascending=False)
            .head(10)
            if fat
            else por_faixa
        )
        return {
            "analise": meta,
            "kpis": [
                {"label": "Total em aberto", "value": _fmt_brl(float(ab["valor"].sum())), "hint": "duplicatareceber"},
                {"label": "Títulos", "value": str(len(ab)), "hint": ""},
                {"label": "Vencido 90+ dias", "value": _fmt_brl(float(ab.loc[ab["dias"] > 90, "valor"].sum())), "hint": "risco alto"},
                {"label": "Faixas", "value": str(len(labels)), "hint": "aging"},
            ],
            "chart": {
                "mode": "stacked_bar",
                "type": "bar",
                "labels": labels,
                "datasets": [{"label": "Valor em aberto (R$)", "unit": "currency", "data": [round(float(por_faixa.get(f, 0)), 2) for f in labels]}],
            },
            "chart_title": "Aging de contas a receber (global)",
            "chart_secondary": {
                "mode": "receita_custo_hbar",
                "type": "bar",
                "indexAxis": "y",
                "labels": [f"Fatura {x}" for x in top.index.astype(str)][:10],
                "datasets": [{"label": "Valor (R$)", "unit": "currency", "data": [round(float(x), 2) for x in top.values[:10]]}],
            } if fat else None,
        }

    if analise_id == 2:
        ab_cr = _cr_abertas(df_cr)
        ab_cp = _cp_abertas(df_cp)
        fim = hoje + pd.Timedelta(days=90)
        semanas = pd.date_range(hoje, fim, freq="W-MON")[:13]
        labels = [s.strftime("%d/%m") for s in semanas]
        entradas, saidas = [], []
        cm_cr = dm._get_case_insensitive_column_map(ab_cr.columns) if not ab_cr.empty else {}
        cm_cp = dm._get_case_insensitive_column_map(ab_cp.columns) if not ab_cp.empty else {}
        for sem in semanas:
            prox = sem + pd.Timedelta(days=7)
            e = s = 0.0
            if not ab_cr.empty and cm_cr.get("datavenc") and cm_cr.get("valorvenc"):
                m = (pd.to_datetime(ab_cr[cm_cr["datavenc"]], errors="coerce") >= sem) & (
                    pd.to_datetime(ab_cr[cm_cr["datavenc"]], errors="coerce") < prox
                )
                e = float(_num(ab_cr.loc[m, cm_cr["valorvenc"]]).sum())
            if not ab_cp.empty and cm_cp.get("datavenc"):
                vcol = cm_cp.get("valorvencimento") or cm_cp.get("liquidoitemnota") or cm_cp.get("valorvenc")
                if vcol:
                    m = (pd.to_datetime(ab_cp[cm_cp["datavenc"]], errors="coerce") >= sem) & (
                        pd.to_datetime(ab_cp[cm_cp["datavenc"]], errors="coerce") < prox
                    )
                    s = float(_num(ab_cp.loc[m, vcol]).sum())
            entradas.append(round(e, 2))
            saidas.append(round(s, 2))
        saldo = np.cumsum(np.array(entradas) - np.array(saidas))
        return {
            "analise": meta,
            "kpis": [
                {"label": "Entradas 90d", "value": _fmt_brl(sum(entradas)), "hint": "AR por vencimento"},
                {"label": "Saídas 90d", "value": _fmt_brl(sum(saidas)), "hint": "AP por vencimento"},
                {"label": "Saldo projetado", "value": _fmt_brl(float(saldo[-1]) if len(saldo) else 0), "hint": "entradas − saídas"},
                {"label": "Semanas", "value": str(len(labels)), "hint": ""},
            ],
            "chart": {
                "mode": "fluxo_caixa",
                "type": "line",
                "labels": labels,
                "datasets": [
                    {"label": "Entradas (AR)", "unit": "currency", "data": entradas},
                    {"label": "Saídas (AP)", "unit": "currency", "data": saidas},
                    {"label": "Saldo acumulado", "unit": "currency", "data": [round(float(x), 2) for x in saldo]},
                ],
            },
            "chart_title": "Projeção de caixa — próximos 90 dias",
        }

    if analise_id == 3:
        if df_cr.empty:
            return _empty(meta)
        cm = dm._get_case_insensitive_column_map(df_cr.columns)
        venc = cm.get("datavenc")
        pag = cm.get("datapagto")
        fat = cm.get("codfatura")
        if not venc or not pag:
            return _empty(meta)
        df = df_cr.copy()
        df["venc"] = pd.to_datetime(df[venc], errors="coerce")
        df["pag"] = pd.to_datetime(df[pag], errors="coerce")
        df = df.dropna(subset=["venc", "pag"])
        if df.empty:
            return _empty(meta, "Nenhum título quitado para calcular prazo")
        df["atraso"] = (df["pag"].dt.normalize() - df["venc"].dt.normalize()).dt.days
        grp_col = fat if fat else df.columns[0]
        g = df.groupby(grp_col)["atraso"].mean().sort_values(ascending=False).head(12)
        media = float(df["atraso"].mean())
        return {
            "analise": meta,
            "kpis": [
                {"label": "Prazo médio geral", "value": f"{media:.0f} dias", "hint": "pagamento − vencimento"},
                {"label": "Títulos quitados", "value": str(len(df)), "hint": ""},
                {"label": "Maior atraso médio", "value": f"{g.iloc[0]:.0f} dias" if len(g) else "—", "hint": str(g.index[0]) if len(g) else ""},
                {"label": "No prazo (≤0d)", "value": str(int((df["atraso"] <= 0).sum())), "hint": "títulos"},
            ],
            "chart": {
                "mode": "margem_hbar",
                "type": "bar",
                "indexAxis": "y",
                "labels": [f"Fatura {x}" for x in g.index.astype(str)],
                "datasets": [{"label": "Dias de atraso médio", "unit": "days", "data": [round(float(x), 1) for x in g.values]}],
            },
            "chart_title": "Prazo médio de recebimento por fatura",
        }

    if analise_id == 4:
        ab = _cp_abertas(df_cp)
        if ab.empty:
            return _empty(meta)
        cm = dm._get_case_insensitive_column_map(ab.columns)
        venc = cm.get("datavenc")
        val = cm.get("valorvencimento") or cm.get("liquidoitemnota")
        forn = cm.get("codforn")
        if not venc or not val:
            return _empty(meta)
        ab = ab.copy()
        ab["venc"] = pd.to_datetime(ab[venc], errors="coerce")
        ab["valor"] = _num(ab[val])
        ab = ab.dropna(subset=["venc"])
        ab["dias"] = (ab["venc"].dt.normalize() - hoje).dt.days
        ab["faixa"] = ab["dias"].apply(lambda d: _faixa_aging(max(d, 0)) if d >= 0 else "Vencido")
        por_faixa = ab.groupby("faixa")["valor"].sum()
        ordem = ["Vencido", "0–30 dias", "31–60 dias", "61–90 dias", "90+ dias"]
        labels = [f for f in ordem if f in por_faixa.index]
        return {
            "analise": meta,
            "kpis": [
                {"label": "AP em aberto", "value": _fmt_brl(float(ab["valor"].sum())), "hint": ""},
                {"label": "Duplicatas", "value": str(len(ab)), "hint": ""},
                {"label": "Vencidas", "value": _fmt_brl(float(ab.loc[ab["dias"] < 0, "valor"].sum())), "hint": "prioridade"},
                {"label": "Fornecedores", "value": str(ab[forn].nunique()) if forn else "—", "hint": ""},
            ],
            "chart": {
                "mode": "stacked_bar",
                "type": "bar",
                "labels": labels,
                "datasets": [{"label": "Valor AP (R$)", "unit": "currency", "data": [round(float(por_faixa.get(f, 0)), 2) for f in labels]}],
            },
            "chart_title": "Contas a pagar por faixa de vencimento",
        }
    return {"error": "Análise não implementada"}


def _frota(meta, filtered, apartamento_id, placa_filter, start_date, end_date, filial_filter, tipo_negocio_filter, analise_id):
    km = _km_por_placa(filtered)
    custos = _custos_por_placa(filtered, apartamento_id, placa_filter, start_date, end_date, filial_filter, tipo_negocio_filter)

    if analise_id == 1:
        if km.empty and custos.empty:
            return _empty(meta)
        m = custos.merge(km, on="placa", how="outer").fillna(0)
        m["r_km"] = np.where(m["km"] > 0, m["custo_total"] / m["km"], 0)
        m = m[m["placa"].astype(str).str.strip().isin(["", "...", "nan"]) == False]
        m_valid = m[m["km"] > 0].copy()
        media = float(m_valid["r_km"].mean()) if not m_valid.empty else 0
        m = m_valid.sort_values("r_km", ascending=False).head(12)
        return {
            "analise": meta,
            "kpis": [
                {"label": "Placas analisadas", "value": str(len(m)), "hint": ""},
                {"label": "R$/km médio", "value": _fmt_brl(media), "hint": "custo ÷ km"},
                {"label": "Pior placa", "value": _fmt_brl(float(m.iloc[0]["r_km"])) if not m.empty else "—", "hint": str(m.iloc[0]["placa"]) if not m.empty else ""},
                {"label": "Km total", "value": f"{m['km'].sum():,.0f}".replace(",", "."), "hint": "período"},
            ],
            "chart": {
                "mode": "margem_hbar",
                "type": "bar",
                "indexAxis": "y",
                "labels": [str(x) for x in m["placa"]],
                "datasets": [{"label": "R$/km", "unit": "currency", "data": [round(float(x), 2) for x in m["r_km"]]}],
            },
            "chart_title": "Custo por km rodado (top placas)",
        }

    if analise_id == 2:
        comb = _despesas_grupo_por_placa(filtered, "COMBUSTIVEL")
        if comb.empty or km.empty:
            return _empty(meta, "Sem dados de combustível ou km no período")
        m = comb.merge(km, on="placa", how="inner")
        litros_col = None
        df_d = filtered["df_despesas_filtrado"]
        cm = dm._get_case_insensitive_column_map(df_d.columns)
        if "quantidade" in cm:
            sub = df_d[_norm_txt(df_d[cm["descgrupod"]]).str.contains("COMBUSTIVEL", na=False)]
            placa = cm.get("placaveiculo")
            if placa and not sub.empty:
                lit = sub.groupby(placa)[cm["quantidade"]].apply(lambda s: _num(s).sum()).reset_index()
                lit.columns = ["placa", "litros"]
                m = m.merge(lit, on="placa", how="left")
        if "litros" not in m.columns:
            m["litros"] = m["valor"] / 5.5
        m["kml"] = np.where(m["litros"] > 0, m["km"] / m["litros"], 0)
        media_kml = float(m["kml"].mean())
        pior = m.loc[m["kml"].idxmin()] if not m.empty else None
        melhor = m.loc[m["kml"].idxmax()] if not m.empty else None
        m = m.sort_values("kml").head(12)
        return {
            "analise": meta,
            "kpis": [
                {"label": "Placas", "value": str(len(m)), "hint": "no gráfico (12 piores)"},
                {"label": "km/l médio frota", "value": f"{media_kml:.2f}".replace(".", ","), "hint": "todas com km e combustível"},
                {"label": "Melhor consumo", "value": f"{melhor['kml']:.2f}".replace(".", ",") if melhor is not None else "—", "hint": str(melhor["placa"]) if melhor is not None else ""},
                {"label": "Pior consumo", "value": f"{pior['kml']:.2f}".replace(".", ",") if pior is not None else "—", "hint": str(pior["placa"]) if pior is not None else ""},
            ],
            "chart": {
                "mode": "margem_hbar",
                "type": "bar",
                "indexAxis": "y",
                "labels": [str(x) for x in m["placa"]],
                "datasets": [{"label": "km/l", "unit": "number", "data": [round(float(x), 2) for x in m["kml"]]}],
            },
            "chart_title": "Piores consumos km/l (top 12)",
        }

    if analise_id == 3:
        manut = _despesas_grupo_por_placa(filtered, "MANUTENCAO")
        if manut.empty or km.empty:
            return _empty(meta)
        m = manut.merge(km, on="placa", how="inner")
        m["manut_k"] = np.where(m["km"] > 0, m["valor"] / m["km"] * 1000, 0)
        media_manut = float(m["manut_k"].mean())
        m = m.sort_values("manut_k", ascending=False).head(12)
        return {
            "analise": meta,
            "kpis": [
                {"label": "Placas", "value": str(len(m)), "hint": "top 12 no gráfico"},
                {"label": "Média R$/1.000 km", "value": _fmt_brl(media_manut), "hint": "frota com km no período"},
                {"label": "Pior placa", "value": _fmt_brl(float(m.iloc[0]["manut_k"])) if not m.empty else "—", "hint": str(m.iloc[0]["placa"]) if not m.empty else ""},
                {"label": "Manutenção total", "value": _fmt_brl(float(m["valor"].sum())), "hint": ""},
            ],
            "chart": {
                "mode": "margem_hbar",
                "type": "bar",
                "indexAxis": "y",
                "labels": [str(x) for x in m["placa"]],
                "datasets": [{"label": "R$/1.000 km", "unit": "currency", "data": [round(float(x), 2) for x in m["manut_k"]]}],
            },
            "chart_title": "Manutenção por 1.000 km rodado",
        }

    if analise_id == 4:
        df_v = filtered["df_viagens_cliente"]
        if df_v.empty:
            return _empty(meta)
        cm = dm._get_case_insensitive_column_map(df_v.columns)
        placa = cm.get("placaveiculo")
        dt = cm.get("dataviagemmotorista")
        if not placa or not dt:
            return _empty(meta)
        df = df_v.copy()
        df[dt] = pd.to_datetime(df[dt], errors="coerce")
        df = df.dropna(subset=[dt])
        dias_uteis = max((end_date - start_date).days, 1)
        g = df.groupby(placa)[dt].apply(lambda s: s.dt.normalize().nunique()).reset_index()
        g.columns = ["placa", "dias_viagem"]
        g["util_pct"] = g["dias_viagem"] / dias_uteis * 100
        media_util = float(g["util_pct"].mean())
        pior = g.sort_values("util_pct").iloc[0] if not g.empty else None
        g = g.sort_values("util_pct").head(12)
        return {
            "analise": meta,
            "kpis": [
                {"label": "Placas", "value": str(len(g)), "hint": "top 12 menores no gráfico"},
                {"label": "Utilização média", "value": _fmt_pct(media_util), "hint": f"todas as placas · {dias_uteis} dias"},
                {"label": "Menor utilização", "value": _fmt_pct(float(pior["util_pct"])) if pior is not None else "—", "hint": str(pior["placa"]) if pior is not None else ""},
                {"label": "Viagens totais", "value": str(len(df)), "hint": ""},
            ],
            "chart": {
                "mode": "margem_hbar",
                "type": "bar",
                "indexAxis": "y",
                "labels": [str(x) for x in g["placa"]],
                "datasets": [{"label": "Utilização %", "unit": "percent", "data": [round(float(x), 1) for x in g["util_pct"]]}],
            },
            "chart_title": "Utilização da frota (% dias com viagem)",
        }
    return {"error": "Análise não implementada"}


def _operacional(meta, filtered, apartamento_id, start_date, end_date, analise_id):
    df_fluxo = _carregar_fluxo(apartamento_id, start_date, end_date)
    df_v = filtered["df_viagens_cliente"]

    if analise_id == 1:
        if df_fluxo.empty:
            df = df_v
            cm = dm._get_case_insensitive_column_map(df.columns) if not df.empty else {}
            status_col = cm.get("ctestatus")
            if not status_col:
                return _empty(meta, "Status CT-e indisponível — use modo SATI")
            g = df[status_col].fillna("(sem status)").astype(str).value_counts()
        else:
            col = "ctestatus" if "ctestatus" in df_fluxo.columns else df_fluxo.columns[0]
            g = df_fluxo[col].fillna("(sem status)").astype(str).value_counts()
        labels = list(g.index[:8])
        return {
            "analise": meta,
            "kpis": [
                {"label": "CT-es no fluxo", "value": str(int(g.sum())), "hint": ""},
                {"label": "Status distintos", "value": str(len(g)), "hint": ""},
                {"label": "Principal status", "value": str(labels[0])[:20] if labels else "—", "hint": f"{g.iloc[0]} viagens" if len(g) else ""},
                {"label": "Cancelados/rej.", "value": str(sum(int(c) for i, c in g.items() if "CANC" in str(i).upper() or "REJ" in str(i).upper())), "hint": "aprox."},
            ],
            "chart": {"mode": "doughnut", "type": "doughnut", "labels": labels, "datasets": [{"label": "CT-es", "data": [int(x) for x in g.values[:8]]}]},
            "chart_title": "Distribuição de status CT-e",
        }

    if analise_id == 2:
        if df_v.empty:
            return _empty(meta)
        cm = dm._get_case_insensitive_column_map(df_v.columns)
        merc = cm.get("descricaomercadoria")
        quebra = cm.get("valorquebra")
        if not merc or not quebra:
            return _empty(meta)
        df = df_v.copy()
        df["qb"] = _num(df[quebra])
        df = df[df["qb"] > 0]
        if df.empty:
            return _empty(meta, "Sem registros de quebra no período")
        g = df.groupby(merc)["qb"].sum().sort_values(ascending=False).head(12)
        return {
            "analise": meta,
            "kpis": [
                {"label": "Valor quebra total", "value": _fmt_brl(float(df["qb"].sum())), "hint": ""},
                {"label": "CT-es com quebra", "value": str(len(df)), "hint": ""},
                {"label": "Mercadorias", "value": str(len(g)), "hint": ""},
                {"label": "Maior item", "value": _fmt_brl(float(g.iloc[0])), "hint": str(g.index[0])[:35]},
            ],
            "chart": {
                "mode": "receita_custo_hbar",
                "type": "bar",
                "indexAxis": "y",
                "labels": [str(x)[:35] for x in g.index],
                "datasets": [{"label": "Valor quebra (R$)", "unit": "currency", "data": [round(float(x), 2) for x in g.values]}],
            },
            "chart_title": "Quebra de carga por mercadoria",
        }

    if analise_id == 3:
        if df_fluxo.empty:
            return _empty(meta, "Fluxo SATI indisponível")
        tmp = df_fluxo.copy()
        tmp["emissao"] = pd.to_datetime(tmp.get("emissao"), errors="coerce")
        tmp["viagem"] = pd.to_datetime(tmp.get("data_viagem_motorista"), errors="coerce")
        tmp = tmp.dropna(subset=["emissao", "viagem"])
        if tmp.empty:
            return _empty(meta)
        tmp["dias"] = (tmp["viagem"].dt.normalize() - tmp["emissao"].dt.normalize()).dt.days.clip(lower=0)
        media = float(tmp["dias"].mean())
        por_placa = (
            tmp.groupby("placa")["dias"].mean().sort_values(ascending=False).head(10)
            if "placa" in tmp.columns
            else None
        )
        return {
            "analise": meta,
            "kpis": [
                {"label": "Média geral", "value": f"{media:.1f} dias".replace(".", ","), "hint": "emissão → viagem"},
                {"label": "CT-es", "value": str(len(tmp)), "hint": ""},
                {"label": "Mediana", "value": f"{tmp['dias'].median():.0f} dias", "hint": ""},
                {"label": "Acima 7 dias", "value": str(int((tmp["dias"] > 7).sum())), "hint": "alerta"},
            ],
            "chart": {
                "mode": "receita_custo_bar",
                "type": "bar",
                "labels": [str(x) for x in por_placa.index] if por_placa is not None else ["Geral"],
                "datasets": [
                    {
                        "label": "Dias médios",
                        "unit": "days",
                        "data": [round(float(x), 1) for x in (por_placa.values if por_placa is not None else [media])],
                    }
                ],
            },
            "chart_title": "Tempo médio entre emissão CT-e e viagem",
        }

    if analise_id == 4:
        if df_fluxo.empty:
            return _empty(meta)
        col = "mdfestatus" if "mdfestatus" in df_fluxo.columns else None
        if not col:
            return _empty(meta)
        g = df_fluxo[col].fillna("Pendente").astype(str).value_counts()
        enc = sum(int(cnt) for idx, cnt in g.items() if "encerr" in str(idx).lower())
        total = int(g.sum())
        pct = enc / total * 100 if total else 0
        return {
            "analise": meta,
            "kpis": [
                {"label": "Manifestos", "value": str(total), "hint": ""},
                {"label": "% encerrados", "value": _fmt_pct(pct), "hint": ""},
                {"label": "Pendentes", "value": str(total - enc), "hint": ""},
                {"label": "Status tipos", "value": str(len(g)), "hint": ""},
            ],
            "chart": {"mode": "doughnut", "type": "doughnut", "labels": list(g.index[:6]), "datasets": [{"label": "MDF-e", "data": [int(x) for x in g.values[:6]]}]},
            "chart_title": "Status de encerramento MDF-e",
        }
    return {"error": "Análise não implementada"}


def _estrategica(meta, filtered, apartamento_id, placa_filter, start_date, end_date, filial_filter, tipo_negocio_filter, analise_id):
    df_fat = _base_viagens_fat(filtered)
    custo_total = _custo_operacional_total(
        filtered, apartamento_id, placa_filter, start_date, end_date, filial_filter, tipo_negocio_filter
    )

    if analise_id == 1:
        if df_fat.empty:
            return _empty(meta)
        cv = dm._get_case_insensitive_column_map(df_fat.columns)
        col = cv.get("nomecliente", "nomecliente")
        grp = _alocar_custo_proporcional(df_fat, col, custo_total).head(10)
        return {
            "analise": meta,
            "kpis": [
                {"label": "Clientes top", "value": str(len(grp)), "hint": ""},
                {"label": "Receita top 10", "value": _fmt_brl(float(grp["receita"].sum())), "hint": ""},
                {"label": "Margem média top", "value": _fmt_pct(float(grp["lucro"].sum() / grp["receita"].sum() * 100) if grp["receita"].sum() else 0), "hint": ""},
                {"label": "AR em aberto", "value": _fmt_brl(dm._calcular_contas_receber_pendentes(filtered["df_contas_receber_raw"])), "hint": "global"},
            ],
            "chart": {
                "mode": "receita_custo_hbar",
                "type": "bar",
                "indexAxis": "y",
                "labels": [str(x)[:35] for x in grp[col]],
                "datasets": [
                    {"label": "Receita (R$)", "unit": "currency", "data": [round(float(x), 2) for x in grp["receita"]]},
                    {"label": "Lucro est. (R$)", "unit": "currency", "data": [round(float(x), 2) for x in grp["lucro"]]},
                ],
            },
            "chart_title": "Comercial 360 — top clientes (receita × lucro)",
        }

    if analise_id == 2:
        if df_fat.empty:
            return _empty(meta)
        cv = dm._get_case_insensitive_column_map(df_fat.columns)
        num = cv.get("numero", "numero")
        df = df_fat.copy()
        n = len(df)
        df["custo_al"] = custo_total / max(n, 1)
        df["lucro"] = df["receita"] - df["custo_al"]
        df["margem"] = np.where(df["receita"] > 0, df["lucro"] / df["receita"] * 100, 0)
        worst = df.sort_values("margem").head(12)
        return {
            "analise": meta,
            "kpis": [
                {"label": "CT-es", "value": str(n), "hint": ""},
                {"label": "Margem média", "value": _fmt_pct(float(df["margem"].mean())), "hint": "rateio uniforme"},
                {"label": "Piores viagens", "value": str(len(worst)), "hint": "no gráfico"},
                {"label": "Prejuízo estimado", "value": _fmt_brl(float(worst.loc[worst["lucro"] < 0, "lucro"].sum())), "hint": "top 12"},
            ],
            "chart": {
                "mode": "margem_hbar",
                "type": "bar",
                "indexAxis": "y",
                "labels": [f"CT-e {x}" for x in worst[num].astype(str)],
                "datasets": [{"label": "Margem %", "unit": "percent", "data": [round(float(x), 1) for x in worst["margem"]]}],
            },
            "chart_title": "Piores margens por CT-e",
        }

    if analise_id == 3:
        if df_fat.empty:
            return _empty(meta)
        cv = dm._get_case_insensitive_column_map(df_fat.columns)
        mot = cv.get("nomemotorista", "nomemotorista")
        fm = cv.get("fretemotorista", "fretemotorista")
        qb = cv.get("valorquebra", "valorquebra")
        df = df_fat.copy()
        df["spread"] = df["receita"] - _num(df[fm]) if fm in df.columns else df["receita"]
        df["qb"] = _num(df[qb]) if qb in df.columns else 0
        g = (
            df.groupby(mot, dropna=False)
            .agg(receita=("receita", "sum"), spread=("spread", "sum"), quebra=("qb", "sum"), viagens=("receita", "count"))
            .reset_index()
        )
        g[mot] = g[mot].fillna("(sem motorista)")
        g = g.sort_values("receita", ascending=False).head(12)
        return {
            "analise": meta,
            "kpis": [
                {"label": "Motoristas", "value": str(len(g)), "hint": ""},
                {"label": "Faturamento top", "value": _fmt_brl(float(g["receita"].sum())), "hint": ""},
                {"label": "Spread total", "value": _fmt_brl(float(g["spread"].sum())), "hint": ""},
                {"label": "Quebra total", "value": _fmt_brl(float(g["quebra"].sum())), "hint": ""},
            ],
            "chart": {
                "mode": "receita_custo_hbar",
                "type": "bar",
                "indexAxis": "y",
                "labels": [str(x)[:30] for x in g[mot]],
                "datasets": [
                    {"label": "Receita (R$)", "unit": "currency", "data": [round(float(x), 2) for x in g["receita"]]},
                    {"label": "Spread (R$)", "unit": "currency", "data": [round(float(x), 2) for x in g["spread"]]},
                ],
            },
            "chart_title": "Performance do motorista — receita × spread",
        }

    if analise_id == 4:
        r = _financeira(meta, filtered, 1)
        r2 = _financeira(meta, filtered, 2)
        kpis = r.get("kpis", [])[:2] + r2.get("kpis", [])[:2]
        return {
            "analise": meta,
            "kpis": kpis,
            "chart": r2.get("chart"),
            "chart_title": "Caixa transportadora — aging + projeção 90 dias",
        }

    if analise_id == 5:
        km = _km_por_placa(filtered)
        custos = _custos_por_placa(filtered, apartamento_id, placa_filter, start_date, end_date, filial_filter, tipo_negocio_filter)
        comb = _despesas_grupo_por_placa(filtered, "COMBUSTIVEL")
        if km.empty:
            return _empty(meta)
        m = custos.merge(km, on="placa", how="outer").fillna(0)
        m["r_km"] = np.where(m["km"] > 0, m["custo_total"] / m["km"], 0)
        m = m.merge(comb.rename(columns={"valor": "comb"}), on="placa", how="left").fillna(0)
        m["kml"] = np.where(m["comb"] > 0, m["km"] / (m["comb"] / 5.5), 0)
        media_rkm = float(m.loc[m["km"] > 0, "r_km"].mean()) if (m["km"] > 0).any() else 0
        media_kml = float(m.loc[m["kml"] > 0, "kml"].mean()) if (m["kml"] > 0).any() else 0
        comb_total = float(m["comb"].sum())
        m = m.sort_values("r_km", ascending=False).head(10)
        return {
            "analise": meta,
            "kpis": [
                {"label": "Placas", "value": str(len(m)), "hint": "top 10 R$/km"},
                {"label": "R$/km médio", "value": _fmt_brl(media_rkm), "hint": "frota com km"},
                {"label": "km/l médio", "value": f"{media_kml:.2f}".replace(".", ","), "hint": "frota com combustível"},
                {"label": "Combustível", "value": _fmt_brl(comb_total), "hint": ""},
            ],
            "chart": {
                "mode": "receita_custo_bar",
                "type": "bar",
                "labels": [str(x) for x in m["placa"]],
                "datasets": [
                    {"label": "R$/km", "unit": "currency", "data": [round(float(x), 2) for x in m["r_km"]]},
                    {"label": "km/l", "unit": "number", "data": [round(float(x), 2) for x in m["kml"]]},
                ],
            },
            "chart_title": "Eficiência integrada — custo/km e consumo",
        }

    if analise_id == 6:
        df_fluxo = _carregar_fluxo(apartamento_id, start_date, end_date)
        if df_fluxo.empty:
            return _empty(meta)
        total = len(df_fluxo)
        com_cte = int(df_fluxo.get("num_cte", pd.Series()).notna().sum()) if "num_cte" in df_fluxo.columns else total
        com_mdfe = int(df_fluxo.get("mdfestatus", pd.Series()).notna().sum()) if "mdfestatus" in df_fluxo.columns else 0
        com_ciot = int(df_fluxo.get("ciot", pd.Series()).notna().sum()) if "ciot" in df_fluxo.columns else 0
        labels = ["CT-e emitido", "CIOT", "MDF-e"]
        vals = [com_cte / total * 100 if total else 0, com_ciot / total * 100 if total else 0, com_mdfe / total * 100 if total else 0]
        return {
            "analise": meta,
            "kpis": [
                {"label": "Viagens fluxo", "value": str(total), "hint": ""},
                {"label": "% com CT-e", "value": _fmt_pct(vals[0]), "hint": ""},
                {"label": "% com CIOT", "value": _fmt_pct(vals[1]), "hint": ""},
                {"label": "% com MDF-e", "value": _fmt_pct(vals[2]), "hint": ""},
            ],
            "chart": {
                "mode": "receita_custo_bar",
                "type": "bar",
                "labels": labels,
                "datasets": [{"label": "% conclusão", "unit": "percent", "data": [round(float(x), 1) for x in vals]}],
            },
            "chart_title": "Compliance — etapas documentais concluídas",
        }
    return {"error": "Análise não implementada"}


def get_visao_bi_data(
    visao_key: str,
    analise_id: int,
    apartamento_id: int,
    start_date,
    end_date,
    placa_filter: str,
    filial_filter: list,
    tipo_negocio_filter: str,
) -> dict:
    visao = VISOES.get(visao_key)
    if not visao or analise_id not in visao["analises"]:
        return {"error": "Visão ou análise inválida"}

    meta = get_visao_meta(visao_key, analise_id)
    dm.sync_expense_groups_if_needed(apartamento_id)
    start_date, end_date = dm.resolver_intervalo_consulta(apartamento_id, start_date, end_date)

    if visao_key in ("volume", "custos"):
        handlers_early = {
            "volume": lambda: get_exploratorio_data(
                visao_key, analise_id, apartamento_id, start_date, end_date,
                placa_filter, filial_filter, tipo_negocio_filter, meta,
            ),
            "custos": lambda: get_exploratorio_data(
                visao_key, analise_id, apartamento_id, start_date, end_date,
                placa_filter, filial_filter, tipo_negocio_filter, meta,
            ),
        }
        return handlers_early[visao_key]()

    filtered = dm._obter_dados_filtrados_mestre(
        apartamento_id, start_date, end_date, placa_filter, filial_filter, tipo_negocio_filter
    )

    handlers = {
        "financeira": lambda: _financeira(meta, filtered, analise_id),
        "frota": lambda: _frota(
            meta, filtered, apartamento_id, placa_filter, start_date, end_date, filial_filter, tipo_negocio_filter, analise_id
        ),
        "operacional": lambda: _operacional(meta, filtered, apartamento_id, start_date, end_date, analise_id),
        "estrategica": lambda: _estrategica(
            meta, filtered, apartamento_id, placa_filter, start_date, end_date, filial_filter, tipo_negocio_filter, analise_id
        ),
    }
    if visao_key not in handlers:
        return {"error": "Visão não implementada"}
    return handlers[visao_key]()
