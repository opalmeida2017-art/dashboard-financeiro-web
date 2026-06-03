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


def _filial_label(alias: str = "f") -> str:
    return (
        f"TRIM(CAST(CAST({alias}.codfilial AS INTEGER) AS TEXT)) || ' - ' || "
        f"COALESCE(TRIM({alias}.nome), 'Filial ' || CAST(CAST({alias}.codfilial AS INTEGER) AS TEXT))"
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


def query_fluxo_viagem(schema: str = "c3332") -> str:
    """Fluxo operacional diário: ordem, CT-e, averbação, CIOT, pedágio, MDF-e."""
    emissao = _safe_ts("c.data")
    emissao_oc = _safe_ts("oc.data")
    return f"""
        WITH base AS (
            SELECT
                c.numero,
                c.numeroconhecimento AS num_cte,
                v.placa,
                mot.nome AS motorista,
                {emissao} AS emissao,
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
                mf.codmanif
            FROM {schema}.conhecimento c
            LEFT JOIN {schema}.conhecimentoadic ad ON ad.numero = c.numero
            LEFT JOIN {schema}.veiculo v ON v.codveiculo = c.codveiculo
            LEFT JOIN {schema}.motorista mot ON mot.codmotorista = c.codmotorista
            LEFT JOIN {schema}.ordemcar oc ON oc.codordemcar = c.codordemcar
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
                SELECT m.mdfechave, m.mdfestatus, m.mdfeprot, m.numeromdfe, m.seriemdfe,
                       m.codmanif, m.datafinalizacao, m.valorpedagio, m.pedagioembfretemot
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

            UNION ALL

            SELECT
                NULL::integer AS numero,
                NULL::integer AS num_cte,
                v.placa,
                mot.nome AS motorista,
                {emissao_oc} AS emissao,
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
                NULL::integer AS codmanif
            FROM {schema}.ordemcar oc
            LEFT JOIN {schema}.veiculo v ON v.codveiculo = oc.codveiculo
            LEFT JOIN {schema}.motorista mot ON mot.codmotorista = oc.codmotorista
            WHERE oc.cancelado IS DISTINCT FROM 'S'
              AND NOT EXISTS (
                  SELECT 1 FROM {schema}.conhecimento c2
                  WHERE c2.codordemcar = oc.codordemcar
                    AND c2.cancelado IS DISTINCT FROM 'S'
              )
        )
        SELECT *
        FROM base
        WHERE 1=1
          AND (:start_date IS NULL OR emissao >= :start_date)
          AND (:end_date IS NULL OR emissao <= :end_date)
          {_FILIAL_FILTER_CONHECIMENTO.replace('c.codfilial', 'codfilial')}
        ORDER BY emissao DESC NULLS LAST, placa NULLS LAST
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
            c.permitefaturar,
            c.valorpedagio AS "valorPedagio",
            c.pedagioembutidofrete AS "pedagioEmbutidoFrete",
            c.codcliente,
            c.codmotorista,
            c.codfilial,
            c.codveiculo,
            v.placa AS placaveiculo,
            {_filial_label("f")} AS nomefilial,
            {_filial_label("f")} AS nomefil,
            cli.nome AS nomecliente,
            mot.nome AS nomemotorista,
            mer.descricao AS descricaomercadoria,
            c.pesosaida,
            TRIM(COALESCE(co.nome, '')) || CASE WHEN co.uf IS NOT NULL AND TRIM(co.uf) <> '' THEN ' - ' || TRIM(co.uf) ELSE '' END AS cidorigemformat,
            TRIM(COALESCE(cd.nome, '')) || CASE WHEN cd.uf IS NOT NULL AND TRIM(cd.uf) <> '' THEN ' - ' || TRIM(cd.uf) ELSE '' END AS ciddestinoformat
        FROM {schema}.conhecimento c
        LEFT JOIN {schema}.veiculo v ON v.codveiculo = c.codveiculo
        LEFT JOIN {schema}.filial f ON f.codfilial = c.codfilial
        LEFT JOIN {schema}.cliente cli ON cli.codcliente = c.codcliente
        LEFT JOIN {schema}.motorista mot ON mot.codmotorista = c.codmotorista
        LEFT JOIN {schema}.mercadoria mer ON mer.codmercadoria = c.codmercadoria
        LEFT JOIN {schema}.cidade co ON co.codcidade = c.codcidadeorigem
        LEFT JOIN {schema}.cidade cd ON cd.codcidade = c.codcidadedestino
        WHERE c.cancelado IS DISTINCT FROM 'S'
        {_FILIAL_FILTER_CONHECIMENTO}
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
            c.comissao,
            c.valorquebra,
            c.codfilial,
            v.placa AS placaveiculo,
            {_filial_label("f")} AS nomefilial
        FROM {schema}.conhecimento c
        LEFT JOIN {schema}.veiculo v ON v.codveiculo = c.codveiculo
        LEFT JOIN {schema}.filial f ON f.codfilial = c.codfilial
        WHERE c.cancelado IS DISTINCT FROM 'S'
        {_FILIAL_FILTER_CONHECIMENTO}
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
            {safe_data} AS datacontrole,
            {safe_data} AS datacontroleformat,
            {safe_emissao} AS dataemissao,
            n.codfilial,
            n.codveiculo,
            n.codmotorista,
            v.placa AS placaveiculo,
            v.veiculoproprio,
            {_filial_label("f")} AS nomefilial,
            {_filial_label("f")} AS nomefil,
            it.codgrupo AS codgrupod,
            g.descricao AS "descGrupoD",
            ng.descricao AS descnegocio,
            i.codnota AS "codNota",
            i.codfornecedor AS codforn,
            i.codacertomotorista,
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
        LEFT JOIN {schema}.negocio ng
            ON ng.codnegocio = COALESCE(i.codnegocio, it.codnegocio)
        WHERE 1=1
        {_FILIAL_FILTER_NOTA}
    """


def _query_contas_pagar(schema: str) -> str:
    return f"""
        SELECT
            :apartamento_id AS apartamento_id,
            i.codinterno AS "codItemNota",
            dp.codduplicatapagar,
            dp.codtransacao,
            i.liquido AS liquidoitemnota,
            dp.valorvencimento,
            dp.datapagamento,
            dp.datavencimento AS datavenc,
            dp.codfilial,
            n.serie,
            n.numeronota AS numnota,
            n.codfornecedor AS codforn,
            {_filial_label("f")} AS nomefilial
        FROM {schema}.itemnota i
        INNER JOIN {schema}.nota n ON n.codnota = i.codnota
        LEFT JOIN {schema}.filial f ON f.codfilial = n.codfilial
        LEFT JOIN {schema}.duplicatapagar dp
            ON dp.codnota = n.codnota
            AND dp.codfornecedor = n.codfornecedor
            AND dp.numeronota = n.numeronota
            AND dp.serie = n.serie
        WHERE 1=1
        {_FILIAL_FILTER_NOTA}
    """


def _query_contas_receber(schema: str) -> str:
    return f"""
        SELECT
            :apartamento_id AS apartamento_id,
            dr.codduplicatareceber,
            dr.codtransacao,
            dr.valorvencimento AS valorvenc,
            dr.valorpagamento AS valorpagto,
            dr.datavencimento AS datavenc,
            dr.datapagamento AS datapagto,
            dr.datavencimento AS dataemissao,
            dr.codfatura,
            dr.parcela,
            dr.codbaixa
        FROM {schema}.duplicatareceber dr
        WHERE 1=1
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
        WHERE c.codacertomotorista IS NOT NULL
          AND c.cancelado IS DISTINCT FROM 'S'
        {_FILIAL_FILTER_CONHECIMENTO}
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
        "sati_tables": ["itemnota", "nota", "duplicatapagar"],
        "virtual_columns": ["apartamento_id"],
        "description": "Contas a pagar",
    },
    "relFilContasReceber": {
        "sati_tables": ["duplicatareceber"],
        "virtual_columns": ["apartamento_id"],
        "description": "Contas a receber",
    },
    "relFilAcertoMot": {
        "sati_tables": ["conhecimento", "veiculo"],
        "virtual_columns": ["apartamento_id"],
        "description": "Acerto de motorista por viagem",
    },
}

# Tabelas public.* do BIWEB que não vêm do dump SATI (criar com migration 6 ou sql/criar_tabelas_biweb_apartamento.sql)
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
