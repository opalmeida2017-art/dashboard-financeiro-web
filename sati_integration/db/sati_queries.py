"""
Consultas SQL do BIWEB sobre o banco SATI restaurado (schema c3332).

Mapeamento relFil* -> tabelas SATI:
  relFilViagensCliente   -> c3332.conhecimento (+ veiculo, filial)
  relFilViagensFatCliente -> idem (filtro permitefaturar no app)
  relFilDespesasGerais   -> c3332.itemnota + nota + item + grupo + veiculo + negocio
  relFilContasPagarDet   -> itemnota + nota + duplicatapagar
  relFilContasReceber    -> c3332.duplicatareceber
  relFilAcertoMot        -> c3332.conhecimento (dados de acerto por viagem)
"""

from __future__ import annotations

SATI_QUERY_KEYS = frozenset(
    {
        "relFilViagensCliente",
        "relFilViagensFatCliente",
        "relFilDespesasGerais",
        "relFilContasPagarDet",
        "relFilContasReceber",
        "relFilAcertoMot",
    }
)

_FILIAL_FILTER_CONHECIMENTO = "AND (:cod_filial IS NULL OR c.codfilial = :cod_filial)"
_FILIAL_FILTER_NOTA = "AND (:cod_filial IS NULL OR n.codfilial = :cod_filial)"
_FILIAL_FILTER_DUPLICATA = "AND (:cod_filial IS NULL OR dp.codfilial = :cod_filial)"


# Evita erro Python/psycopg2 (ex.: dataemissao com ano 202500 no SATI)
def _safe_ts(col_expr: str) -> str:
    return f"""CASE
        WHEN {col_expr} IS NULL THEN NULL
        WHEN EXTRACT(YEAR FROM {col_expr}) NOT BETWEEN 1900 AND 2100 THEN NULL
        ELSE {col_expr}
    END"""


def _date_range_clause(col_expr: str) -> str:
    """Filtro opcional por período (:start_date/:end_date NULL = sem filtro)."""
    col = _safe_ts(col_expr)
    return f"""
        AND (:start_date IS NULL OR ({col})::date >= CAST(:start_date AS date))
        AND (:end_date IS NULL OR ({col})::date <= CAST(:end_date AS date))"""


_DATE_VIAGEM = _date_range_clause("c.dataviagemmotorista")
_DATE_NOTA = _date_range_clause("n.data")
_DATE_VENC_PAGAR = _date_range_clause("dp.datavencimento")
_DATE_VENC_RECEBER = _date_range_clause("dr.datavencimento")


def _proprietario_filter_conhecimento(c_alias: str = "c", v_alias: str = "v") -> str:
    return (
        f"AND (:cod_proprietario IS NULL OR "
        f"{c_alias}.codproprietario = :cod_proprietario OR "
        f"{v_alias}.codproprietario = :cod_proprietario)"
    )


def _proprietario_filter_itemnota() -> str:
    """Despesas (itemnota): só codproprietario do item — nota não tem essa coluna no SATI."""
    return (
        "AND (:cod_proprietario IS NULL OR "
        "i.codproprietario = :cod_proprietario)"
    )


def _proprietario_filter_acerto_duplicata(schema: str, dup_alias: str) -> str:
    """Contas ligadas ao proprietário via acertoproprietario (SATI)."""
    return f"""
        AND (
            :cod_proprietario IS NULL
            OR EXISTS (
                SELECT 1 FROM {schema}.acertoproprietario ap
                WHERE ap.codacertoproprietario = {dup_alias}.codacertoproprietario
                  AND ap.codproprietario = :cod_proprietario
            )
        )"""


# Tabelas relFil* que aceitam pushdown de período no SQL (contas usam janela financeira própria).
SATI_TABLES_PERIOD_FILTER = frozenset(
    {
        "relFilViagensCliente",
        "relFilViagensFatCliente",
        "relFilDespesasGerais",
        "relFilAcertoMot",
    }
)


def _filial_label(alias: str = "f") -> str:
    return (
        f"TRIM(CAST(CAST({alias}.codfilial AS INTEGER) AS TEXT)) || ' - ' || "
        f"COALESCE(TRIM({alias}.nome), 'Filial ' || CAST(CAST({alias}.codfilial AS INTEGER) AS TEXT))"
    )


def _unidade_embarque_label(cod_expr: str, alias: str = "ue") -> str:
    """Rótulo da unidade de embarque (SATI: coluna descricao, não nome)."""
    return (
        f"TRIM(CAST(CAST({cod_expr} AS INTEGER) AS TEXT) || ' - ' || "
        f"COALESCE(TRIM({alias}.descricao), TRIM({alias}.nomereduzido), "
        f"'Unidade ' || CAST(CAST({cod_expr} AS INTEGER) AS TEXT)))"
    )


