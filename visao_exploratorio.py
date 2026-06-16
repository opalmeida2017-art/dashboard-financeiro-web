"""Visões exploratórias — volume (faturamento) e estrutura de custos (despesas)."""

from __future__ import annotations

import data_manager as dm
from gestao_comercial import _fmt_brl, _fmt_pct

EXPLORATORIO_VISOES = {
    "volume": {
        "titulo": "Visão volume",
        "subtitulo": "Faturamento e movimentação por dimensão",
        "badge": "Volume",
        "badge_class": "receita",
        "analises": {
            1: {
                "titulo": "Evolução receita × custo",
                "subtitulo": "Série temporal do período",
                "pergunta": "A receita está acompanhando o custo no período filtrado?",
                "icone": "blue",
                "emoji": "📈",
            },
            2: {
                "titulo": "Faturamento por filial",
                "subtitulo": "Participação por unidade",
                "pergunta": "Qual filial concentra o faturamento da operação?",
                "icone": "green",
                "emoji": "🏢",
            },
            3: {
                "titulo": "Top clientes por faturamento",
                "subtitulo": "Maiores em R$ (sem margem)",
                "pergunta": "Quem puxa volume de frete no período?",
                "icone": "purple",
                "emoji": "👥",
            },
            4: {
                "titulo": "Rotas mais frequentes",
                "subtitulo": "Contagem de viagens origem → destino",
                "pergunta": "Onde operamos mais viagens?",
                "icone": "blue",
                "emoji": "🗺️",
            },
            5: {
                "titulo": "Faturamento por mercadoria",
                "subtitulo": "Tipo de carga transportada",
                "pergunta": "Qual mercadoria domina o faturamento?",
                "icone": "green",
                "emoji": "📦",
            },
            6: {
                "titulo": "Volume por rota (kg)",
                "subtitulo": "Peso total movimentado",
                "pergunta": "Onde há mais tonelada embarcada?",
                "icone": "purple",
                "emoji": "⚖️",
            },
            7: {
                "titulo": "Viagens por veículo",
                "subtitulo": "Quantidade de CT-es por placa",
                "pergunta": "Qual ativo mais rodou no período?",
                "icone": "blue",
                "emoji": "🚛",
            },
            8: {
                "titulo": "Motoristas por faturamento",
                "subtitulo": "Ranking em frete empresa",
                "pergunta": "Quem mais faturou no período?",
                "icone": "red",
                "emoji": "👤",
            },
        },
    },
    "custos": {
        "titulo": "Estrutura de custos",
        "subtitulo": "Composição e despesas por dimensão",
        "badge": "Custos",
        "badge_class": "despesa",
        "analises": {
            1: {
                "titulo": "Composição por filial",
                "subtitulo": "Custo viagem, despesa geral e tipo D",
                "pergunta": "Quanto é viagem, fixo (tipo D) e despesa geral em cada filial?",
                "icone": "blue",
                "emoji": "📊",
            },
            2: {
                "titulo": "Despesas por grupo",
                "subtitulo": "Grupos contábeis do SATI",
                "pergunta": "Qual grupo de despesa mais pressiona o resultado?",
                "icone": "red",
                "emoji": "📁",
            },
            3: {
                "titulo": "Despesas por filial",
                "subtitulo": "Total consolidado",
                "pergunta": "Qual unidade gasta mais no período?",
                "icone": "green",
                "emoji": "🏢",
            },
            4: {
                "titulo": "Manutenção por veículo",
                "subtitulo": "Grupo manutenção × placa",
                "pergunta": "Qual caminhão mais gasta em oficina?",
                "icone": "red",
                "emoji": "🔧",
            },
            5: {
                "titulo": "Combustível por produto",
                "subtitulo": "Diesel, arla e outros itens",
                "pergunta": "Onde está o gasto com combustível por tipo?",
                "icone": "purple",
                "emoji": "⛽",
            },
            6: {
                "titulo": "Combustível por veículo",
                "subtitulo": "Valor em R$ por placa",
                "pergunta": "Qual placa mais abastece em valor?",
                "icone": "blue",
                "emoji": "🚛",
            },
        },
    },
}


