"""Relatório de inconsistências no banco SATI (nota / itemnota)."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

import pandas as pd
from sqlalchemy import text

from sati_integration.db.sati_queries import _safe_ts
from sati_integration.db.sati_source import (
    get_sati_engine,
    get_sati_schema,
    sati_enabled_for_apartment,
)

_SCHEMA_RE = re.compile(r"^c\d+$", re.I)

_GRUPOS_AUDITORIA = ("SEGURO", "PEDAGIO", "PEDÁGIO", "QUEBRA", "ICMS")


def _numero_nota_expr(alias: str = "n") -> str:
    return f"NULLIF(TRIM(COALESCE({alias}.numeronf::text, {alias}.numeronota::text, '')), '')"


def _data_controle_expr(alias: str = "n") -> str:
    return _safe_ts(f"{alias}.data")


def _despesa_nao(expr: str = "n.despesa") -> str:
    return f"UPPER(TRIM(COALESCE({expr}::text, ''))) = 'N'"


def _valordescontado_vazio(expr: str = "vm.valordescontado") -> str:
    return f"COALESCE({expr}, 0) = 0"


def _ramo_frota(expr: str) -> str:
    return f"UPPER(TRIM(COALESCE({expr}, ''))) = 'FROTA'"


def _serie_rq(expr: str = "n.serie") -> str:
    return f"UPPER(TRIM(COALESCE({expr}::text, ''))) = 'RQ'"


def _sql_nota_ativa(schema: str, alias: str = "n") -> str:
    """Exclui nota cancelada (datacanc) e nota ligada a CT-e cancelado."""
    return f"""{alias}.datacanc IS NULL
          AND NOT EXISTS (
              SELECT 1
              FROM {schema}.conhecimentonota cn
              INNER JOIN {schema}.conhecimento c ON c.numero = cn.numero
              WHERE cn.codnota = {alias}.codnota
                AND UPPER(TRIM(COALESCE(c.cancelado::text, ''))) = 'S'
          )"""


def _grupo_especial_clause(col: str = "g.descricao") -> str:
    parts = []
    for term in _GRUPOS_AUDITORIA:
        esc = term.replace("'", "''")
        parts.append(f"UPPER(TRIM(COALESCE({col}, ''))) LIKE '%{esc}%'")
    return "(" + " OR ".join(parts) + ")"


def _period_clause(col_expr: str, start_date: date | datetime | None, end_date: date | datetime | None) -> tuple[str, dict]:
    clauses: list[str] = []
    params: dict[str, Any] = {}
    col = _safe_ts(col_expr)
    if start_date:
        clauses.append(f"({col})::date >= CAST(:start_date AS date)")
        params["start_date"] = start_date
    if end_date:
        clauses.append(f"({col})::date <= CAST(:end_date AS date)")
        params["end_date"] = end_date
    if not clauses:
        return "", params
    return " AND " + " AND ".join(clauses), params


def _fmt_data(val) -> str | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, (datetime, date)):
        return val.strftime("%d/%m/%Y")
    try:
        return pd.Timestamp(val).strftime("%d/%m/%Y")
    except Exception:
        return str(val)


def _fmt_moeda(val) -> float:
    try:
        n = float(val)
        return round(n, 2) if pd.notna(n) else 0.0
    except (TypeError, ValueError):
        return 0.0


def _query_notas_duplicadas(schema: str, period_sql: str) -> str:
    num = _numero_nota_expr("n")
    dt = _data_controle_expr("n")
    return f"""
        WITH base AS (
            SELECT
                n.codnota,
                {num} AS numero,
                TRIM(COALESCE(n.serie::text, '')) AS serie,
                n.codfornecedor,
                TRIM(COALESCE(forn.nome, '')) AS fornecedor,
                ({dt})::date AS datacontrole
            FROM {schema}.nota n
            LEFT JOIN {schema}.fornecedor forn ON forn.codfornecedor = n.codfornecedor
            WHERE {num} IS NOT NULL
              AND n.codfornecedor IS NOT NULL
              AND {_sql_nota_ativa(schema)}
              {period_sql}
        ),
        grupos AS (
            SELECT numero, serie, codfornecedor, datacontrole, COUNT(*) AS qtd
            FROM base
            WHERE datacontrole IS NOT NULL
            GROUP BY numero, serie, codfornecedor, datacontrole
            HAVING COUNT(*) > 1
        )
        SELECT
            b.codnota,
            b.numero,
            b.serie,
            b.codfornecedor,
            b.fornecedor,
            b.datacontrole,
            g.qtd AS qtd_duplicadas
        FROM base b
        INNER JOIN grupos g
            ON g.numero = b.numero
           AND g.serie IS NOT DISTINCT FROM b.serie
           AND g.codfornecedor = b.codfornecedor
           AND g.datacontrole IS NOT DISTINCT FROM b.datacontrole
        ORDER BY b.datacontrole DESC NULLS LAST, b.fornecedor, b.numero, b.codnota
    """


def _query_frota_despesa_n(schema: str, period_sql: str, *, apenas_serie_rq: bool = False) -> str:
    """Notas com itens FROTA e flag despesa = N (inconsistência operacional)."""
    num = _numero_nota_expr("n")
    dt = _data_controle_expr("n")
    if apenas_serie_rq:
        serie_sql = f"AND ({_serie_rq()})"
    else:
        serie_sql = f"AND NOT ({_serie_rq()})"
    return f"""
        SELECT DISTINCT
            n.codnota,
            {num} AS numero,
            TRIM(COALESCE(n.serie::text, '')) AS serie,
            UPPER(TRIM(COALESCE(n.despesa::text, ''))) AS despesa,
            ({dt})::date AS datacontrole,
            TRIM(COALESCE(forn.nome, '')) AS fornecedor,
            COUNT(i.codinterno) OVER (PARTITION BY n.codnota) AS qtd_itens_frota
        FROM {schema}.nota n
        INNER JOIN {schema}.itemnota i ON i.codnota = n.codnota
        LEFT JOIN {schema}.item it ON it.coditem = i.coditem
        LEFT JOIN {schema}.negocio ng
            ON ng.codnegocio = COALESCE(i.codnegocio, it.codnegocio)
        LEFT JOIN {schema}.fornecedor forn ON forn.codfornecedor = n.codfornecedor
        WHERE {_ramo_frota("ng.descricao")}
          AND ({_despesa_nao()})
          AND {_sql_nota_ativa(schema)}
          {serie_sql}
          {period_sql}
        ORDER BY datacontrole DESC NULLS LAST, fornecedor, numero
    """


def _query_itens_grupos_especiais(schema: str, period_sql: str) -> str:
    num = _numero_nota_expr("n")
    dt = _data_controle_expr("n")
    return f"""
        SELECT
            i.codinterno AS coditemnota,
            n.codnota,
            {num} AS numero,
            TRIM(COALESCE(n.serie::text, '')) AS serie,
            ({dt})::date AS datacontrole,
            TRIM(COALESCE(forn.nome, '')) AS fornecedor,
            TRIM(COALESCE(g.descricao, '')) AS grupo,
            TRIM(COALESCE(it.descricao, '')) AS item,
            UPPER(TRIM(COALESCE(ng.descricao, ''))) AS ramo,
            COALESCE(i.liquido, i.valor, 0)::numeric AS valor
        FROM {schema}.itemnota i
        INNER JOIN {schema}.nota n ON n.codnota = i.codnota
        LEFT JOIN {schema}.item it ON it.coditem = i.coditem
        LEFT JOIN {schema}.grupo g ON g.codgrupo = it.codgrupo
        LEFT JOIN {schema}.negocio ng
            ON ng.codnegocio = COALESCE(i.codnegocio, it.codnegocio)
        LEFT JOIN {schema}.fornecedor forn
            ON forn.codfornecedor = COALESCE(i.codfornecedor, n.codfornecedor)
        WHERE {_grupo_especial_clause()}
          AND {_sql_nota_ativa(schema)}
          {period_sql}
        ORDER BY datacontrole DESC NULLS LAST, grupo, fornecedor, numero
    """


def _query_veiculomulta_despesa(schema: str, period_sql: str) -> str:
    """
    Nota gerada a partir de veiculomulta (codnota) com valordescontado vazio
    e flag despesa = N (inconsistência — conta a pagar deve ter despesa = S).
    """
    num = _numero_nota_expr("n")
    dt = _data_controle_expr("n")
    vd_vazio = _valordescontado_vazio()
    return f"""
        SELECT
            vm.codveiculomulta,
            vm.codnota,
            {num} AS numero,
            TRIM(COALESCE(n.serie::text, '')) AS serie,
            UPPER(TRIM(COALESCE(n.despesa::text, ''))) AS despesa,
            'S' AS despesa_esperada,
            COALESCE(vm.valordescontado, 0)::numeric AS valordescontado,
            COALESCE(vm.valormulta, 0)::numeric AS valormulta,
            TRIM(COALESCE(vm.numero, '')) AS num_multa,
            ({dt})::date AS datacontrole,
            TRIM(COALESCE(forn.nome, '')) AS fornecedor
        FROM {schema}.veiculomulta vm
        INNER JOIN {schema}.nota n ON n.codnota = vm.codnota
        LEFT JOIN {schema}.fornecedor forn
            ON forn.codfornecedor = COALESCE(vm.codfornecedor, n.codfornecedor)
        WHERE vm.codnota IS NOT NULL
          AND vm.codnota > 0
          AND {vd_vazio}
          AND ({_despesa_nao()})
          AND {_sql_nota_ativa(schema)}
          {period_sql}
        ORDER BY datacontrole DESC NULLS LAST, fornecedor, numero
    """


def _linhas_duplicadas(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    linhas: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        numero = row.get("numero") or "—"
        serie = row.get("serie") or ""
        nota = f"{serie}/{numero}" if serie else str(numero)
        linhas.append(
            {
                "codnota": int(row["codnota"]) if pd.notna(row.get("codnota")) else None,
                "nota": nota,
                "fornecedor": row.get("fornecedor") or "—",
                "datacontrole": _fmt_data(row.get("datacontrole")),
                "qtd_duplicadas": int(row.get("qtd_duplicadas") or 0),
            }
        )
    return linhas


def _linhas_frota(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    linhas: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        numero = row.get("numero") or "—"
        serie = row.get("serie") or ""
        nota = f"{serie}/{numero}" if serie else str(numero)
        linhas.append(
            {
                "codnota": int(row["codnota"]) if pd.notna(row.get("codnota")) else None,
                "nota": nota,
                "fornecedor": row.get("fornecedor") or "—",
                "datacontrole": _fmt_data(row.get("datacontrole")),
                "despesa": row.get("despesa") or "—",
                "qtd_itens_frota": int(row.get("qtd_itens_frota") or 0),
            }
        )
    return linhas


def _linhas_grupos(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    linhas: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        numero = row.get("numero") or "—"
        serie = row.get("serie") or ""
        nota = f"{serie}/{numero}" if serie else str(numero)
        linhas.append(
            {
                "coditemnota": int(row["coditemnota"]) if pd.notna(row.get("coditemnota")) else None,
                "codnota": int(row["codnota"]) if pd.notna(row.get("codnota")) else None,
                "nota": nota,
                "fornecedor": row.get("fornecedor") or "—",
                "datacontrole": _fmt_data(row.get("datacontrole")),
                "grupo": row.get("grupo") or "—",
                "item": row.get("item") or "—",
                "ramo": row.get("ramo") or "—",
                "valor": _fmt_moeda(row.get("valor")),
            }
        )
    return linhas


def _linhas_veiculomulta(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    linhas: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        numero = row.get("numero") or "—"
        serie = row.get("serie") or ""
        nota = f"{serie}/{numero}" if serie else str(numero)
        vd = _fmt_moeda(row.get("valordescontado"))
        linhas.append(
            {
                "codveiculomulta": int(row["codveiculomulta"])
                if pd.notna(row.get("codveiculomulta"))
                else None,
                "codnota": int(row["codnota"]) if pd.notna(row.get("codnota")) else None,
                "nota": nota,
                "num_multa": row.get("num_multa") or "—",
                "fornecedor": row.get("fornecedor") or "—",
                "datacontrole": _fmt_data(row.get("datacontrole")),
                "despesa": row.get("despesa") or "—",
                "despesa_esperada": row.get("despesa_esperada") or "—",
                "valordescontado": vd,
                "valormulta": _fmt_moeda(row.get("valormulta")),
            }
        )
    return linhas


def _km_vazio_expr(expr: str) -> str:
    """KM não preenchido: NULL ou zero."""
    return f"({expr} IS NULL OR COALESCE({expr}::numeric, 0) = 0)"


def _query_ctes_sem_km(schema: str, period_sql: str) -> str:
    """CT-es sem kmini e kmfim no conhecimento (período = data da viagem / emissão)."""
    dt = "COALESCE(c.dataviagemmotorista, c.data)"
    return f"""
        SELECT
            c.numero,
            c.numeroconhecimento AS num_cte,
            ({_safe_ts(dt)})::date AS data_viagem,
            TRIM(COALESCE(v.placa, '')) AS placa,
            TRIM(COALESCE(mot.nome, '')) AS motorista,
            TRIM(COALESCE(cli.nome, '')) AS cliente,
            TRIM(COALESCE(co.nome, '')) || CASE
                WHEN co.uf IS NOT NULL AND TRIM(co.uf) <> '' THEN ' - ' || TRIM(co.uf)
                ELSE ''
            END AS origem,
            TRIM(COALESCE(cd.nome, '')) || CASE
                WHEN cd.uf IS NOT NULL AND TRIM(cd.uf) <> '' THEN ' - ' || TRIM(cd.uf)
                ELSE ''
            END AS destino,
            c.kmini::numeric AS km_inicial,
            c.kmfim::numeric AS km_final,
            NULLIF(c.kmrodado::numeric, 0) AS km_rodado
        FROM {schema}.conhecimento c
        LEFT JOIN {schema}.veiculo v ON v.codveiculo = c.codveiculo
        LEFT JOIN {schema}.motorista mot ON mot.codmotorista = c.codmotorista
        LEFT JOIN {schema}.cliente cli ON cli.codcliente = c.codcliente
        LEFT JOIN {schema}.cidade co ON co.codcidade = c.codcidadeorigem
        LEFT JOIN {schema}.cidade cd ON cd.codcidade = c.codcidadedestino
        WHERE UPPER(TRIM(COALESCE(c.cancelado::text, ''))) IS DISTINCT FROM 'S'
          AND {_km_vazio_expr("c.kmini")}
          AND {_km_vazio_expr("c.kmfim")}
          {period_sql}
        ORDER BY ({_safe_ts(dt)}) DESC NULLS LAST, c.numero DESC
        LIMIT 500
    """


def _linhas_ctes_sem_km(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    linhas: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        num_cte = row.get("num_cte")
        numero = row.get("numero")
        try:
            num_cte_i = int(num_cte) if pd.notna(num_cte) else None
        except (TypeError, ValueError):
            num_cte_i = None
        try:
            numero_i = int(numero) if pd.notna(numero) else None
        except (TypeError, ValueError):
            numero_i = None
        cte_lbl = str(num_cte_i) if num_cte_i is not None else "—"
        if numero_i is not None:
            cte_lbl = f"{cte_lbl} \\ {numero_i}" if cte_lbl != "—" else str(numero_i)
        origem = str(row.get("origem") or "").strip()
        destino = str(row.get("destino") or "").strip()
        rota = f"{origem} \\ {destino}" if origem and destino else (origem or destino or "—")
        km_rod = row.get("km_rodado")
        try:
            km_rod_f = float(km_rod) if pd.notna(km_rod) else None
        except (TypeError, ValueError):
            km_rod_f = None
        linhas.append(
            {
                "cte": cte_lbl,
                "numero": numero_i,
                "num_cte": num_cte_i,
                "data_viagem": _fmt_data(row.get("data_viagem")),
                "placa": row.get("placa") or "—",
                "motorista": row.get("motorista") or "—",
                "cliente": row.get("cliente") or "—",
                "rota": rota,
                "km_inicial": "—",
                "km_final": "—",
                "km_rodado": round(km_rod_f, 0) if km_rod_f is not None else None,
            }
        )
    return linhas


def _sql_cte_valido_mesma_nota(alias: str = "c") -> str:
    """CT-e válido para checagem de nota duplicada: não cancelado, autorizado, pagar=S e a faturar=S."""
    st = f"UPPER(TRIM(COALESCE({alias}.ctestatus::text, '')))"
    return f"""
          UPPER(TRIM(COALESCE({alias}.cancelado::text, ''))) IS DISTINCT FROM 'S'
          AND (
            {st} IN ('2', '100', '135')
            OR LOWER(TRIM(COALESCE({alias}.ctestatus::text, ''))) LIKE '%autor%'
            OR NULLIF(TRIM({alias}.ctechave::text), '') IS NOT NULL
            OR NULLIF(TRIM({alias}.cteprot::text), '') IS NOT NULL
          )
          AND UPPER(TRIM(COALESCE({alias}.pagar::text, ''))) = 'S'
          AND UPPER(TRIM(COALESCE({alias}.permitefaturar::text, ''))) = 'S'
    """


def _query_ctes_mesma_nota(schema: str, period_sql: str) -> str:
    """CT-es distintos com a mesma NF-e; ignora cancelado, não autorizado e flags pagar/a faturar desmarcadas."""
    dt = "COALESCE(c.dataviagemmotorista, c.data)"
    return f"""
        WITH base AS (
            SELECT
                c.numero,
                c.numeroconhecimento AS num_cte,
                ({_safe_ts(dt)})::date AS data_viagem,
                TRIM(COALESCE(v.placa, '')) AS placa,
                TRIM(COALESCE(cli.nome, '')) AS cliente,
                NULLIF(TRIM(cn.chavenfe::text), '') AS chave,
                NULLIF(TRIM(cn.numeronota::text), '') AS numeronota,
                TRIM(COALESCE(cn.serie::text, '')) AS serie,
                cn.codnota,
                CASE
                    WHEN NULLIF(TRIM(cn.chavenfe::text), '') IS NOT NULL
                    THEN 'chave:' || TRIM(cn.chavenfe::text)
                    ELSE 'num:' || TRIM(COALESCE(cn.serie::text, '')) || '/' || TRIM(cn.numeronota::text)
                END AS nota_key,
                CASE
                    WHEN COALESCE(TRIM(cn.serie::text), '') <> ''
                    THEN TRIM(cn.serie::text) || '/' || TRIM(cn.numeronota::text)
                    ELSE NULLIF(TRIM(cn.numeronota::text), '')
                END AS nota_lbl
            FROM {schema}.conhecimentonota cn
            INNER JOIN {schema}.conhecimento c ON c.numero = cn.numero
            LEFT JOIN {schema}.veiculo v ON v.codveiculo = c.codveiculo
            LEFT JOIN {schema}.cliente cli ON cli.codcliente = c.codcliente
            LEFT JOIN {schema}.nota n ON n.codnota = cn.codnota
            WHERE {_sql_cte_valido_mesma_nota("c")}
              AND (n.codnota IS NULL OR n.datacanc IS NULL)
              AND (
                NULLIF(TRIM(cn.chavenfe::text), '') IS NOT NULL
                OR NULLIF(TRIM(cn.numeronota::text), '') IS NOT NULL
              )
              {period_sql}
        ),
        grupos AS (
            SELECT nota_key, COUNT(DISTINCT numero) AS qtd_ctes
            FROM base
            WHERE nota_key IS NOT NULL
            GROUP BY nota_key
            HAVING COUNT(DISTINCT numero) > 1
        )
        SELECT
            b.numero,
            b.num_cte,
            b.data_viagem,
            b.placa,
            b.cliente,
            b.chave,
            b.numeronota,
            b.serie,
            b.nota_lbl,
            b.nota_key,
            g.qtd_ctes
        FROM base b
        INNER JOIN grupos g ON g.nota_key = b.nota_key
        ORDER BY g.qtd_ctes DESC, b.nota_key, b.data_viagem DESC NULLS LAST, b.numero
        LIMIT 800
    """


def _linhas_ctes_mesma_nota(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    linhas: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        num_cte = row.get("num_cte")
        numero = row.get("numero")
        try:
            num_cte_i = int(num_cte) if pd.notna(num_cte) else None
        except (TypeError, ValueError):
            num_cte_i = None
        try:
            numero_i = int(numero) if pd.notna(numero) else None
        except (TypeError, ValueError):
            numero_i = None
        cte_lbl = str(num_cte_i) if num_cte_i is not None else "—"
        if numero_i is not None:
            cte_lbl = f"{cte_lbl} \\ {numero_i}" if cte_lbl != "—" else str(numero_i)
        chave = str(row.get("chave") or "").strip()
        nota = str(row.get("nota_lbl") or "").strip() or "—"
        try:
            qtd = int(row["qtd_ctes"]) if pd.notna(row.get("qtd_ctes")) else None
        except (TypeError, ValueError):
            qtd = None
        linhas.append(
            {
                "cte": cte_lbl,
                "numero": numero_i,
                "num_cte": num_cte_i,
                "data_viagem": _fmt_data(row.get("data_viagem")),
                "placa": row.get("placa") or "—",
                "cliente": row.get("cliente") or "—",
                "nota": nota,
                "chave": (chave[:20] + "...") if len(chave) > 24 else (chave or "—"),
                "chave_completa": chave or "—",
                "qtd_ctes": qtd,
            }
        )
    return linhas


def get_db_inconsistencias(
    apartamento_id: int,
    start_date: date | datetime | None = None,
    end_date: date | datetime | None = None,
) -> dict[str, Any]:
    from app.data.database import engine as app_engine

    if not sati_enabled_for_apartment(app_engine, apartamento_id):
        return {"error": "Consulta disponível apenas com banco SATI restaurado (PostgreSQL)."}

    schema = get_sati_schema(apartamento_id)
    if not _SCHEMA_RE.match(schema or ""):
        return {"error": f"Schema SATI inválido: {schema!r}"}

    period_sql, period_params = _period_clause("n.data", start_date, end_date)
    period_cte_sql, period_cte_params = _period_clause(
        "COALESCE(c.dataviagemmotorista, c.data)", start_date, end_date
    )

    try:
        engine = get_sati_engine()
        with engine.connect() as conn:
            df_dup = pd.read_sql(
                text(_query_notas_duplicadas(schema, period_sql)),
                conn,
                params=period_params,
            )
            df_frota = pd.read_sql(
                text(_query_frota_despesa_n(schema, period_sql, apenas_serie_rq=False)),
                conn,
                params=period_params,
            )
            df_frota_os = pd.read_sql(
                text(_query_frota_despesa_n(schema, period_sql, apenas_serie_rq=True)),
                conn,
                params=period_params,
            )
            df_grupos = pd.read_sql(
                text(_query_itens_grupos_especiais(schema, period_sql)),
                conn,
                params=period_params,
            )
            df_vm = pd.read_sql(
                text(_query_veiculomulta_despesa(schema, period_sql)),
                conn,
                params=period_params,
            )
            df_km = pd.read_sql(
                text(_query_ctes_sem_km(schema, period_cte_sql)),
                conn,
                params=period_cte_params,
            )
            df_mesma_nota = pd.read_sql(
                text(_query_ctes_mesma_nota(schema, period_cte_sql)),
                conn,
                params=period_cte_params,
            )
    except Exception as exc:
        return {"error": f"Erro ao consultar SATI: {exc}"}

    linhas_dup = _linhas_duplicadas(df_dup)
    linhas_frota = _linhas_frota(df_frota)
    linhas_frota_os = _linhas_frota(df_frota_os)
    linhas_grupos = _linhas_grupos(df_grupos)
    linhas_vm = _linhas_veiculomulta(df_vm)
    linhas_km = _linhas_ctes_sem_km(df_km)
    linhas_mesma_nota = _linhas_ctes_mesma_nota(df_mesma_nota)

    filtros: dict[str, str] = {}
    from app.utils.helpers import format_date_br

    if start_date:
        filtros["start_date"] = format_date_br(start_date)
    if end_date:
        filtros["end_date"] = format_date_br(end_date)
    filtros["exclui"] = (
        "notas canceladas (datacanc); CT-es cancelados, não autorizados "
        "ou com pagar/a faturar desmarcado"
    )

    return {
        "titulo": "Inconsistências do banco SATI",
        "filtros": filtros,
        "secoes": [
            {
                "id": "ctes_mesma_nota",
                "titulo": "CT-es com a mesma nota vinculada",
                "descricao": (
                    "Mais de um CT-e no período compartilhando a mesma NF-e "
                    "(chave ou série/número em conhecimentonota). "
                    "Desconsidera: CT-e cancelado, não autorizado, pagar conhecimento desmarcado "
                    "e a faturar (permitefaturar) desmarcado; notas com datacanc também são ignoradas."
                ),
                "total": len(linhas_mesma_nota),
                "linhas": linhas_mesma_nota,
            },
            {
                "id": "ctes_sem_km",
                "titulo": "CT-es sem KM inicial e KM final",
                "descricao": (
                    "Viagens (conhecimento) no período da tela em que kmini e kmfim "
                    "estão vazios ou zero — impede o cálculo de KM vazio."
                ),
                "total": len(linhas_km),
                "linhas": linhas_km,
            },
            {
                "id": "notas_duplicadas",
                "titulo": "Notas duplicadas",
                "descricao": "Mesmo número, mesma série, mesmo fornecedor e mesma data de controle.",
                "total": len(linhas_dup),
                "linhas": linhas_dup,
            },
            {
                "id": "frota_despesa_n",
                "titulo": "Itens FROTA com nota despesa = N",
                "descricao": (
                    "Notas (série diferente de RQ) com itens de ramo FROTA cuja flag "
                    "despesa da nota está marcada como N."
                ),
                "total": len(linhas_frota),
                "linhas": linhas_frota,
            },
            {
                "id": "frota_os_despesa_n",
                "titulo": "Itens FROTA com Ordem de serviço despesa = N",
                "descricao": (
                    "Ordens de serviço (série RQ) com itens de ramo FROTA cuja flag "
                    "despesa da nota está marcada como N."
                ),
                "total": len(linhas_frota_os),
                "linhas": linhas_frota_os,
            },
            {
                "id": "grupos_especiais",
                "titulo": "Itens em grupos Seguro, Pedágio, Quebra ou ICMS",
                "descricao": "Relação de itens cujo grupo contém seguro, pedágio, quebra ou ICMS.",
                "total": len(linhas_grupos),
                "linhas": linhas_grupos,
            },
            {
                "id": "veiculomulta_despesa",
                "titulo": "Multa (veiculomulta) com despesa = N indevida",
                "descricao": (
                    "Nota gerada a partir de veiculomulta (codnota) com valor descontado "
                    "vazio (NULL ou 0) e flag despesa = N — deveria ser despesa = S (conta a pagar)."
                ),
                "total": len(linhas_vm),
                "linhas": linhas_vm,
            },
        ],
        "total_geral": (
            len(linhas_mesma_nota)
            + len(linhas_km)
            + len(linhas_dup)
            + len(linhas_frota)
            + len(linhas_frota_os)
            + len(linhas_grupos)
            + len(linhas_vm)
        ),
    }