def build_sati_query(table_name: str, schema: str = "c3332") -> str | None:
    """Retorna o SQL parametrizado para a tabela lógica do BIWEB, ou None."""
    builders = {
        "relFilViagensCliente": _query_viagens,
        "relFilViagensFatCliente": _query_viagens_fat,
        "relFilDespesasGerais": _query_despesas,
        "relFilContasPagarDet": _query_contas_pagar,
        "relFilContasReceber": _query_contas_receber,
        "relFilAcertoMot": _query_acerto_motorista,
    }
    builder = builders.get(table_name)
    if not builder:
        return None
    return builder(schema)


def query_embarcadores_cadastro(schema: str = "c3332") -> str:
    """Cadastro completo de embarcadores no SATI (tabela embarcador)."""
    return f"""
        SELECT
            e.codembarcador AS "codEmbarcador",
            TRIM(COALESCE(e.nome, '')) AS nomeembarcador
        FROM {schema}.embarcador e
        WHERE e.codembarcador IS NOT NULL
          AND e.codembarcador > 0
        ORDER BY e.nome NULLS LAST, e.codembarcador
    """


def query_fluxo_viagem(
    schema: str = "c3332",
    *,
    incluir_km_vazio: bool = True,
    somente_com_mdfe_emitido: bool = False,
) -> str:
    """Fluxo operacional diário: ordem, CT-e, averbação, CIOT, pedágio, MDF-e.

    Km vazio = kmini(atual) − kmfim(viagem anterior) no mesmo veículo.
    incluir_km_vazio=True também tenta fallback em manif.kmvazio (coluna do patch).
    """
    emissao = _safe_ts("c.data")
    emissao_oc = _safe_ts("oc.data")
    join_km_vazio = f"""
            LEFT JOIN LATERAL (
                SELECT c_prev.kmfim::numeric AS prev_kmfim
                FROM {schema}.conhecimento c_prev
                WHERE c_prev.codveiculo = c.codveiculo
                  AND c_prev.cancelado IS DISTINCT FROM 'S'
                  AND c_prev.kmfim IS NOT NULL
                  AND (
                    c_prev.dataviagemmotorista < c.dataviagemmotorista
                    OR (
                      c_prev.dataviagemmotorista IS NOT DISTINCT FROM c.dataviagemmotorista
                      AND c_prev.numero < c.numero
                    )
                  )
                ORDER BY c_prev.dataviagemmotorista DESC NULLS LAST, c_prev.numero DESC
                LIMIT 1
            ) lag_km ON TRUE
"""
    if incluir_km_vazio:
        col_km_vazio = """
                CASE
                    WHEN c.kmini IS NOT NULL
                     AND lag_km.prev_kmfim IS NOT NULL
                     AND c.kmini::numeric > lag_km.prev_kmfim
                    THEN (c.kmini::numeric - lag_km.prev_kmfim)
                    ELSE NULLIF(mf.kmvazio, 0)
                END AS km_vazio,"""
        sel_km_vazio_lateral = ",\n                       m.kmvazio"
    else:
        # Sem coluna manif.kmvazio: só o cálculo entre conhecimentos
        col_km_vazio = """
                CASE
                    WHEN c.kmini IS NOT NULL
                     AND lag_km.prev_kmfim IS NOT NULL
                     AND c.kmini::numeric > lag_km.prev_kmfim
                    THEN (c.kmini::numeric - lag_km.prev_kmfim)
                    ELSE NULL
                END AS km_vazio,"""
        sel_km_vazio_lateral = ""
    filtro_mdfe_emitido = ""
    filtro_ordem_sem_mdfe = ""
    if somente_com_mdfe_emitido:
        filtro_mdfe_emitido = """
              AND (
                  NULLIF(TRIM(mf.mdfeprot::text), '') IS NOT NULL
                  OR LOWER(TRIM(COALESCE(mf.mdfestatus::text, ''))) LIKE '%autor%'
                  OR LOWER(TRIM(COALESCE(mf.mdfestatus::text, ''))) IN ('100', '135', 'autorizado')
              )"""
        filtro_ordem_sem_mdfe = " AND 1=0"
    return f"""
        WITH base AS (
            SELECT
                c.numero,
                c.numeroconhecimento AS num_cte,
                v.placa,
                mot.nome AS motorista,
                {emissao} AS emissao,
                {_safe_ts("c.dataviagemmotorista")} AS data_viagem_motorista,
                COALESCE(c.kmini, mf.kmini) AS km_inicial,
                COALESCE(c.kmfim, mf.kmfim) AS km_final,
                NULLIF(c.kmrodado, 0) AS km_rodado,
                mf.kmprevisto AS km_previsto,
                oc.numero AS num_ordem,
                oc.emitida AS nfe_emitida,
                c.codordemcar,
                c.codfilial,
                c.ctechave,
                c.cteprot AS protocolo_cte,
                c.ctestatus,
                NULLIF(TRIM(COALESCE(
                    NULLIF(TRIM(c.ciot::text), ''),
                    mf_dados.ciot_do_manifesto,
                    mf_dados.ciot_manifxml,
                    NULLIF(TRIM(c.numviagopcartao::text), ''),
                    CASE
                        WHEN ad.numeroviagemsimpl IS NOT NULL AND ad.numeroviagemsimpl::text NOT IN ('', '0')
                        THEN TRIM(ad.numeroviagemsimpl::text)
                    END
                )), '') AS ciot,
                c.numautgerrisco AS protocolo_averbacao,
                NULLIF(TRIM(COALESCE(
                    NULLIF(TRIM(c.numeropedagio::text), ''),
                    mf_dados.pedagio_do_manifesto,
                    mf_dados.pedagio_cartao_manifesto,
                    mf_dados.viagem_cartao_manifesto
                )), '') AS numeropedagio,
                NULLIF(TRIM(c.tpvalepedagio::text), '') AS tpvalepedagio,
                mf.valorpedagio AS manif_valorpedagio,
                mf.pedagioembfretemot AS manif_pedagio_emb_mot,
                mf.mdfechave,
                mf.mdfestatus,
                mf.mdfeprot,
                mf.numeromdfe,
                mf.seriemdfe,
                mf.datafinalizacao AS mdfe_data_finalizacao,
                mfe.prot_encerramento AS mdfe_prot_encerramento,
                COALESCE(mf_dados.tem_doc_manifesto, 0) AS tem_documento,
                doc_cte.nomearq_descarga_cte,
                cli.nome AS nomecliente,
                rem.nome AS nome_remetente,
                TRIM(COALESCE(co.nome, '')) || CASE WHEN co.uf IS NOT NULL AND TRIM(co.uf) <> '' THEN ' - ' || TRIM(co.uf) ELSE '' END AS cidorigemformat,
                TRIM(COALESCE(cd.nome, '')) || CASE WHEN cd.uf IS NOT NULL AND TRIM(cd.uf) <> '' THEN ' - ' || TRIM(cd.uf) ELSE '' END AS ciddestinoformat,
                mf.codmanif,
                {col_km_vazio}
                nfe_xml.nfe_notaxml_ok,
                nfe_xml.nfe_numero_notaxml
            FROM {schema}.conhecimento c
            LEFT JOIN {schema}.conhecimentoadic ad ON ad.numero = c.numero
            LEFT JOIN {schema}.veiculo v ON v.codveiculo = c.codveiculo
            LEFT JOIN {schema}.motorista mot ON mot.codmotorista = c.codmotorista
            LEFT JOIN {schema}.ordemcar oc ON oc.codordemcar = c.codordemcar
            LEFT JOIN {schema}.cliente cli ON cli.codcliente = c.codcliente
            LEFT JOIN {schema}.cliente rem ON rem.codcliente = c.codremetente
            LEFT JOIN {schema}.cidade co ON co.codcidade = c.codcidadeorigem
            LEFT JOIN {schema}.cidade cd ON cd.codcidade = c.codcidadedestino
            {join_km_vazio}
            LEFT JOIN LATERAL (
                SELECT
                    'S' AS nfe_notaxml_ok,
                    NULLIF(TRIM(
                        COALESCE(
                            CASE
                                WHEN COALESCE(TRIM(nx.serie::text), '') <> ''
                                THEN TRIM(nx.serie::text) || '/' || TRIM(nx.numeronota::text)
                                ELSE NULLIF(TRIM(nx.numeronota::text), '')
                            END,
                            CASE
                                WHEN COALESCE(TRIM(cn_nfe.serie::text), '') <> ''
                                THEN TRIM(cn_nfe.serie::text) || '/' || TRIM(cn_nfe.numeronota::text)
                                ELSE NULLIF(TRIM(cn_nfe.numeronota::text), '')
                            END
                        )
                    ), '') AS nfe_numero_notaxml
                FROM {schema}.conhecimentonota cn_nfe
                LEFT JOIN {schema}.notaxml nx
                    ON TRIM(cn_nfe.chavenfe::text) = TRIM(nx.chavenfe::text)
                    AND (nx.tipoes IS NULL OR UPPER(TRIM(nx.tipoes::text)) = 'T')
                WHERE cn_nfe.numero = c.numero
                  AND (
                    NULLIF(TRIM(cn_nfe.chavenfe::text), '') IS NOT NULL
                    OR NULLIF(TRIM(cn_nfe.numeronota::text), '') IS NOT NULL
                  )
                ORDER BY
                    CASE WHEN nx.chavenfe IS NOT NULL THEN 0 ELSE 1 END,
                    cn_nfe.datadigitacao DESC NULLS LAST
                LIMIT 1
            ) nfe_xml ON TRUE
            LEFT JOIN LATERAL (
                SELECT
                    MAX(NULLIF(TRIM(c2.ciot::text), '')) AS ciot_do_manifesto,
                    MAX(NULLIF(TRIM(mx.ciot::text), '')) AS ciot_manifxml,
                    MAX(NULLIF(TRIM(c2.numeropedagio::text), '')) AS pedagio_do_manifesto,
                    MAX(NULLIF(TRIM(c2.numerocartaopedagio::text), '')) AS pedagio_cartao_manifesto,
                    MAX(NULLIF(TRIM(c2.numviagopcartao::text), '')) AS viagem_cartao_manifesto,
                    MAX(CASE WHEN d_manif.coddocumento IS NOT NULL THEN 1 ELSE 0 END) AS tem_doc_manifesto
                FROM {schema}.manifconhecimento mc_self
                INNER JOIN {schema}.manifconhecimento mc2 ON mc2.codmanif = mc_self.codmanif
                LEFT JOIN {schema}.conhecimento c2
                    ON c2.numero = mc2.numero AND c2.cancelado IS DISTINCT FROM 'S'
                LEFT JOIN {schema}.manifxml mx ON mx.numero = mc2.numero
                LEFT JOIN {schema}.documento d_manif
                    ON d_manif.nometabela = 'CONHECIMENTO'
                    AND d_manif.chavetabela = mc2.numero
                    AND NULLIF(TRIM(d_manif.nomearq::text), '') IS NOT NULL
                WHERE mc_self.numero = c.numero
            ) mf_dados ON TRUE
            LEFT JOIN LATERAL (
                SELECT MAX(NULLIF(TRIM(d.nomearq::text), '')) AS nomearq_descarga_cte
                FROM {schema}.documento d
                WHERE d.nometabela = 'CONHECIMENTO'
                  AND d.chavetabela = c.numero
                  AND NULLIF(TRIM(d.nomearq::text), '') IS NOT NULL
            ) doc_cte ON TRUE
            LEFT JOIN LATERAL (
                SELECT m.mdfechave, m.mdfestatus, m.mdfeprot, m.numeromdfe, m.seriemdfe,
                       m.codmanif, m.datafinalizacao, m.valorpedagio, m.pedagioembfretemot,
                       m.kmini, m.kmfim, m.kmprevisto{sel_km_vazio_lateral}
                FROM {schema}.manifconhecimento mc
                INNER JOIN {schema}.manif m ON m.codmanif = mc.codmanif
                WHERE mc.numero = c.numero
                ORDER BY m.mdfedatareciboenv DESC NULLS LAST
                LIMIT 1
            ) mf ON TRUE
            LEFT JOIN LATERAL (
                SELECT ev.nprot AS prot_encerramento
                FROM {schema}.manifev ev
                WHERE ev.codmanif = mf.codmanif
                  AND ev.nprot IS NOT NULL
                  AND TRIM(ev.nprot::text) <> ''
                ORDER BY ev.datahorareclote DESC NULLS LAST
                LIMIT 1
            ) mfe ON TRUE
            WHERE c.cancelado IS DISTINCT FROM 'S'
              {filtro_mdfe_emitido}

            UNION ALL

            SELECT
                NULL::integer AS numero,
                NULL::integer AS num_cte,
                v.placa,
                mot.nome AS motorista,
                {emissao_oc} AS emissao,
                NULL::timestamp AS data_viagem_motorista,
                NULL::numeric AS km_inicial,
                NULL::numeric AS km_final,
                NULL::numeric AS km_rodado,
                NULL::numeric AS km_previsto,
                oc.numero AS num_ordem,
                oc.emitida AS nfe_emitida,
                oc.codordemcar,
                oc.codfilial,
                NULL::varchar, NULL::varchar, NULL::varchar, NULL::varchar,
                NULL::varchar, NULL::varchar,
                NULL::varchar,
                NULL::numeric, NULL::varchar,
                NULL::varchar, NULL::varchar, NULL::varchar,
                NULL::integer, NULL::integer,
                NULL::timestamp, NULL::varchar,
                0 AS tem_documento,
                NULL::varchar AS nomearq_descarga_cte,
                NULL::varchar AS nomecliente,
                NULL::varchar AS nome_remetente,
                NULL::varchar AS cidorigemformat,
                NULL::varchar AS ciddestinoformat,
                NULL::integer AS codmanif,
                NULL::numeric AS km_vazio,
                NULL::varchar AS nfe_notaxml_ok,
                NULL::varchar AS nfe_numero_notaxml
            FROM {schema}.ordemcar oc
            LEFT JOIN {schema}.veiculo v ON v.codveiculo = oc.codveiculo
            LEFT JOIN {schema}.motorista mot ON mot.codmotorista = oc.codmotorista
            WHERE oc.cancelado IS DISTINCT FROM 'S'
              {filtro_ordem_sem_mdfe}
              AND NOT EXISTS (
                  SELECT 1 FROM {schema}.conhecimento c2
                  WHERE c2.codordemcar = oc.codordemcar
                    AND c2.cancelado IS DISTINCT FROM 'S'
              )
        )
        SELECT *
        FROM base
        WHERE 1=1
          AND (:start_date IS NULL OR COALESCE(data_viagem_motorista, emissao) >= :start_date)
          AND (:end_date IS NULL OR COALESCE(data_viagem_motorista, emissao) <= :end_date)
          {_FILIAL_FILTER_CONHECIMENTO.replace('c.codfilial', 'codfilial')}
        ORDER BY COALESCE(data_viagem_motorista, emissao) DESC NULLS LAST, placa NULLS LAST
    """