def _n(val) -> float:
    try:
        return float(val or 0)
    except (TypeError, ValueError):
        return 0.0


def _pick(row: dict, *keys):
    for k in keys:
        if k in row and row[k] is not None:
            return row[k]
    return None


def _sort_rows(rows: list, key_fn, reverse: bool = True) -> list:
    return sorted(rows, key=key_fn, reverse=reverse)


def _top_by(rows: list, key_fn):
    return max(rows, key=key_fn) if rows else None


def _empty(meta, hint="Sem dados para os filtros selecionados"):
    return {
        "analise": meta,
        "kpis": [{"label": "Dados", "value": "—", "hint": hint}],
        "chart": None,
        "chart_title": "Sem dados",
    }


def _volume(meta, data: dict, analise_id: int) -> dict:
    if not data:
        return _empty(meta)

    if analise_id == 1:
        rows = data.get("evolucao_faturamento_custo") or []
        if not rows:
            return _empty(meta)
        labels = [str(r.get("Periodo", "")) for r in rows]
        fat = [_n(r.get("Faturamento")) for r in rows]
        custo = [_n(r.get("Custo")) for r in rows]
        tf, tc = sum(fat), sum(custo)
        margem = (tf - tc) / tf * 100 if tf > 0 else 0
        return {
            "analise": meta,
            "kpis": [
                {"label": "Receita período", "value": _fmt_brl(tf), "hint": ""},
                {"label": "Custo período", "value": _fmt_brl(tc), "hint": "viagem + geral + tipo D"},
                {"label": "Margem bruta", "value": _fmt_pct(margem), "hint": "receita − custo"},
                {"label": "Pontos no gráfico", "value": str(len(labels)), "hint": ""},
            ],
            "chart": {
                "mode": "fluxo_caixa",
                "type": "line",
                "labels": labels,
                "datasets": [
                    {"label": "Faturamento (R$)", "unit": "currency", "data": [round(x, 2) for x in fat]},
                    {"label": "Custo total (R$)", "unit": "currency", "data": [round(x, 2) for x in custo]},
                ],
            },
            "chart_title": "Evolução faturamento vs custo total",
        }

    if analise_id == 2:
        rows = data.get("faturamento_filial") or []
        if not rows:
            return _empty(meta)
        rows = _sort_rows(rows, lambda r: _n(r.get("freteEmpresa")))
        vals = [_n(r.get("freteEmpresa")) for r in rows]
        total = sum(vals)
        top = rows[0]
        return {
            "analise": meta,
            "kpis": [
                {"label": "Filiais", "value": str(len(rows)), "hint": ""},
                {"label": "Faturamento total", "value": _fmt_brl(total), "hint": ""},
                {"label": "Maior filial", "value": str(_pick(top, "nomeFilial", "nomefilial"))[:30], "hint": _fmt_brl(_n(top.get("freteEmpresa")))},
                {"label": "Participação top", "value": _fmt_pct(_n(top.get("freteEmpresa")) / total * 100 if total else 0), "hint": ""},
            ],
            "chart": {
                "mode": "doughnut",
                "type": "doughnut",
                "labels": [str(_pick(r, "nomeFilial", "nomefilial"))[:28] for r in rows],
                "datasets": [{"label": "Faturamento", "data": [round(v, 2) for v in vals]}],
            },
            "chart_title": "Faturamento por filial",
        }

    if analise_id == 3:
        rows = data.get("top_clientes") or []
        if not rows:
            return _empty(meta)
        rows = _sort_rows(rows, lambda r: _n(r.get("freteEmpresa")))
        vals = [_n(r.get("freteEmpresa")) for r in rows]
        total = sum(vals)
        return {
            "analise": meta,
            "kpis": [
                {"label": "Clientes no top", "value": str(len(rows)), "hint": "10 maiores"},
                {"label": "Faturamento top", "value": _fmt_brl(total), "hint": ""},
                {"label": "Cliente #1", "value": str(rows[0].get("nomeCliente", ""))[:35], "hint": _fmt_brl(vals[0])},
                {"label": "Ticket médio top", "value": _fmt_brl(total / len(rows)), "hint": "média do ranking"},
            ],
            "chart": {
                "mode": "receita_custo_hbar",
                "type": "bar",
                "indexAxis": "y",
                "labels": [str(r.get("nomeCliente", ""))[:35] for r in rows],
                "datasets": [{"label": "Faturamento (R$)", "unit": "currency", "data": [round(v, 2) for v in vals]}],
            },
            "chart_title": "Top clientes por faturamento",
        }

    if analise_id == 4:
        rows = data.get("top_rotas") or []
        if not rows:
            return _empty(meta)
        rows = _sort_rows(rows, lambda r: _n(r.get("contagem")))
        counts = [int(_n(r.get("contagem"))) for r in rows]
        return {
            "analise": meta,
            "kpis": [
                {"label": "Rotas no top", "value": str(len(rows)), "hint": ""},
                {"label": "Viagens total top", "value": str(sum(counts)), "hint": ""},
                {"label": "Rota #1", "value": str(rows[0].get("rota", ""))[:40], "hint": f"{counts[0]} viagens"},
                {"label": "Média top", "value": f"{sum(counts) / len(counts):.0f}", "hint": "viagens/rota"},
            ],
            "chart": {
                "mode": "margem_hbar",
                "type": "bar",
                "indexAxis": "y",
                "labels": [str(r.get("rota", ""))[:42] for r in rows],
                "datasets": [{"label": "Nº viagens", "unit": "count", "data": counts}],
            },
            "chart_title": "Rotas mais frequentes",
        }

    if analise_id == 5:
        rows = data.get("faturamento_por_mercadoria") or []
        if not rows:
            return _empty(meta)
        rows = _sort_rows(rows, lambda r: _n(r.get("faturamento")))
        vals = [_n(r.get("faturamento")) for r in rows]
        total = sum(vals)
        return {
            "analise": meta,
            "kpis": [
                {"label": "Tipos de carga", "value": str(len(rows)), "hint": ""},
                {"label": "Faturamento", "value": _fmt_brl(total), "hint": ""},
                {"label": "Mercadoria #1", "value": str(rows[0].get("mercadoria", ""))[:35], "hint": _fmt_pct(vals[0] / total * 100 if total else 0)},
                {"label": "Top 3", "value": _fmt_pct(sum(vals[:3]) / total * 100 if total else 0), "hint": "do faturamento"},
            ],
            "chart": {
                "mode": "doughnut",
                "type": "doughnut",
                "labels": [str(r.get("mercadoria", ""))[:28] for r in rows],
                "datasets": [{"label": "Faturamento", "data": [round(v, 2) for v in vals]}],
            },
            "chart_title": "Faturamento por tipo de mercadoria",
        }

    if analise_id == 6:
        rows = data.get("volume_por_rota") or []
        if not rows:
            return _empty(meta)
        rows = _sort_rows(rows, lambda r: _n(r.get("pesoSaida") or r.get("pesosaida")))
        pesos = [_n(r.get("pesoSaida") or r.get("pesosaida")) for r in rows]
        total = sum(pesos)
        return {
            "analise": meta,
            "kpis": [
                {"label": "Rotas", "value": str(len(rows)), "hint": ""},
                {"label": "Peso total", "value": f"{total:,.0f} kg".replace(",", "."), "hint": ""},
                {"label": "Rota #1", "value": str(rows[0].get("rota", ""))[:40], "hint": f"{pesos[0]:,.0f} kg".replace(",", ".")},
                {"label": "Média/rota", "value": f"{total / len(pesos):,.0f} kg".replace(",", "."), "hint": ""},
            ],
            "chart": {
                "mode": "receita_custo_bar",
                "type": "bar",
                "labels": [str(r.get("rota", ""))[:30] for r in rows],
                "datasets": [{"label": "Peso (kg)", "unit": "kg", "data": [round(p, 0) for p in pesos]}],
            },
            "chart_title": "Volume de carga (kg) por rota",
        }

    if analise_id == 7:
        rows = data.get("viagens_por_veiculo") or []
        if not rows:
            return _empty(meta)
        rows = _sort_rows(rows, lambda r: _n(r.get("contagem")))
        counts = [int(_n(r.get("contagem"))) for r in rows]
        return {
            "analise": meta,
            "kpis": [
                {"label": "Placas", "value": str(len(rows)), "hint": ""},
                {"label": "Viagens total", "value": str(sum(counts)), "hint": ""},
                {"label": "Placa #1", "value": str(rows[0].get("placa", "")), "hint": f"{counts[0]} viagens"},
                {"label": "Média/placa", "value": f"{sum(counts) / len(counts):.1f}".replace(".", ","), "hint": "viagens"},
            ],
            "chart": {
                "mode": "receita_custo_bar",
                "type": "bar",
                "labels": [str(r.get("placa", "")) for r in rows],
                "datasets": [{"label": "Nº viagens", "unit": "count", "data": counts}],
            },
            "chart_title": "Viagens por veículo",
        }

    if analise_id == 8:
        rows = data.get("faturamento_motorista") or []
        if not rows:
            return _empty(meta)
        rows = _sort_rows(rows, lambda r: _n(r.get("faturamento")))
        vals = [_n(r.get("faturamento")) for r in rows]
        total = sum(vals)
        return {
            "analise": meta,
            "kpis": [
                {"label": "Motoristas", "value": str(len(rows)), "hint": "top 10"},
                {"label": "Faturamento top", "value": _fmt_brl(total), "hint": ""},
                {"label": "Motorista #1", "value": str(rows[0].get("nomeMotorista", ""))[:35], "hint": _fmt_brl(vals[0])},
                {"label": "Média top", "value": _fmt_brl(total / len(rows)), "hint": ""},
            ],
            "chart": {
                "mode": "receita_custo_hbar",
                "type": "bar",
                "indexAxis": "y",
                "labels": [str(r.get("nomeMotorista", ""))[:35] for r in rows],
                "datasets": [{"label": "Faturamento (R$)", "unit": "currency", "data": [round(v, 2) for v in vals]}],
            },
            "chart_title": "Motoristas por faturamento",
        }

    return {"error": "Análise não implementada"}


