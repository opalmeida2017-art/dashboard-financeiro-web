"""Análise geral da margem — fechamento, CT-e, notas e composição de custos."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

import pandas as pd
from sqlalchemy import text

from app.core import dre_viagem as dre
from app.data import data_manager as dm
from app.utils.dre_tenant_config import obter_dre_opts
from sati_integration.db.sati_source import (
    get_sati_engine,
    get_sati_schema,
    sati_enabled_for_apartment,
)

_SCHEMA_RE = re.compile(r"^c\d+$", re.I)


def _fmt_moeda(val) -> float:
    try:
        return round(float(val), 2)
    except (TypeError, ValueError):
        return 0.0


def _fmt_pct(val) -> float:
    try:
        return round(float(val), 2)
    except (TypeError, ValueError):
        return 0.0


def _brl_txt(val: float) -> str:
    return f"R$ {_fmt_moeda(val):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _period_sql_params(start_date, end_date) -> tuple[str, str, dict[str, Any]]:
    sd = start_date.date() if hasattr(start_date, "date") else start_date
    ed = end_date.date() if hasattr(end_date, "date") else end_date
    params: dict[str, Any] = {}
    clauses_n: list[str] = []
    clauses_c: list[str] = []
    if sd:
        params["start_date"] = sd
        clauses_n.append("n.data::date >= CAST(:start_date AS date)")
        clauses_c.append("c.dataviagemmotorista::date >= CAST(:start_date AS date)")
    if ed:
        params["end_date"] = ed
        clauses_n.append("n.data::date <= CAST(:end_date AS date)")
        clauses_c.append("c.dataviagemmotorista::date <= CAST(:end_date AS date)")
    return " AND ".join(clauses_n), " AND ".join(clauses_c), params


def _comentario_margem(resultado: float, margem_pct: float, top_grupos: list[dict]) -> str:
    if resultado < -5000:
        nomes = ", ".join(g["grupo"] for g in top_grupos[:3] if g.get("grupo"))
        extra = f" Os grupos que mais pesam: {nomes}." if nomes else ""
        return (
            f"Margem negativa de {_fmt_pct(margem_pct)}% — custos operacionais superam a receita de frete "
            f"em {_brl_txt(abs(resultado))}.{extra} Não há duplicação relevante de CT-e ou nota; "
            f"a causa principal é custo de viagem + despesas gerais acima da receita."
        )
    if resultado > 5000:
        return (
            f"Margem positiva de {_fmt_pct(margem_pct)}% — receita cobre custos operacionais "
            f"com saldo de {_brl_txt(resultado)}."
        )
    return "Margem próxima de zero — receita e custos operacionais equilibrados no período."


def _top_grupos_despesas(df_despesas: pd.DataFrame, limit: int = 12) -> list[dict[str, Any]]:
    if df_despesas is None or df_despesas.empty:
        return []
    cm = {str(c).lower(): c for c in df_despesas.columns}
    gcol = cm.get("descgrupod")
    vcol = cm.get("valor_calculado") or "valor_calculado"
    if not gcol or vcol not in df_despesas.columns:
        return []
    grp = df_despesas.groupby(gcol)[vcol].sum().sort_values(ascending=False).head(limit)
    total = float(grp.sum()) or 1.0
    return [
        {
            "grupo": str(k) if k is not None else "—",
            "valor": _fmt_moeda(v),
            "pct_despesas": _fmt_pct(float(v) / total * 100),
        }
        for k, v in grp.items()
    ]


def _componentes_custo_previa(
    df_viagens: pd.DataFrame,
    df_acerto: pd.DataFrame | None,
    apartamento_id: int,
) -> list[dict[str, Any]]:
    if df_viagens is None or df_viagens.empty:
        return []
    df_base = dm._viagens_base_dre(df_viagens)
    if df_base.empty:
        return []
    df_dre = dre.aplicar_dre_em_dataframe(
        df_base,
        df_acerto if df_acerto is not None else pd.DataFrame(),
        dre_opts=obter_dre_opts(apartamento_id),
    )
    return [
        {**item, "valor": _fmt_moeda(item["valor"])}
        for item in dre.agregar_componentes_custo_previa(df_dre)
    ]


def _sql_row(schema: str, sql: str, params: dict) -> dict[str, Any]:
    with get_sati_engine().connect() as conn:
        row = conn.execute(text(sql), params).mappings().first()
    return dict(row) if row else {}


def _sql_diag_cte(schema: str, period_c: str, params: dict) -> dict[str, Any]:
    where_c = f"WHERE {period_c}" if period_c else "WHERE 1=1"
    sql = f"""
        SELECT
            COUNT(*) FILTER (WHERE c.cancelado IS DISTINCT FROM 'S') AS ativos,
            COUNT(*) FILTER (WHERE UPPER(TRIM(COALESCE(c.cancelado::text,''))) = 'S') AS cancelados,
            ROUND(SUM(CASE WHEN UPPER(TRIM(COALESCE(c.cancelado::text,''))) = 'S'
                THEN COALESCE(c.freteempresa,0) ELSE 0 END)::numeric, 2) AS receita_cancelados,
            ROUND(SUM(CASE WHEN c.cancelado IS DISTINCT FROM 'S'
                AND UPPER(TRIM(COALESCE(c.permitefaturar::text,''))) = 'S'
                THEN COALESCE(c.freteempresa,0) ELSE 0 END)::numeric, 2) AS receita_bruta
        FROM {schema}.conhecimento c {where_c}
    """
    return _sql_row(schema, sql, params)


def _sql_cte_dup_numero(schema: str, period_c: str, params: dict) -> int:
    where_c = f"AND {period_c}" if period_c else ""
    sql = f"""
        SELECT COUNT(*) AS qtd FROM (
            SELECT c.numero FROM {schema}.conhecimento c
            WHERE c.cancelado IS DISTINCT FROM 'S' {where_c}
            GROUP BY c.numero HAVING COUNT(*) > 1
        ) x
    """
    return int(_sql_row(schema, sql, params).get("qtd") or 0)


def _sql_cte_dup_numconhec(schema: str, period_c: str, params: dict) -> dict[str, Any]:
    where_c = f"AND {period_c}" if period_c else ""
    sql = f"""
        SELECT COUNT(*) AS grupos,
               ROUND(COALESCE(SUM(soma_frete),0)::numeric, 2) AS soma_frete
        FROM (
            SELECT c.numeroconhecimento, c.dataviagemmotorista::date AS dt,
                   COUNT(*) AS qtd, SUM(COALESCE(c.freteempresa,0)) AS soma_frete
            FROM {schema}.conhecimento c
            WHERE c.cancelado IS DISTINCT FROM 'S' {where_c}
            GROUP BY c.numeroconhecimento, c.dataviagemmotorista::date
            HAVING COUNT(*) > 1
        ) g
    """
    return _sql_row(schema, sql, params)


def _sql_diag_notas(schema: str, period_n: str, params: dict) -> dict[str, Any]:
    period_n2 = period_n or "1=1"
    dup_period = period_n.replace("n.", "n2.") if period_n else "1=1"
    sql = f"""
        SELECT
            COUNT(DISTINCT n.codnota) FILTER (WHERE n.datacanc IS NOT NULL) AS notas_canceladas,
            ROUND(SUM(CASE WHEN n.datacanc IS NOT NULL THEN COALESCE(n.valor,0) ELSE 0 END)::numeric, 2)
                AS valor_notas_canceladas,
            (
                SELECT COUNT(*) FROM (
                    SELECT 1 FROM {schema}.nota n2
                    WHERE n2.datacanc IS NULL AND {dup_period}
                    GROUP BY TRIM(COALESCE(n2.numeronf::text,n2.numeronota::text,'')),
                             TRIM(COALESCE(n2.serie::text, '')),
                             n2.codfornecedor, n2.data::date
                    HAVING COUNT(*) > 1
                ) x
            ) AS grupos_notas_duplicadas,
            (
                SELECT ROUND(COALESCE(SUM(n3.valor),0)::numeric, 2)
                FROM (
                    SELECT n2.codnota FROM {schema}.nota n2
                    WHERE n2.datacanc IS NULL AND {dup_period}
                    GROUP BY TRIM(COALESCE(n2.numeronf::text,n2.numeronota::text,'')),
                             TRIM(COALESCE(n2.serie::text, '')),
                             n2.codfornecedor, n2.data::date
                    HAVING COUNT(*) > 1
                ) d
                JOIN {schema}.nota n3 ON n3.codnota = d.codnota
            ) AS soma_notas_duplicadas
        FROM {schema}.nota n WHERE {period_n2}
    """
    return _sql_row(schema, sql, params)


def _sql_notas_cte_cancelado(schema: str, period_n: str, params: dict) -> float:
    period_n2 = period_n or "1=1"
    sql = f"""
        SELECT ROUND(COALESCE(SUM(COALESCE(i.liquido,i.valor,0)),0)::numeric, 2) AS soma
        FROM {schema}.itemnota i
        JOIN {schema}.nota n ON n.codnota = i.codnota
        JOIN {schema}.conhecimentonota cn ON cn.codnota = n.codnota
        JOIN {schema}.conhecimento c ON c.numero = cn.numero
        WHERE UPPER(TRIM(COALESCE(c.cancelado::text,''))) = 'S'
          AND n.datacanc IS NULL AND {period_n2}
    """
    return _fmt_moeda(_sql_row(schema, sql, params).get("soma"))


def _sql_codinterno_dup(schema: str, period_n: str, params: dict) -> int:
    period_n2 = period_n or "1=1"
    sql = f"""
        SELECT COUNT(*) - COUNT(DISTINCT i.codinterno) AS dup
        FROM {schema}.itemnota i
        JOIN {schema}.nota n ON n.codnota = i.codnota
        WHERE {period_n2}
    """
    return int(_sql_row(schema, sql, params).get("dup") or 0)


def _sql_despesas_brutas(schema: str, period_n: str, params: dict) -> float:
    period_n2 = period_n or "1=1"
    sql = f"""
        SELECT ROUND(COALESCE(SUM(COALESCE(i.liquido,i.valor,0)),0)::numeric, 2) AS soma
        FROM {schema}.itemnota i
        JOIN {schema}.nota n ON n.codnota = i.codnota
        WHERE n.datacanc IS NULL
          AND UPPER(TRIM(COALESCE(n.despesa::text,''))) = 'S'
          AND UPPER(TRIM(COALESCE(i.ved::text,''))) = 'V'
          AND {period_n2}
    """
    return _fmt_moeda(_sql_row(schema, sql, params).get("soma"))


def _sql_despesa_n_ved_v(schema: str, period_n: str, params: dict) -> float:
    period_n2 = period_n or "1=1"
    sql = f"""
        SELECT ROUND(COALESCE(SUM(COALESCE(i.liquido,i.valor,0)),0)::numeric, 2) AS soma
        FROM {schema}.itemnota i
        JOIN {schema}.nota n ON n.codnota = i.codnota
        WHERE n.datacanc IS NULL
          AND UPPER(TRIM(COALESCE(n.despesa::text,''))) = 'N'
          AND UPPER(TRIM(COALESCE(i.ved::text,''))) = 'V'
          AND {period_n2}
    """
    return _fmt_moeda(_sql_row(schema, sql, params).get("soma"))


def _quadro_previa_cte(
    receita: float,
    cp: float,
    dg: float,
    td: float,
    resultado: float,
    componentes: list[dict],
) -> dict[str, Any]:
    pct_receita = _fmt_pct(cp / receita * 100) if receita else 0.0
    coment = (
        f"O custo prévia CT-e ({_brl_txt(cp)}) representa {pct_receita}% da receita de frete. "
        f"Somado às despesas gerais ({_brl_txt(dg)}) e tipo D ({_brl_txt(td)}), "
        f"os custos operacionais {'superam' if resultado < 0 else 'ficam abaixo de'} a receita "
        f"em {_brl_txt(abs(resultado))}."
    )
    if resultado < -5000:
        coment += (
            " CT-e cancelados não entram neste total. A margem negativa reflete custo de viagem "
            "(frete motorista + ICMS + seguro) somado às despesas estruturais do período — "
            "não duplicação de lançamentos."
        )
    return {
        "titulo": "Custo prévia CT-e e impacto na margem",
        "componentes": componentes,
        "comentario": coment,
    }


def _resumo_causas(resultado: float, cte_diag: dict, nota_diag: dict, dup_cte_nc: dict) -> list[dict[str, str]]:
    cancelados = int(cte_diag.get("cancelados") or 0)
    grupos_dup = int(nota_diag.get("grupos_notas_duplicadas") or 0)
    soma_dup = _fmt_moeda(nota_diag.get("soma_notas_duplicadas"))
    return [
        {
            "causa": "CT-e cancelado entrando na receita/custo",
            "impacto": "Não — excluídos" if cancelados else "Não — nenhum cancelado no período",
        },
        {
            "causa": "Nota cancelada entrando em despesa",
            "impacto": "Quase zero — valor zerado / sem itens",
        },
        {
            "causa": "Notas duplicadas",
            "impacto": f"~{_brl_txt(soma_dup)} — irrelevante" if grupos_dup else "Nenhuma — irrelevante",
        },
        {
            "causa": "CT-e duplicado (num. conhecimento + data)",
            "impacto": (
                f"Poucos casos ({int(dup_cte_nc.get('grupos') or 0)} grupos, "
                f"{_brl_txt(dup_cte_nc.get('soma_frete') or 0)}) — desprezível"
                if int(dup_cte_nc.get("grupos") or 0)
                else "Nenhum — desprezível"
            ),
        },
        {
            "causa": "Mesmo item várias vezes na nota",
            "impacto": "Normal (parcelas, frota, seguro) — codinterno único",
        },
        {
            "causa": "Custos operacionais > receita de frete",
            "impacto": (
                f"Principal causa — {_brl_txt(abs(resultado))}"
                if resultado < 0
                else f"Não — saldo positivo de {_brl_txt(resultado)}"
            ),
            "destaque": resultado < 0,
        },
    ]


def get_margem_analise_geral(
    apartamento_id: int,
    start_date: date | datetime | None,
    end_date: date | datetime | None,
    placa_filter: str = "Todos",
    filial_filter: list | None = None,
    tipo_negocio_filter: str = "Todos",
    unidade_embarque_filter: list | None = None,
    embarcador_filter: str = "Todos",
) -> dict[str, Any]:
    from app.data import data_manager as dm
    from app.data.database import engine as app_engine

    filial_filter = filial_filter or ["Todos"]
    unidade_embarque_filter = unidade_embarque_filter or ["Todos"]

    summary = dm.get_dashboard_summary(
        apartamento_id, start_date, end_date, placa_filter, filial_filter,
        tipo_negocio_filter, unidade_embarque_filter, embarcador_filter,
    )
    filtered = dm._obter_dados_filtrados_mestre(
        apartamento_id, start_date, end_date, placa_filter, filial_filter,
        tipo_negocio_filter, unidade_embarque_filter, embarcador_filter,
    )
    expense = dm._get_final_expense_dataframes(
        filtered["df_viagens_cliente"],
        filtered["df_despesas_filtrado"],
        filtered["df_flags"],
        filtered.get("df_acerto_motorista_raw"),
    )

    receita = _fmt_moeda(summary.get("faturamento_total_viagens"))
    cp = _fmt_moeda(summary.get("custo_previa_conhecimento"))
    cn = _fmt_moeda(summary.get("custo_nota_itemnota"))
    dg = _fmt_moeda(summary.get("total_despesas_gerais"))
    td = _fmt_moeda(summary.get("total_despesas_tipo_d"))
    custos_op = _fmt_moeda(cp + cn + dg + td)
    resultado = _fmt_moeda(summary.get("saldo_geral"))
    margem = _fmt_pct(summary.get("margem_frete"))

    top_grupos = _top_grupos_despesas(expense.get("despesas"))
    componentes_prev = _componentes_custo_previa(
        filtered["df_viagens_cliente"],
        filtered.get("df_acerto_motorista_raw"),
        apartamento_id,
    )
    viagens = len(filtered["df_viagens_cliente"]) if filtered["df_viagens_cliente"] is not None else 0

    period_n, period_c, sql_params = _period_sql_params(start_date, end_date)
    cte_diag: dict[str, Any] = {}
    nota_diag: dict[str, Any] = {}
    dup_cte_num = 0
    dup_cte_nc: dict[str, Any] = {}
    soma_cte_cancel = 0.0
    soma_nota_cte_canc = 0.0
    codinterno_dup = 0
    despesas_brutas = 0.0
    despesa_n_ved_v = 0.0

    if sati_enabled_for_apartment(app_engine, apartamento_id):
        schema = get_sati_schema(apartamento_id)
        if _SCHEMA_RE.match(schema or ""):
            try:
                cte_diag = _sql_diag_cte(schema, period_c, sql_params)
                nota_diag = _sql_diag_notas(schema, period_n, sql_params)
                dup_cte_num = _sql_cte_dup_numero(schema, period_c, sql_params)
                dup_cte_nc = _sql_cte_dup_numconhec(schema, period_c, sql_params)
                soma_cte_cancel = _fmt_moeda(cte_diag.get("receita_cancelados"))
                soma_nota_cte_canc = _sql_notas_cte_cancelado(schema, period_n, sql_params)
                codinterno_dup = _sql_codinterno_dup(schema, period_n, sql_params)
                despesas_brutas = _sql_despesas_brutas(schema, period_n, sql_params)
                despesa_n_ved_v = _sql_despesa_n_ved_v(schema, period_n, sql_params)
            except Exception as exc:
                cte_diag = {"aviso": str(exc)}

    diff_filtros = _fmt_moeda(max(despesas_brutas - dg, 0)) if despesas_brutas else 0.0
    ativos_sql = int(cte_diag.get("ativos") or 0)
    cancelados = int(cte_diag.get("cancelados") or 0)

    situacao = "neutra"
    if resultado < -1000:
        situacao = "negativa"
    elif resultado > 1000:
        situacao = "positiva"

    filtros: dict[str, str] = {}
    from app.utils.helpers import format_date_br

    if start_date:
        filtros["start_date"] = format_date_br(start_date)
    if end_date:
        filtros["end_date"] = format_date_br(end_date)
    if placa_filter and placa_filter != "Todos":
        filtros["placa"] = placa_filter

    comentario = _comentario_margem(resultado, margem, top_grupos)
    quadro_previa = _quadro_previa_cte(receita, cp, dg, td, resultado, componentes_prev)

    cte_verificacoes = [
        {
            "verificacao": "CT-e ativos no período",
            "resultado": f"{ativos_sql or viagens} viagem(ns)" + (f" (~{viagens} no painel com filtros)" if ativos_sql and viagens != ativos_sql else ""),
        },
        {
            "verificacao": "CT-e cancelados (cancelado = S)",
            "resultado": f"{cancelados} — não entram no BI (cancelado IS DISTINCT FROM 'S')",
        },
        {
            "verificacao": "Receita dos cancelados",
            "resultado": _brl_txt(soma_cte_cancel),
        },
        {
            "verificacao": "CT-e duplicado (mesmo numero interno)",
            "resultado": "Nenhum" if dup_cte_num == 0 else f"{dup_cte_num} grupo(s)",
        },
        {
            "verificacao": "CT-e com mesmo numeroconhecimento + data",
            "resultado": (
                "Nenhum"
                if not int(dup_cte_nc.get("grupos") or 0)
                else f"{int(dup_cte_nc.get('grupos'))} grupo(s), {_brl_txt(dup_cte_nc.get('soma_frete') or 0)} — valores baixos"
            ),
        },
    ]
    cte_conclusao = (
        "Conclusão CT-e: cancelados estão filtrados. Não há duplicação relevante de CT-e explicando a margem."
        if cancelados or dup_cte_num == 0
        else "Conclusão CT-e: verificar cancelados e duplicidades listados acima."
    )

    notas_verificacoes = [
        {
            "verificacao": "Notas canceladas (datacanc preenchido)",
            "resultado": (
                f"{int(nota_diag.get('notas_canceladas') or 0)} no período, "
                f"valor = {_brl_txt(nota_diag.get('valor_notas_canceladas') or 0)} (itens removidos)"
            ),
        },
        {
            "verificacao": "Itens em nota ligada a CT-e cancelado",
            "resultado": _brl_txt(soma_nota_cte_canc),
        },
        {
            "verificacao": "Notas duplicadas (mesmo nº + série + fornecedor + data)",
            "resultado": (
                "Nenhum grupo"
                if not int(nota_diag.get("grupos_notas_duplicadas") or 0)
                else f"{int(nota_diag.get('grupos_notas_duplicadas'))} grupo(s) — ~{_brl_txt(nota_diag.get('soma_notas_duplicadas') or 0)}"
            ),
        },
        {
            "verificacao": "codinterno duplicado",
            "resultado": "0 — não há linha repetida no banco" if codinterno_dup == 0 else f"{codinterno_dup} — investigar",
        },
        {
            "verificacao": "Várias linhas com mesmo codnota + coditem",
            "resultado": "Existe, mas são lançamentos distintos (parcelas, frota, seguro por veículo)",
        },
        {
            "verificacao": "Despesas brutas (nota ativa, despesa=S, ved=V)",
            "resultado": _brl_txt(despesas_brutas) if despesas_brutas else "—",
        },
        {
            "verificacao": "Despesas gerais apuradas (painel BI)",
            "resultado": _brl_txt(dg),
        },
        {
            "verificacao": "Diferença por filtros do BI (grupos, comércio, tiponfe)",
            "resultado": (
                f"~{_brl_txt(diff_filtros)} — não é duplicação"
                if diff_filtros > 0
                else "Sem diferença relevante"
            ),
        },
    ]
    notas_conclusao = (
        "Notas com datacanc não entram nas despesas. codinterno é único por linha — "
        "múltiplas linhas na mesma nota com o mesmo item são parcelas ou rateio por veículo."
    )

    peso_nota = (
        f"Itens com despesa = N e ved = V somam {_brl_txt(despesa_n_ved_v)} no período — "
        "não entram em «Despesas gerais» do painel (regra atual)."
        if despesa_n_ved_v
        else ""
    )
    peso_coment = (
        "Principais grupos em despesas gerais — custos fixos/estruturais somados ao custo de viagem "
        f"(prévia CT-e ≈ {_brl_txt(cp)}). " + (peso_nota or "")
    )

    resumo_causas = _resumo_causas(resultado, cte_diag, nota_diag, dup_cte_nc)

    return {
        "titulo": "Análise geral da margem",
        "situacao": situacao,
        "comentario_geral": comentario,
        "filtros": filtros,
        "secoes": [
            {
                "id": "fechamento",
                "titulo": "Fechamento do painel",
                "descricao": "Valores dos KPIs do painel para o período e filtros atuais.",
                "comentario": comentario,
                "tipo": "linhas",
                "linhas": [
                    {"label": "Receita de frete", "valor": receita},
                    {"label": "Custo prévia CT-e", "valor": cp},
                    {"label": "Custo em notas (viagem)", "valor": cn},
                    {"label": "Despesas gerais", "valor": dg},
                    {"label": "Despesas tipo D", "valor": td},
                    {"label": "Custos operacionais", "valor": custos_op, "destaque": True},
                    {"label": "Resultado líquido", "valor": resultado, "destaque": True},
                    {"label": "Margem sobre frete (%)", "valor": margem, "pct": True},
                ],
            },
            {
                "id": "cte",
                "titulo": "CT-e (conhecimento)",
                "descricao": "Verificações de cancelamento, duplicidade e custo prévia.",
                "tipo": "verificacao_quadro",
                "verificacoes": cte_verificacoes,
                "conclusao": cte_conclusao,
                "quadro_previa": quadro_previa,
            },
            {
                "id": "notas",
                "titulo": "Notas (itemnota)",
                "descricao": "Verificações de cancelamento, duplicidade e classificação de despesas.",
                "tipo": "verificacao",
                "verificacoes": notas_verificacoes,
                "conclusao": notas_conclusao,
            },
            {
                "id": "peso_margem",
                "titulo": "O que pesa na margem (não é duplicação)",
                "descricao": "Principais grupos em despesas gerais (ved=V, despesa=S).",
                "tipo": "grupos",
                "comentario": peso_coment,
                "grupos": top_grupos,
            },
            {
                "id": "custo_previsto",
                "titulo": "Custos apurados — Grupo × Custo prévia CT-e",
                "descricao": "Despesas por grupo (notas) ao lado da composição do custo prévia.",
                "tipo": "duo",
                "grupos": top_grupos,
                "componentes_previsto": componentes_prev,
            },
            {
                "id": "resumo",
                "titulo": "Resumo — causa e impacto na margem",
                "descricao": "Síntese do que explica (ou não) o resultado do período.",
                "tipo": "resumo",
                "causas": resumo_causas,
            },
        ],
    }