def _query_viagens(schema: str) -> str:
    return f"""
        SELECT
            :apartamento_id AS apartamento_id,
            c.numero,
            c.numeroconhecimento AS "numConhec",
            c.dataviagemmotorista,
            c.data AS dataemissao,
            c.tipofrete,
            c.freteempresa,
            c.fretemotorista,
            c.comissao,
            c.valorquebra,
            c.outrosdescontosmot,
            c.outrosdescontosmot2,
            c.pedagioembfretemot AS "pedagioEmbFretMot",
            c.descsegurosaldomot AS "descSeguroSaldoMot",
            c.valorpedagiomot AS "valorPedagioMot",
            c.permitefaturar,
            c.pagar AS "pagarConhecimento",
            c.kmini,
            c.kmfim,
            c.kmrodado,
            c.vlbasecomissao,
            c.codacertomotorista,
            c.valorpedagio AS "valorPedagio",
            c.pedagioembutidofrete AS "pedagioEmbutidoFrete",
            c.valoricms AS "valorICMS",
            c.icmsembutido AS "icmsEmbutido",
            c.premioseguro AS "premioSeguro",
            c.premioseguro2 AS "premioSeguro2",
            c.descsegurosaldo AS "descSeguroSaldo",
            c.codcliente,
            c.codmotorista,
            c.codfilial,
            c.codunidadeembarque AS "codUnidadeEmb",
            {_unidade_embarque_label("c.codunidadeembarque")} AS nomeunidembarque,
            c.codembarcador AS "codEmbarcador",
            c.codproprietario AS "codProp",
            c.codproprietario AS "codProprietario",
            emb.nome AS nomeembarcador,
            c.codveiculo,
            v.placa AS placaveiculo,
            v.veiculoproprio,
            {_filial_label("f")} AS nomefilial,
            {_filial_label("f")} AS nomefil,
            cli.nome AS nomecliente,
            mot.nome AS nomemotorista,
            mer.descricao AS descricaomercadoria,
            c.pesosaida,
            TRIM(COALESCE(co.nome, '')) || CASE WHEN co.uf IS NOT NULL AND TRIM(co.uf) <> '' THEN ' - ' || TRIM(co.uf) ELSE '' END AS cidorigemformat,
            TRIM(COALESCE(cd.nome, '')) || CASE WHEN cd.uf IS NOT NULL AND TRIM(cd.uf) <> '' THEN ' - ' || TRIM(cd.uf) ELSE '' END AS ciddestinoformat,
            nfe_xml.nfe_numero_notaxml AS "numNotaNF"
        FROM {schema}.conhecimento c
        LEFT JOIN {schema}.veiculo v ON v.codveiculo = c.codveiculo
        LEFT JOIN {schema}.filial f ON f.codfilial = c.codfilial
        LEFT JOIN {schema}.unidadeembarque ue ON ue.codunidadeembarque = c.codunidadeembarque
        LEFT JOIN {schema}.embarcador emb ON emb.codembarcador = c.codembarcador
        LEFT JOIN {schema}.cliente cli ON cli.codcliente = c.codcliente
        LEFT JOIN {schema}.motorista mot ON mot.codmotorista = c.codmotorista
        LEFT JOIN {schema}.mercadoria mer ON mer.codmercadoria = c.codmercadoria
        LEFT JOIN {schema}.cidade co ON co.codcidade = c.codcidadeorigem
        LEFT JOIN {schema}.cidade cd ON cd.codcidade = c.codcidadedestino
        LEFT JOIN LATERAL (
            SELECT NULLIF(TRIM(
                COALESCE(
                    CASE
                        WHEN COALESCE(TRIM(nx.serie::text), '') <> ''
                        THEN TRIM(nx.serie::text) || '/' || TRIM(nx.numeronota::text)
                        ELSE NULLIF(TRIM(nx.numeronota::text), '')
                    END,
                    CASE
                        WHEN COALESCE(TRIM(cn_nfe.serie::text), '') <> ''
                        THEN TRIM(cn_nfe.serie::text) || '/' || TRIM(cn_nfe.numeronota::text)
                        ELSE NULLIF(TRIM(cn_nfe.numeronota::text), '')
                    END
                )
            ), '') AS nfe_numero_notaxml
            FROM {schema}.conhecimentonota cn_nfe
            LEFT JOIN {schema}.notaxml nx
                ON TRIM(cn_nfe.chavenfe::text) = TRIM(nx.chavenfe::text)
                AND (nx.tipoes IS NULL OR UPPER(TRIM(nx.tipoes::text)) = 'T')
            WHERE cn_nfe.numero = c.numero
              AND (
                NULLIF(TRIM(cn_nfe.chavenfe::text), '') IS NOT NULL
                OR NULLIF(TRIM(cn_nfe.numeronota::text), '') IS NOT NULL
              )
            ORDER BY
                CASE WHEN nx.chavenfe IS NOT NULL THEN 0 ELSE 1 END,
                cn_nfe.datadigitacao DESC NULLS LAST
            LIMIT 1
        ) nfe_xml ON TRUE
        WHERE c.cancelado IS DISTINCT FROM 'S'
        {_FILIAL_FILTER_CONHECIMENTO}
        {_DATE_VIAGEM}
        {_proprietario_filter_conhecimento("c")}
    """