def _custos(meta, data: dict, analise_id: int) -> dict:
    if not data:
        return _empty(meta)

    if analise_id == 1:
        comp = data.get("despesas_por_filial_e_grupo") or {}
        labels = comp.get("labels") or []
        datasets = comp.get("datasets") or []
        if not labels or not datasets:
            return _empty(meta)
        colors = {
            "Custo de Viagem": "#f59e0b",
            "Despesa Geral": "#ef4444",
            "Despesa Tipo D": "#7c3aed",
        }
        n = len(labels)
        totais_filial = []
        for i in range(n):
            t = sum(_n(ds.get("data", [])[i]) for ds in datasets if i < len(ds.get("data", [])))
            totais_filial.append(t)
        order = sorted(range(n), key=lambda i: totais_filial[i], reverse=True)
        labels_ord = [labels[i] for i in order]
        datasets_ord = [
            {
                "label": ds.get("label", ""),
                "data": [round(_n(ds.get("data", [])[i]), 2) for i in order],
                "color": colors.get(ds.get("label", ""), "#64748b"),
            }
            for ds in datasets
        ]
        total = sum(totais_filial)
        idx_maior = order[0] if order else 0
        maior_nome = str(labels[idx_maior])[:35] if labels else "—"
        maior_val = totais_filial[idx_maior] if totais_filial else 0
        partes_maior = []
        for ds in datasets:
            v = _n(ds.get("data", [])[idx_maior]) if idx_maior < len(ds.get("data", [])) else 0
            if v > 0:
                partes_maior.append(f"{ds.get('label', '')}: {_fmt_brl(v)}")
        return {
            "analise": meta,
            "kpis": [
                {"label": "Filiais", "value": str(len(labels)), "hint": ""},
                {"label": "Total composto", "value": _fmt_brl(total), "hint": ""},
                {"label": "Categorias", "value": str(len(datasets)), "hint": ""},
                {
                    "label": "Maior filial",
                    "value": maior_nome,
                    "hint": f"{_fmt_brl(maior_val)} · " + " · ".join(partes_maior[:2]),
                },
            ],
            "chart": {
                "mode": "stacked_multi",
                "type": "bar",
                "labels": labels_ord,
                "datasets": datasets_ord,
            },
            "chart_title": "Composição das despesas por filial (ordenado por total)",
        }

    if analise_id == 2:
        rows = data.get("despesa_super_grupo") or []
        if not rows:
            return _empty(meta)
        vals = [_n(_pick(r, "vlcontabil", "valor_calculado")) for r in rows]
        total = sum(vals)
        return {
            "analise": meta,
            "kpis": [
                {"label": "Grupos", "value": str(len(rows)), "hint": "top 10"},
                {"label": "Total", "value": _fmt_brl(total), "hint": ""},
                {"label": "Grupo #1", "value": str(_pick(rows[0], "descSuperGrupoD", "descgrupod", "descGrupoD"))[:35], "hint": _fmt_pct(vals[0] / total * 100 if total else 0)},
                {"label": "Top 3", "value": _fmt_pct(sum(vals[:3]) / total * 100 if total else 0), "hint": "do total"},
            ],
            "chart": {
                "mode": "doughnut",
                "type": "doughnut",
                "labels": [str(_pick(r, "descSuperGrupoD", "descgrupod", "descGrupoD"))[:28] for r in rows],
                "datasets": [{"label": "Despesa", "data": [round(v, 2) for v in vals]}],
            },
            "chart_title": "Despesas por grupo",
        }

    if analise_id == 3:
        rows = data.get("despesa_filial") or []
        if not rows:
            return _empty(meta)
        rows = _sort_rows(rows, lambda r: _n(_pick(r, "vlcontabil", "valor_calculado")))
        vals = [_n(_pick(r, "vlcontabil", "valor_calculado")) for r in rows]
        total = sum(vals)
        return {
            "analise": meta,
            "kpis": [
                {"label": "Filiais", "value": str(len(rows)), "hint": ""},
                {"label": "Despesa total", "value": _fmt_brl(total), "hint": ""},
                {"label": "Maior filial", "value": str(_pick(rows[0], "nomeFil", "nomefil", "nomefilial"))[:35], "hint": _fmt_brl(vals[0])},
                {"label": "Média/filial", "value": _fmt_brl(total / len(rows)), "hint": ""},
            ],
            "chart": {
                "mode": "receita_custo_bar",
                "type": "bar",
                "labels": [str(_pick(r, "nomeFil", "nomefil", "nomefilial"))[:28] for r in rows],
                "datasets": [{"label": "Despesa (R$)", "unit": "currency", "data": [round(v, 2) for v in vals]}],
            },
            "chart_title": "Despesas por filial (ordenado por valor)",
        }

    if analise_id == 4:
        rows = data.get("custo_manutencao_veiculo") or []
        if not rows:
            return _empty(meta)
        vals = [_n(_pick(r, "vlcontabil", "valor_calculado")) for r in rows]
        return {
            "analise": meta,
            "kpis": [
                {"label": "Placas", "value": str(len(rows)), "hint": ""},
                {"label": "Manutenção total", "value": _fmt_brl(sum(vals)), "hint": ""},
                {"label": "Placa #1", "value": str(_pick(rows[0], "placaVeiculo", "placaveiculo")), "hint": _fmt_brl(vals[0])},
                {"label": "Média/placa", "value": _fmt_brl(sum(vals) / len(vals)), "hint": ""},
            ],
            "chart": {
                "mode": "margem_hbar",
                "type": "bar",
                "indexAxis": "y",
                "labels": [str(_pick(r, "placaVeiculo", "placaveiculo")) for r in rows],
                "datasets": [{"label": "Manutenção (R$)", "unit": "currency", "data": [round(v, 2) for v in vals]}],
            },
            "chart_title": "Custo de manutenção por veículo",
        }

    if analise_id == 5:
        rows = data.get("gastos_por_combustivel") or []
        if not rows:
            return _empty(meta)
        vals = [_n(r.get("valor_total")) for r in rows]
        return {
            "analise": meta,
            "kpis": [
                {"label": "Tipos combustível", "value": str(len(rows)), "hint": ""},
                {"label": "Gasto total", "value": _fmt_brl(sum(vals)), "hint": ""},
                {"label": "Item #1", "value": str(rows[0].get("item", ""))[:35], "hint": _fmt_brl(vals[0])},
                {"label": "Itens listados", "value": str(len(rows)), "hint": ""},
            ],
            "chart": {
                "mode": "receita_custo_hbar",
                "type": "bar",
                "indexAxis": "y",
                "labels": [str(r.get("item", ""))[:35] for r in rows],
                "datasets": [{"label": "Valor (R$)", "unit": "currency", "data": [round(v, 2) for v in vals]}],
            },
            "chart_title": "Gasto por tipo de combustível",
        }

    if analise_id == 6:
        rows = data.get("combustivel_por_veiculo") or []
        if not rows:
            return _empty(meta)
        vals = [_n(_pick(r, "valor_total", "valorTotal")) for r in rows]
        litros = sum(_n(r.get("litros_total")) for r in rows)
        return {
            "analise": meta,
            "kpis": [
                {"label": "Placas", "value": str(len(rows)), "hint": ""},
                {"label": "Gasto total", "value": _fmt_brl(sum(vals)), "hint": ""},
                {"label": "Placa #1", "value": str(_pick(rows[0], "placaVeiculo", "placaveiculo")), "hint": _fmt_brl(vals[0])},
                {"label": "Litros (se houver)", "value": f"{litros:,.0f}".replace(",", ".") if litros else "—", "hint": "itemnota.quantidade"},
            ],
            "chart": {
                "mode": "receita_custo_hbar",
                "type": "bar",
                "indexAxis": "y",
                "labels": [str(_pick(r, "placaVeiculo", "placaveiculo")) for r in rows],
                "datasets": [{"label": "Combustível (R$)", "unit": "currency", "data": [round(v, 2) for v in vals]}],
            },
            "chart_title": "Combustível por veículo",
        }

    return {"error": "Análise não implementada"}


def get_exploratorio_data(
    visao_key: str,
    analise_id: int,
    apartamento_id: int,
    start_date,
    end_date,
    placa_filter: str,
    filial_filter: list,
    tipo_negocio_filter: str,
    meta: dict,
) -> dict:
    if visao_key == "volume":
        data = dm.get_faturamento_details_dashboard_data(
            apartamento_id, start_date, end_date, placa_filter, filial_filter, tipo_negocio_filter
        )
        return _volume(meta, data, analise_id)
    if visao_key == "custos":
        data = dm.get_despesas_details_dashboard_data(
            apartamento_id, start_date, end_date, placa_filter, filial_filter, tipo_negocio_filter
        )
        return _custos(meta, data, analise_id)
    return {"error": "Visão exploratória inválida"}