def _query_viagens_fat(schema: str) -> str:
    return f"""
        SELECT
            :apartamento_id AS apartamento_id,
            c.numero,
            c.numeroconhecimento AS "numConhec",
            c.dataviagemmotorista,
            c.freteempresa,
            c.fretemotorista,
            c.permitefaturar,
            c.pagar AS "pagarConhecimento",
            c.comissao,
            c.valorquebra,
            c.codfilial,
            c.codembarcador AS "codEmbarcador",
            c.codproprietario AS "codProp",
            c.codproprietario AS "codProprietario",
            emb.nome AS nomeembarcador,
            v.placa AS placaveiculo,
            {_filial_label("f")} AS nomefilial,
            cli.nome AS nomecliente
        FROM {schema}.conhecimento c
        LEFT JOIN {schema}.veiculo v ON v.codveiculo = c.codveiculo
        LEFT JOIN {schema}.filial f ON f.codfilial = c.codfilial
        LEFT JOIN {schema}.embarcador emb ON emb.codembarcador = c.codembarcador
        LEFT JOIN {schema}.cliente cli ON cli.codcliente = c.codcliente
        WHERE c.cancelado IS DISTINCT FROM 'S'
        {_FILIAL_FILTER_CONHECIMENTO}
        {_DATE_VIAGEM}
        {_proprietario_filter_conhecimento("c")}
    """


def _query_despesas(schema: str) -> str:
    safe_data = _safe_ts("n.data")
    safe_emissao = _safe_ts("n.dataemissao")
    return f"""
        SELECT
            :apartamento_id AS apartamento_id,
            i.codinterno AS "codItemNota",
            i.ved,
            i.liquido,
            i.vlcontabil,
            n.serie,
            n.despesa,
            n.tiponfe,
            n.tipo,
            {safe_data} AS datacontrole,
            {safe_data} AS datacontroleformat,
            {safe_emissao} AS dataemissao,
            n.codfilial,
            n.codunidadeembarque AS "codUnidadeEmbarque",
            {_unidade_embarque_label("n.codunidadeembarque")} AS descunidadeembarque,
            n.codveiculo,
            n.codmotorista,
            v.placa AS placaveiculo,
            v.veiculoproprio,
            {_filial_label("f")} AS nomefilial,
            {_filial_label("f")} AS nomefil,
            it.codgrupo AS codgrupod,
            g.descricao AS "descGrupoD",
            it.investimento AS investimento,
            ng.descricao AS descnegocio,
            i.codnota AS "codNota",
            i.codfornecedor AS codforn,
            TRIM(COALESCE(forn.nome, '')) AS nomefornecedor,
            i.codacertomotorista,
            COALESCE(i.codproprietario, v.codproprietario) AS "codProprietario",
            i.codacertoproprietario AS "codAcertoProprietario",
            i.valor,
            i.custototal,
            it.descricao AS descitemd
        FROM {schema}.itemnota i
        INNER JOIN {schema}.nota n
            ON n.codnota = i.codnota
        LEFT JOIN {schema}.item it ON it.coditem = i.coditem
        LEFT JOIN {schema}.grupo g ON g.codgrupo = it.codgrupo
        LEFT JOIN {schema}.veiculo v ON v.codveiculo = COALESCE(i.codveiculo, n.codveiculo)
        LEFT JOIN {schema}.filial f ON f.codfilial = n.codfilial
        LEFT JOIN {schema}.fornecedor forn ON forn.codfornecedor = i.codfornecedor
        LEFT JOIN {schema}.unidadeembarque ue ON ue.codunidadeembarque = n.codunidadeembarque
        LEFT JOIN {schema}.negocio ng
            ON ng.codnegocio = COALESCE(i.codnegocio, it.codnegocio)
        WHERE 1=1
        {_FILIAL_FILTER_NOTA}
        {_DATE_NOTA}
        {_proprietario_filter_itemnota()}
    """


def query_investimento_estoque(schema: str) -> str:
    """Posição de estoque dos itens com investimento=S (cadastro item, não itemnota)."""
    return f"""
        SELECT
            :apartamento_id AS apartamento_id,
            it.coditem,
            it.descricao AS descitemd,
            CAST(it.saldo AS numeric) AS saldo,
            it.custo,
            it.custoultcompra,
            it.investimento,
            g.descricao AS "descGrupoD",
            CAST(it.saldo AS numeric)
                * COALESCE(NULLIF(it.custo, 0), it.custoultcompra, 0) AS valor_estoque
        FROM {schema}.item it
        LEFT JOIN {schema}.grupo g ON g.codgrupo = it.codgrupo
        WHERE UPPER(TRIM(COALESCE(it.investimento::text, ''))) = 'S'
          AND CAST(it.saldo AS numeric) > 0
        ORDER BY valor_estoque DESC
    """


def _query_contas_pagar(schema: str) -> str:
    return f"""
        SELECT
            :apartamento_id AS apartamento_id,
            i.codinterno AS "codItemNota",
            dp.codduplicatapagar,
            dp.codtransacao,
            dp.codacertoproprietario AS "codAcertoProprietario",
            i.liquido AS liquidoitemnota,
            dp.valorvencimento,
            dp.datapagamento,
            dp.datavencimento AS datavenc,
            dp.codfilial,
            n.serie,
            n.numeronota AS numnota,
            n.codfornecedor AS codforn,
            TRIM(COALESCE(forn.nome, '')) AS nomefornecedor,
            {_filial_label("f")} AS nomefilial
        FROM {schema}.itemnota i
        INNER JOIN {schema}.nota n ON n.codnota = i.codnota
        LEFT JOIN {schema}.filial f ON f.codfilial = n.codfilial
        LEFT JOIN {schema}.fornecedor forn ON forn.codfornecedor = n.codfornecedor
        LEFT JOIN {schema}.duplicatapagar dp
            ON dp.codnota = n.codnota
            AND dp.codfornecedor = n.codfornecedor
            AND dp.numeronota = n.numeronota
            AND dp.serie = n.serie
        WHERE 1=1
        {_FILIAL_FILTER_NOTA}
        {_proprietario_filter_acerto_duplicata(schema, "dp")}
    """


def _query_contas_receber(schema: str) -> str:
    return f"""
        SELECT
            :apartamento_id AS apartamento_id,
            dr.codduplicatareceber,
            dr.codtransacao,
            dr.codacertoproprietario AS "codAcertoProprietario",
            dr.valorvencimento AS valorvenc,
            dr.valorpagamento AS valorpagto,
            dr.datavencimento AS datavenc,
            dr.datapagamento AS datapagto,
            dr.datavencimento AS dataemissao,
            dr.codfatura,
            dr.parcela,
            dr.codbaixa,
            TRIM(COALESCE(cli.nome, '')) AS nomecliente
        FROM {schema}.duplicatareceber dr
        LEFT JOIN {schema}.fatura fat ON fat.codfatura = dr.codfatura
        LEFT JOIN {schema}.cliente cli ON cli.codcliente = fat.codcliente
        WHERE 1=1
        {_proprietario_filter_acerto_duplicata(schema, "dr")}
    """


def _query_acerto_motorista(schema: str) -> str:
    return f"""
        SELECT
            :apartamento_id AS apartamento_id,
            c.numero,
            c.numeroconhecimento AS "numConhec",
            c.codacertomotorista,
            c.dataviagemmotorista,
            c.tipofrete,
            c.comissao,
            c.vlbasecomissao AS vlcomissao,
            c.vlbasecomissao AS vlbasecomissaocalc,
            c.kmini,
            c.kmfim,
            c.kmrodado AS kmparc,
            c.fretemotoristasai AS fretemotoristasai,
            c.freteempresasai,
            c.adiantamentomotorista,
            c.valorquebra,
            c.valorpedagio,
            c.cargadescarga,
            c.despesaextra,
            c.outrosdescontosmot,
            c.outrosdescontosmot2,
            c.pesosaidamotorista,
            c.codmotorista,
            c.codveiculo,
            v.placa AS placaveiculo
        FROM {schema}.conhecimento c
        LEFT JOIN {schema}.veiculo v ON v.codveiculo = c.codveiculo
        WHERE c.cancelado IS DISTINCT FROM 'S'
        {_FILIAL_FILTER_CONHECIMENTO}
        {_DATE_VIAGEM}
        {_proprietario_filter_conhecimento("c")}
    """


# Coluna virtual: não existe no SATI; injetada nas queries para compatibilidade com o BIWEB.
SATI_VIRTUAL_COLUMNS = {
    "apartamento_id": "INTEGER — ID do apartamento no BIWEB (tabela public.apartamentos), não existe em c3332",
}

SATI_TABLE_MAP = {
    "relFilViagensCliente": {
        "sati_tables": ["conhecimento", "veiculo", "filial"],
        "virtual_columns": ["apartamento_id"],
        "description": "Viagens / CT-e",
    },
    "relFilViagensFatCliente": {
        "sati_tables": ["conhecimento", "veiculo", "filial"],
        "virtual_columns": ["apartamento_id"],
        "description": "Faturamento de viagens",
    },
    "relFilDespesasGerais": {
        "sati_tables": ["itemnota", "nota", "item", "grupo", "veiculo", "negocio"],
        "virtual_columns": ["apartamento_id"],
        "description": "Despesas gerais (itens de nota)",
    },
    "relFilContasPagarDet": {
        "sati_tables": ["itemnota", "nota", "duplicatapagar", "transacao"],
        "virtual_columns": ["apartamento_id"],
        "description": "Contas a pagar (em aberto: duplicata sem codtransacao)",
    },
    "relFilContasReceber": {
        "sati_tables": ["duplicatareceber", "transacao"],
        "virtual_columns": ["apartamento_id"],
        "description": "Contas a receber (em aberto: duplicata sem codtransacao)",
    },
    "relFilAcertoMot": {
        "sati_tables": ["conhecimento", "veiculo"],
        "virtual_columns": ["apartamento_id"],
        "description": "Acerto de motorista por viagem",
    },
}

# Tabelas public.* do BIWEB que não vêm do dump SATI (criar com migration 6 ou sql/criar_tabelas_biweb_apartamento.sql)
def query_nfe_pendentes_cte(schema: str = "c3332") -> str:
    """
    NFe de transporte (notaxml.tipoes='T') sem CT-e emitido:
    chave da NFe ausente em conhecimento (via conhecimentonota).
    """
    data_nfe = _safe_ts("nx.data")
    return f"""
        SELECT
            nx.codnotaxml,
            nx.nsu,
            nx.chavenfe,
            nx.numeronota,
            nx.serie,
            {data_nfe} AS data_nfe,
            nx.tipoes,
            nx.status,
            nx.sitnfe,
            nx.destnome,
            nx.clientenome,
            TRIM(nx.nome) AS emitente_nome,
            TRIM(nx.clientenome) AS remetente_nome,
            TRIM(nx.destnome) AS destino_nome,
            NULLIF(TRIM(
                (regexp_match(nx.xml::text, '<xProd>([^<]+)</xProd>'))[1]
            ), '') AS mercadoria_nome,
            nx.valor,
            nx.codfilial,
            COALESCE(
                NULLIF(TRIM(UPPER(nx.placa::text)), ''),
                NULLIF(TRIM(UPPER(v.placa::text)), ''),
                'SEM PLACA'
            ) AS placa
        FROM {schema}.notaxml nx
        LEFT JOIN {schema}.veiculo v ON v.codveiculo = nx.codveiculo
        WHERE nx.tipoes = 'T'
          AND nx.chavenfe IS NOT NULL
          AND TRIM(nx.chavenfe::text) <> ''
          AND NOT EXISTS (
              SELECT 1
              FROM {schema}.conhecimento c
              INNER JOIN {schema}.conhecimentonota cn ON cn.numero = c.numero
              WHERE c.cancelado IS DISTINCT FROM 'S'
                AND TRIM(cn.chavenfe::text) = TRIM(nx.chavenfe::text)
          )
          AND (:start_date IS NULL OR {data_nfe} >= :start_date)
          AND (:end_date IS NULL OR {data_nfe} <= :end_date)
          AND (:cod_filial IS NULL OR nx.codfilial = :cod_filial)
        ORDER BY placa NULLS LAST, {data_nfe} DESC NULLS LAST, nx.chavenfe
    """


BIWEB_APARTAMENTO_TABLES = {
    "apartamentos": ["id", "nome_empresa", "slug", "status", "data_criacao", "data_vencimento", "notas_admin"],
    "usuarios": ["id", "apartamento_id", "email", "password_hash", "nome", "role"],
    "static_expense_groups": [
        "apartamento_id", "group_name", "is_despesa", "is_custo_viagem", "incluir_em_tipo_d",
    ],
    "configuracoes_robo": ["apartamento_id", "chave", "valor"],
    "notificacoes": ["id", "apartamento_id", "mensagem", "lida", "timestamp"],
    "tb_logs_robo": ["id", "apartamento_id", "timestamp", "mensagem"],
    "tb_user_activity": ["apartamento_id", "last_seen_timestamp"],
    "despesas_viagem_associadas": ["apartamento_id", "numero", "coditemnota"],
    "despesas_viagem_excluidas": ["apartamento_id", "numero", "coditemnota"],
}
