# Forçando a atualização para o deploy

import os
import time
import pandas as pd
from sqlalchemy import text
from datetime import datetime, timedelta
from slugify import slugify
from app.data import database as db
from app.data.database import engine
from app import config
import numpy as np
import re
from app.data import database as db_module
import psycopg2
import psycopg2.extras
from sati_integration.db.sati_source import (
    fetch_sati_dataframe,
    get_sati_engine,
    get_sati_schema,
    is_sati_data_table,
    resolve_cod_filial,
    sati_enabled_for_apartment,
)
from sati_integration.db.sati_queries import (
    query_fluxo_viagem,
    query_investimento_estoque,
    query_nfe_pendentes_cte,
)
from app.core import dre_viagem as dre
from app.utils.dre_tenant_config import obter_dre_opts
from app.utils.bi_metas import formatar_delta_pct, obter_metas_bi, status_vs_meta

# Cache em memória dos DataFrames SATI (evita recarregar 6 tabelas a cada requisição)
_DF_CACHE: dict[tuple, tuple[float, pd.DataFrame]] = {}
_DF_CACHE_TTL = int(os.environ.get("BIWEB_CACHE_TTL", "300"))
_FILTER_OPTS_CACHE: dict[tuple, tuple[float, object]] = {}
_FILTER_OPTS_TTL = int(os.environ.get("BIWEB_FILTER_OPTS_TTL", "3600"))
_SYNC_GROUPS_AT: dict[int, float] = {}
_SYNC_GROUPS_TTL = int(os.environ.get("BIWEB_SYNC_GROUPS_TTL", "600"))


def _df_cache_scope() -> str:
    """Isola cache por tenant/banco (apartamento_id=1 em todos os clientes Debian)."""
    return (
        os.getenv("BI_TENANT_SLUG", "").strip().lower()
        or os.getenv("BI_PG_DATABASE", "").strip().lower()
        or os.getenv("DATABASE_URL", "").strip()
        or "default"
    )


def _df_cache_key(
    apartamento_id: int,
    table_name: str,
    start_date=None,
    end_date=None,
) -> tuple:
    sd = ed = ""
    if start_date is not None:
        sd = start_date.date().isoformat() if hasattr(start_date, "date") else str(start_date)
    if end_date is not None:
        ed = end_date.date().isoformat() if hasattr(end_date, "date") else str(end_date)
    return (_df_cache_scope(), apartamento_id, table_name, sd, ed)


def clear_data_cache(apartamento_id: int | None = None):
    """Limpa cache após upload/coleta SATI ou troca de tenant."""
    global _DF_CACHE, _SYNC_GROUPS_AT, _FILTER_OPTS_CACHE
    if apartamento_id is None:
        _DF_CACHE.clear()
        _SYNC_GROUPS_AT.clear()
        _FILTER_OPTS_CACHE.clear()
        return
    keys = [k for k in _DF_CACHE if len(k) >= 2 and k[1] == apartamento_id]
    for k in keys:
        del _DF_CACHE[k]
    opt_keys = [k for k in _FILTER_OPTS_CACHE if len(k) >= 2 and k[1] == apartamento_id]
    for k in opt_keys:
        del _FILTER_OPTS_CACHE[k]
    _SYNC_GROUPS_AT.pop(apartamento_id, None)


def _cached_filter_options(apartamento_id: int, cache_key: str, factory):
    """Cache de listas de filtro (placa/filial/etc.) — independe do período."""
    ck = (_df_cache_scope(), apartamento_id, cache_key)
    now = time.time()
    hit = _FILTER_OPTS_CACHE.get(ck)
    if hit and (now - hit[0]) < _FILTER_OPTS_TTL:
        return hit[1]
    val = factory()
    _FILTER_OPTS_CACHE[ck] = (now, val)
    return val


def _dict_get_ci(d: dict, *keys, default=None):
    """Busca valor em dict ignorando maiúsculas/minúsculas do nome da chave."""
    if not d:
        return default
    lower = {str(k).lower(): k for k in d.keys()}
    for key in keys:
        orig = lower.get(str(key).lower())
        if orig is not None:
            val = d[orig]
            if val is None or (isinstance(val, float) and np.isnan(val)):
                continue
            return val
    return default


def _agregar_acerto_motorista(acerto: pd.DataFrame) -> dict:
    """Agrega km/comissão do acerto usando nomes de coluna do SATI ou Excel."""
    if acerto.empty:
        return {}
    cm = _get_case_insensitive_column_map(acerto.columns)
    specs = [
        (("kmini", "kmIni"), "min", "kmIni"),
        (("kmfim", "kmFim"), "max", "kmFim"),
        (("kmparc", "kmParc", "kmrodado"), "sum", "kmParc"),
        (("comissao",), lambda s: s.iloc[0] if len(s) else 0, "comissao"),
        (("vlbasecomissaocalc", "vlbasecomissao", "vlcomissao"), "sum", "vlBaseComissaoCalc"),
    ]
    agg_dict = {}
    out_keys = {}
    for keys, func, out_name in specs:
        col = next((cm[k] for k in keys if k in cm), None)
        if col:
            agg_dict[col] = func
            out_keys[col] = out_name
    if not agg_dict:
        return {}
    row = acerto.agg(agg_dict)
    result = {}
    for col, out_name in out_keys.items():
        val = row[col] if col in row.index else 0
        result[out_name] = 0 if pd.isna(val) else val
    return result


def _km_comissao_relatorio(viagem_data: dict, acerto_data: dict) -> dict:
    """KM e comissão — base e líquido via regra universal (dre.calcular_frete_motorista_liquido)."""
    km_ini = acerto_data.get("kmIni")
    if km_ini is None or (isinstance(km_ini, (int, float)) and km_ini == 0):
        km_ini = _dict_get_ci(viagem_data, "kmini", "kmIni", default=0)
    km_fim = acerto_data.get("kmFim")
    if km_fim is None or (isinstance(km_fim, (int, float)) and km_fim == 0):
        km_fim = _dict_get_ci(viagem_data, "kmfim", "kmFim", default=0)
    km_rod = acerto_data.get("kmParc")
    if km_rod is None or (isinstance(km_rod, (int, float)) and km_rod == 0):
        km_rod = _dict_get_ci(viagem_data, "kmrodado", "kmparc", "kmParc", default=0)
    if (not km_rod or km_rod == 0) and km_ini and km_fim and float(km_fim) >= float(km_ini):
        km_rod = float(km_fim) - float(km_ini)

    comissao = acerto_data.get("comissao")
    if comissao is None or comissao == 0:
        comissao = _dict_get_ci(viagem_data, "comissao", default=0)

    dados = dre.extrair_dados_frete_motorista(viagem_data)
    comissao_acerto = (
        acerto_data.get("vlComissao")
        or acerto_data.get("vlBaseComissaoCalc")
        or _dict_get_ci(
            viagem_data,
            "vlcomissao",
            "vlbasecomissaocalc",
            "vlbasecomissao",
            default=0,
        )
        or 0
    )
    mot = dre.calcular_frete_motorista_liquido(
        comissao_acerto=float(comissao_acerto or 0),
        comissao_pct=dados["comissao_pct"],
        **{k: dados[k] for k in (
            "fretemotorista", "valor_quebra", "tipo_frete", "valor_pedagio_mot",
            "pedagio_emb_mot", "valor_seguro", "valor_seguro2", "desc_seguro_mot",
            "outros_descontos_mot",
        )},
    )
    tf = dados["tipo_frete"]
    base = mot["base_comissao"] if tf == "P" else dados["fretemotorista"]
    valor_liquido = mot["liquido"]
    valor_comissao = mot["comissao_valor"] if tf == "P" else valor_liquido

    return {
        "km_inicial": float(km_ini or 0),
        "km_final": float(km_fim or 0),
        "km_rodado": float(km_rod or 0),
        "comissao_perc": float(comissao or 0),
        "valor_base_comissao": float(base or 0),
        "valor_comissao_calculada": float(valor_comissao or 0),
        "frete_motorista_liquido": float(valor_liquido or 0),
    }


def _janela_sugestao_despesas(
    df_viagens: pd.DataFrame,
    placa: str,
    data_viagem_obj,
    numero_atual: int,
) -> tuple[pd.Timestamp | None, pd.Timestamp | None, str | None]:
    """
    Da data da viagem atual até o dia anterior à próxima viagem da mesma placa.
    """
    if df_viagens is None or df_viagens.empty or not placa or pd.isna(data_viagem_obj):
        return None, None, None
    cm = _get_case_insensitive_column_map(df_viagens.columns)
    col_placa = cm.get("placaveiculo")
    col_data = cm.get("dataviagemmotorista")
    col_num = cm.get("numero", "numero")
    if not col_placa or not col_data or col_data not in df_viagens.columns:
        return None, None, None

    data_ini = pd.Timestamp(data_viagem_obj).normalize()
    df_placa = df_viagens[df_viagens[col_placa].astype(str).str.upper() == str(placa).upper()].copy()
    if df_placa.empty:
        return data_ini, data_ini, None

    df_placa["_dt"] = pd.to_datetime(df_placa[col_data], errors="coerce")
    proximas = df_placa[
        (df_placa[col_num] != numero_atual)
        & (df_placa["_dt"] > data_ini)
    ].sort_values("_dt")
    if proximas.empty:
        return data_ini, data_ini, None

    proxima_dt = pd.Timestamp(proximas.iloc[0]["_dt"]).normalize()
    data_fim = proxima_dt - pd.Timedelta(days=1)
    if data_fim < data_ini:
        data_fim = data_ini
    proxima_fmt = proxima_dt.strftime("%d/%m/%Y")
    return data_ini, data_fim, proxima_fmt


def _sanitize_for_json(obj):
    """Converte Timestamp/numpy para tipos nativos (API JSON e PDF)."""
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_for_json(v) for v in obj]
    if isinstance(obj, (pd.Timestamp, datetime)):
        return None if pd.isna(obj) else obj.isoformat()
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return None if pd.isna(obj) else float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    try:
        if pd.isna(obj):
            return None
    except (TypeError, ValueError):
        pass
    return obj


def _codtransacao_vazio(val) -> bool:
    """Sem confirmação na tabela transacao (codtransacao vazio/nulo)."""
    if val is None:
        return True
    try:
        if pd.isna(val):
            return True
    except (TypeError, ValueError):
        pass
    txt = str(val).strip()
    return txt == "" or txt.lower() in ("none", "nan", "null")


def _filtrar_financeiro_aberto(df: pd.DataFrame, tipo: str = "pagar") -> pd.DataFrame:
    """
    Contas a pagar/receber em aberto no SATI.
    Quitado = codtransacao preenchido (baixa na transacao) ou data de pagamento informada.
    """
    if df.empty:
        return df
    cm = _get_case_insensitive_column_map(df.columns)
    out = df.copy()

    if tipo == "pagar":
        dup_col = cm.get("codduplicatapagar")
        if not dup_col:
            return pd.DataFrame(columns=df.columns)
        out = out[out[dup_col].notna()]
        pag_col = cm.get("datapagamento")
    else:
        pag_col = cm.get("datapagto") or cm.get("datapagamento")

    trans_col = cm.get("codtransacao")
    if trans_col and trans_col in out.columns:
        out = out[out[trans_col].apply(_codtransacao_vazio)]
    if pag_col and pag_col in out.columns:
        out = out[out[pag_col].isna()]

    return out


FINANCEIRO_VENCIMENTO_MIN = datetime(2000, 1, 1)


def _ontem_data() -> pd.Timestamp:
    return pd.Timestamp.now().normalize() - pd.Timedelta(days=1)


def _coluna_valor_financeiro(cm: dict, tipo: str) -> str | None:
    if tipo == "pagar":
        return cm.get("liquidoitemnota") or cm.get("valorvencimento")
    return cm.get("valorvenc") or cm.get("valorvencimento")


def _resumo_financeiro_pendente(df: pd.DataFrame, tipo: str = "pagar") -> dict:
    """
    KPI financeiro: em aberto (sem transação confirmada).
    - total_periodo: vencimento de 01/01/2000 até ontem
    - vencido: títulos em aberto com vencimento anterior a hoje
    - futuro: títulos em aberto com vencimento após ontem
    """
    vazio = {
        "total_periodo": 0.0,
        "vencido": 0.0,
        "futuro": 0.0,
        "total_aberto": 0.0,
    }
    df_ab = _filtrar_financeiro_aberto(df, tipo)
    if df_ab.empty:
        return vazio
    cm = _get_case_insensitive_column_map(df_ab.columns)
    venc_col = cm.get("datavenc")
    val_col = _coluna_valor_financeiro(cm, tipo)
    if not val_col:
        return vazio

    valores = pd.to_numeric(df_ab[val_col], errors="coerce").fillna(0)
    if venc_col and venc_col in df_ab.columns:
        datas = pd.to_datetime(df_ab[venc_col], errors="coerce").dt.normalize()
    else:
        datas = pd.Series(pd.NaT, index=df_ab.index)

    hoje = pd.Timestamp.now().normalize()
    ontem = _ontem_data()
    inicio = pd.Timestamp(FINANCEIRO_VENCIMENTO_MIN.date())

    mask_valor = valores != 0
    mask_com_data = datas.notna()
    mask_periodo = mask_com_data & (datas >= inicio) & (datas <= ontem)
    mask_futuro = mask_com_data & (datas > ontem)
    mask_vencido = mask_com_data & (datas < hoje)
    mask_sem_data = ~mask_com_data

    total_periodo = float(valores[mask_valor & (mask_periodo | mask_sem_data)].sum())
    vencido = float(valores[mask_valor & mask_vencido & (mask_periodo | mask_sem_data)].sum())
    futuro = float(valores[mask_valor & mask_futuro].sum())
    total_aberto = float(valores[mask_valor].sum())

    return {
        "total_periodo": total_periodo,
        "vencido": vencido,
        "futuro": futuro,
        "total_aberto": total_aberto,
    }


def _filtrar_financeiro_linhas_periodo(df: pd.DataFrame, tipo: str) -> pd.DataFrame:
    """Linhas em aberto com vencimento até ontem (ou sem data) — composição do KPI."""
    df_ab = _filtrar_financeiro_aberto(df, tipo)
    if df_ab.empty:
        return df_ab
    cm = _get_case_insensitive_column_map(df_ab.columns)
    venc_col = cm.get("datavenc")
    if not venc_col or venc_col not in df_ab.columns:
        return df_ab
    datas = pd.to_datetime(df_ab[venc_col], errors="coerce").dt.normalize()
    ontem = _ontem_data()
    inicio = pd.Timestamp(FINANCEIRO_VENCIMENTO_MIN.date())
    mask = datas.isna() | ((datas >= inicio) & (datas <= ontem))
    return df_ab[mask].copy()


def _calcular_contas_pagar_pendentes(df_cp: pd.DataFrame) -> float:
    """SATI: em aberto, vencimento 01/01/2000 até ontem."""
    return _resumo_financeiro_pendente(df_cp, "pagar")["total_periodo"]


def _calcular_contas_receber_pendentes(df_cr: pd.DataFrame) -> float:
    """SATI: em aberto, vencimento 01/01/2000 até ontem."""
    return _resumo_financeiro_pendente(df_cr, "receber")["total_periodo"]


def _coluna_filial(col_map: dict) -> str | None:
    for key in ("nomefil", "nomefilial"):
        if key in col_map:
            return col_map[key]
    return None


def _normalizar_coluna_filial(df: pd.DataFrame) -> pd.DataFrame:
    """Unifica nomefil / nomefilial e remove colunas duplicadas (SATI envia as duas)."""
    if df.empty:
        return df
    df = df.copy()
    col_map = _get_case_insensitive_column_map(df.columns)
    cols_filial = []
    for key in ("nomefil", "nomefilial"):
        if key in col_map:
            cols_filial.append(col_map[key])
    if cols_filial:
        df["nomefil"] = df[cols_filial[0]]
        for col in cols_filial:
            if col in df.columns and col != "nomefil":
                df = df.drop(columns=[col])
    return df.loc[:, ~df.columns.duplicated()]


def _bloco_composicao_despesa(df: pd.DataFrame, categoria: str) -> pd.DataFrame:
    """Extrai só as colunas necessárias para o gráfico de composição por filial."""
    if df.empty:
        return pd.DataFrame(columns=["valor_calculado", "nomefil", "categoria"])
    bloco = _normalizar_coluna_filial(df.assign(categoria=categoria))
    for col in ("valor_calculado", "nomefil", "categoria"):
        if col not in bloco.columns:
            bloco[col] = pd.NA if col == "nomefil" else (categoria if col == "categoria" else 0)
    return bloco[["valor_calculado", "nomefil", "categoria"]]


def sync_expense_groups_if_needed(apartamento_id: int):
    now = time.time()
    last = _SYNC_GROUPS_AT.get(apartamento_id, 0)
    if now - last < _SYNC_GROUPS_TTL:
        return
    sync_expense_groups(apartamento_id)
    _SYNC_GROUPS_AT[apartamento_id] = now


def get_data_as_dataframe(
    table_name: str,
    apartamento_id: int,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> pd.DataFrame:
    """
    Busca dados de uma tabela para um apartamento.
    Com SATI ativo, start_date/end_date aplicam filtro no SQL (tabelas operacionais).
    """
    cache_key = _df_cache_key(apartamento_id, table_name, start_date, end_date)
    now = time.time()
    cached = _DF_CACHE.get(cache_key)
    if cached and (now - cached[0]) < _DF_CACHE_TTL:
        return cached[1].copy()

    if os.getenv("BIWEB_SATI_RESTORING", "").strip():
        print(f"AVISO: Restore SATI em andamento — '{table_name}' retorna vazio temporariamente.")
        return pd.DataFrame()

    if is_sati_data_table(table_name, apartamento_id):
        try:
            df = fetch_sati_dataframe(
                db.engine, table_name, apartamento_id, start_date, end_date
            )
            df = _fix_invalid_dates(df, table_name)
            _DF_CACHE[cache_key] = (now, df)
            return df.copy()
        except Exception as e:
            print(f"ERRO CRÍTICO ao carregar SATI '{table_name}': {e}")
            return pd.DataFrame()

    if not db.table_exists(table_name):
        print(f"AVISO: Tabela '{table_name}' não existe. Retornando DataFrame vazio.")
        return pd.DataFrame()
    try:
        with db.engine.connect() as conn:
            query = text(f'SELECT * FROM "{table_name}" WHERE apartamento_id = :apt_id')
            df = pd.read_sql_query(query, conn, params={"apt_id": apartamento_id})
            
            # CORREÇÃO: Adicionado .strip() para limpar os espaços
            df.columns = [str(col).strip() for col in df.columns]
            
            # --- NOVA LINHA ADICIONADA ---
            # Chama a função de correção de datas antes de retornar o DataFrame
            df = _fix_invalid_dates(df, table_name)
            _DF_CACHE[cache_key] = (now, df)
            return df.copy()
    except Exception as e:
        print(f"ERRO CRÍTICO ao carregar dados da tabela '{table_name}': {e}")
        return pd.DataFrame()

def _get_case_insensitive_column_map(df_columns):
    """Cria um dicionário para mapear nomes de colunas em minúsculas para seus nomes originais."""
    return {col.lower(): col for col in df_columns}


# Ramo de negócio no SATI (tabela negocio / cadastro do item)
TIPO_NEGOCIO_FROTA = "FROTA"
TIPO_NEGOCIO_FRETE = "FRETE/AGENCIAMENTO"
RAMO_NEGOCIO_COMERCIO = "COMERCIO"
GRUPO_VENDA_MARCADOR = "VENDA"
TIPOS_NEGOCIO_PADRAO = (TIPO_NEGOCIO_FROTA, TIPO_NEGOCIO_FRETE)

# veiculo.veiculoproprio — cadastro SATI (placas e filtro Negócio por veículo)
VEICULOPROPRIO_COD_FROTA = frozenset({"S", "F"})
VEICULOPROPRIO_COD_FRETE = frozenset({"N", "R", "A", "M"})
LABEL_VEICULOPROPRIO = {
    "S": "Próprio Prod.",
    "F": "Apoio Frota",
    "R": "Apoio Frete",
    "N": "Terceiros",
    "A": "Agregado",
    "M": "Agregado Misto",
}
TIPOS_PLACA_FROTA = frozenset({"Próprio Prod.", "Apoio Frota", "Próprio"})

# conhecimento.tipofrete — classificação de receita (P/A/S)
TIPOFRETE_COD_FROTA = frozenset({"P"})
TIPOFRETE_COD_FRETE = frozenset({"A", "S"})


def _filial_display_label(cod_filial, nome_filial) -> str:
    cod = str(cod_filial).strip() if pd.notna(cod_filial) else ""
    nome = str(nome_filial).strip() if pd.notna(nome_filial) else ""
    if cod and nome and not nome.startswith(f"{cod} -"):
        return f"{cod} - {nome}"
    if cod:
        return f"{cod} - {nome}" if nome else f"{cod} - Filial {cod}"
    return nome or "Filial Desconhecida"


def _coletar_filiais_de_df(df: pd.DataFrame, col_map: dict) -> list[str]:
    labels = []
    cod_col = col_map.get("codfilial")
    nome_col = next((col_map[c] for c in ("nomefilial", "nomefil") if c in col_map), None)
    if not nome_col:
        return labels
    if cod_col:
        for _, row in df[[cod_col, nome_col]].drop_duplicates().iterrows():
            nome = str(row[nome_col]).strip() if pd.notna(row[nome_col]) else ""
            if not nome:
                continue
            if re.match(r"^\d+\s*-\s*", nome):
                labels.append(nome)
            else:
                labels.append(_filial_display_label(row[cod_col], nome))
    else:
        labels.extend(
            n for n in df[nome_col].dropna().astype(str).str.strip().unique() if n
        )
    return labels


def _coletar_unidades_embarque_de_df(df: pd.DataFrame, col_map: dict) -> list[str]:
    labels: list[str] = []
    nome_col = next(
        (
            col_map[c]
            for c in ("nomeunidembarque", "nomeunidembar", "descunidadeembarque")
            if c in col_map
        ),
        None,
    )
    cod_col = col_map.get("codunidadeembarque") or col_map.get("codunidadeemb")
    if not nome_col:
        return labels
    if cod_col:
        for _, row in df[[cod_col, nome_col]].drop_duplicates().iterrows():
            nome = str(row[nome_col]).strip() if pd.notna(row[nome_col]) else ""
            if not nome:
                continue
            if re.match(r"^\d+\s*-\s*", nome):
                labels.append(nome)
            else:
                labels.append(_filial_display_label(row[cod_col], nome))
    else:
        labels.extend(
            n for n in df[nome_col].dropna().astype(str).str.strip().unique() if n
        )
    return labels


def _coletar_embarcadores_de_df(df: pd.DataFrame, col_map: dict) -> list[dict]:
    """Lista embarcadores com codembarcador preenchido (conhecimento)."""
    cod_col = col_map.get("codembarcador")
    nome_col = col_map.get("nomeembarcador") or col_map.get("embarcadornome")
    if not cod_col:
        return []
    out: list[dict] = []
    cols = [cod_col] + ([nome_col] if nome_col else [])
    for _, row in df[cols].drop_duplicates().iterrows():
        cod_raw = row[cod_col]
        if pd.isna(cod_raw):
            continue
        try:
            cod_num = int(float(cod_raw))
        except (TypeError, ValueError):
            continue
        if cod_num <= 0:
            continue
        nome = ""
        if nome_col and pd.notna(row.get(nome_col)):
            nome = str(row[nome_col]).strip()
        label = f"{cod_num} - {nome}" if nome else str(cod_num)
        out.append({"cod": str(cod_num), "nome": nome, "label": label})
    return out


def _aplicar_filtro_embarcador(df: pd.DataFrame, embarcador_filter: str) -> pd.DataFrame:
    """Mantém CT-es com codembarcador preenchido e igual ao código selecionado."""
    if df.empty or not embarcador_filter or str(embarcador_filter).strip() in ("", "Todos"):
        return df
    col_map = _get_case_insensitive_column_map(df.columns)
    cod_col = col_map.get("codembarcador")
    if not cod_col:
        return df.iloc[0:0].copy()
    try:
        cod_alvo = int(float(str(embarcador_filter).strip()))
    except (TypeError, ValueError):
        return df.iloc[0:0].copy()
    series = pd.to_numeric(df[cod_col], errors="coerce")
    mask = series.notna() & (series > 0) & (series == cod_alvo)
    return df[mask].copy()


def _aplicar_filtro_lista_colunas(
    df_filtrado: pd.DataFrame,
    col_map: dict,
    valores: list,
    chaves_config: str,
) -> pd.DataFrame:
    if not valores or "Todos" in valores:
        return df_filtrado
    cols_possiveis = config.FILTER_COLUMN_MAPS.get(chaves_config, [])
    coluna_para_usar = None
    for col_lower in [c.lower() for c in cols_possiveis]:
        if col_lower in col_map:
            col_original = col_map[col_lower]
            if not df_filtrado[col_original].dropna().empty:
                coluna_para_usar = col_original
                break
    if not coluna_para_usar:
        return df_filtrado
    valores_upper = [str(v).strip().upper() for v in valores if v]
    if not valores_upper:
        return df_filtrado
    return df_filtrado[
        df_filtrado[coluna_para_usar].astype(str).str.strip().str.upper().isin(valores_upper)
    ]


def _normalizar_veiculoproprio(val) -> str:
    return str(val or "").strip().upper()


def _veiculoproprio_eh_frota(val) -> bool:
    return _normalizar_veiculoproprio(val) in VEICULOPROPRIO_COD_FROTA


def _veiculoproprio_eh_frete(val) -> bool:
    v = _normalizar_veiculoproprio(val)
    if not v:
        return True
    return v not in VEICULOPROPRIO_COD_FROTA


def _tipo_placa_label_eh_frota(tipo_label: str) -> bool:
    return str(tipo_label or "").strip() in TIPOS_PLACA_FROTA


def _label_tipo_placa_veiculoproprio(val) -> str:
    """Rótulo SATI veiculo.veiculoproprio (cadastro de veículo)."""
    return LABEL_VEICULOPROPRIO.get(_normalizar_veiculoproprio(val), "Terceiros")


def _incluirateio_sim(val) -> bool:
    return str(val or "").strip().upper() == "S"


def _mapa_veiculos_sati(
    apartamento_id: int,
    cod_proprietario: int | None = None,
) -> dict[str, dict]:
    """placa → metadados do cadastro SATI veiculo (veiculoproprio, incluirateio)."""
    if not sati_enabled_for_apartment(engine, apartamento_id):
        return {}
    if cod_proprietario is None:
        cod_proprietario = obter_cod_proprietario_filtro(apartamento_id)
    try:
        schema = get_sati_schema(apartamento_id)
        if not re.match(r"^c\d+$", schema, re.I):
            return {}
        filtro_prop = ""
        params: dict = {}
        if cod_proprietario is not None:
            filtro_prop = " AND codproprietario = :cod_proprietario"
            params["cod_proprietario"] = cod_proprietario
        sql = text(
            f"""
            SELECT UPPER(TRIM(placa)) AS placa, veiculoproprio, incluirateio
            FROM {schema}.veiculo
            WHERE NULLIF(TRIM(placa), '') IS NOT NULL
            {filtro_prop}
            """
        )
        with get_sati_engine().connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        out: dict[str, dict] = {}
        for placa, vp, ir in rows:
            if not placa:
                continue
            placa_limpa = str(placa).strip().upper()
            cod_vp = _normalizar_veiculoproprio(vp)
            out[placa_limpa] = {
                "veiculoproprio": cod_vp,
                "incluirateio": str(ir or "").strip().upper(),
                "tipo": _label_tipo_placa_veiculoproprio(cod_vp),
            }
        return out
    except Exception as exc:
        if "incluirateio" in str(exc).lower():
            return _mapa_veiculos_sati_sem_rateio(apartamento_id, cod_proprietario)
        print(f"Aviso mapa veiculos SATI: {exc}")
        return {}


def _mapa_veiculos_sati_sem_rateio(
    apartamento_id: int,
    cod_proprietario: int | None = None,
) -> dict[str, dict]:
    """Fallback quando o schema SATI não possui incluirateio."""
    mapa_vp = _mapa_placas_veiculo_sati_legacy(apartamento_id, cod_proprietario)
    return {
        placa: {
            "veiculoproprio": cod,
            "incluirateio": "",
            "tipo": _label_tipo_placa_veiculoproprio(cod),
        }
        for placa, cod in mapa_vp.items()
    }


def _mapa_placas_veiculo_sati_legacy(
    apartamento_id: int,
    cod_proprietario: int | None = None,
) -> dict[str, str]:
    if not sati_enabled_for_apartment(engine, apartamento_id):
        return {}
    if cod_proprietario is None:
        cod_proprietario = obter_cod_proprietario_filtro(apartamento_id)
    try:
        schema = get_sati_schema(apartamento_id)
        if not re.match(r"^c\d+$", schema, re.I):
            return {}
        filtro_prop = ""
        params: dict = {}
        if cod_proprietario is not None:
            filtro_prop = " AND codproprietario = :cod_proprietario"
            params["cod_proprietario"] = cod_proprietario
        sql = text(
            f"""
            SELECT UPPER(TRIM(placa)) AS placa, veiculoproprio
            FROM {schema}.veiculo
            WHERE NULLIF(TRIM(placa), '') IS NOT NULL
            {filtro_prop}
            """
        )
        with get_sati_engine().connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return {
            str(placa).strip().upper(): _normalizar_veiculoproprio(vp)
            for placa, vp in rows
            if placa
        }
    except Exception as exc:
        print(f"Aviso mapa placas veiculo SATI: {exc}")
        return {}


def _mapa_placas_veiculo_sati(apartamento_id: int) -> dict[str, str]:
    """placa → código veiculoproprio a partir da tabela veiculo."""
    return {placa: meta["veiculoproprio"] for placa, meta in _mapa_veiculos_sati(apartamento_id).items()}


def _lista_placas_rateio(apartamento_id: int) -> list[str]:
    """Placas com veiculo.incluirateio = S (participam do rateio tipo D)."""
    return sorted(
        placa
        for placa, meta in _mapa_veiculos_sati(apartamento_id).items()
        if _incluirateio_sim(meta.get("incluirateio"))
    )


def _filtrar_lista_placas_por_tipo_negocio(
    placas: list[dict],
    tipo_negocio_filter: str,
) -> list[dict]:
    if not tipo_negocio_filter or tipo_negocio_filter == "Todos":
        return placas
    tipo = tipo_negocio_filter.upper().strip()
    out: list[dict] = []
    for item in placas:
        cod = _normalizar_veiculoproprio(item.get("veiculoproprio"))
        if tipo == TIPO_NEGOCIO_FROTA and _veiculoproprio_eh_frota(cod):
            out.append(item)
        elif (
            tipo == TIPO_NEGOCIO_FRETE.upper()
            or "FRETE" in tipo
            or "AGENCIAMENTO" in tipo
            or "TERCEIRO" in tipo
        ) and _veiculoproprio_eh_frete(cod):
            out.append(item)
    return out


def _filtrar_viagens_por_tipo_negocio(df: pd.DataFrame, col_map: dict, tipo_negocio_filter: str) -> pd.DataFrame:
    """Filtro Negócio: veículo (veiculoproprio). Receita/DRE continua por conhecimento.tipofrete."""
    if df.empty or not tipo_negocio_filter or tipo_negocio_filter == "Todos":
        return df
    tipo = tipo_negocio_filter.upper().strip()
    eh_frete = (
        tipo == TIPO_NEGOCIO_FRETE.upper()
        or "FRETE" in tipo
        or "AGENCIAMENTO" in tipo
        or "TERCEIRO" in tipo
    )

    if "veiculoproprio" in col_map:
        vp = df[col_map["veiculoproprio"]].astype(str).str.upper().str.strip()
        if tipo == TIPO_NEGOCIO_FROTA:
            return df[vp.isin(VEICULOPROPRIO_COD_FROTA)].copy()
        if eh_frete:
            return df[~vp.isin(VEICULOPROPRIO_COD_FROTA)].copy()

    if "tipofrete" not in col_map:
        return df
    tf = df[col_map["tipofrete"]].astype(str).str.upper().str.strip()
    if tipo == TIPO_NEGOCIO_FROTA:
        return df[tf.isin(TIPOFRETE_COD_FROTA)].copy()
    if eh_frete:
        return df[tf.isin(TIPOFRETE_COD_FRETE)].copy()
    return pd.DataFrame(columns=df.columns)


def _limite_data_operacional() -> pd.Timestamp:
    """Último dia aceito para gráficos (evita vencimentos futuros distorcerem o eixo)."""
    return pd.Timestamp(datetime.now().date()) + pd.Timedelta(days=31)


def _serie_data_controle(df: pd.DataFrame, col_map: dict | None = None) -> pd.Series:
    """Escolhe a melhor coluna de data (evita colisão datacontrole vs dataControle)."""
    if df.empty:
        return pd.Series(dtype="datetime64[ns]")
    if col_map is None:
        col_map = _get_case_insensitive_column_map(df.columns)
    melhor_serie = None
    melhor_count = -1
    for key in ("datacontrole", "dataemissao", "dataviagemmotorista", "datacontroleformat"):
        if key not in col_map:
            continue
        col = col_map[key]
        if col not in df.columns:
            continue
        serie = df[col] if pd.api.types.is_datetime64_any_dtype(df[col]) else pd.to_datetime(df[col], errors="coerce")
        validos = int(serie.notna().sum())
        if validos > melhor_count:
            melhor_count = validos
            melhor_serie = serie
    if melhor_serie is None:
        return pd.Series(pd.NaT, index=df.index)
    limite = _limite_data_operacional()
    minimo = pd.Timestamp("1990-01-01")
    melhor_serie = melhor_serie.mask((melhor_serie < minimo) | (melhor_serie > limite))
    return melhor_serie


def get_default_date_range(apartamento_id: int) -> tuple[datetime, datetime]:
    """Sem filtro na URL: período definido no painel (configuracoes_robo.BI_PERIODO_PADRAO)."""
    try:
        from app.utils.periodo_padrao import (
            CHAVE_CONFIG,
            PERIODO_PADRAO_DEFAULT,
            calcular_intervalo_periodo_padrao,
            normalizar_periodo_padrao,
        )
    except ImportError:
        from utils.periodo_padrao import (
            CHAVE_CONFIG,
            PERIODO_PADRAO_DEFAULT,
            calcular_intervalo_periodo_padrao,
            normalizar_periodo_padrao,
        )

    periodo = PERIODO_PADRAO_DEFAULT
    try:
        cfg = ler_configuracoes_robo(apartamento_id)
        periodo = normalizar_periodo_padrao(cfg.get(CHAVE_CONFIG))
    except Exception:
        pass
    return calcular_intervalo_periodo_padrao(periodo)


def resolver_intervalo_consulta(
    apartamento_id: int,
    start_date: datetime | None,
    end_date: datetime | None,
) -> tuple[datetime, datetime]:
    if start_date and end_date:
        if start_date > end_date:
            start_date, end_date = end_date, start_date
        return start_date, end_date
    return get_default_date_range(apartamento_id)


def resolver_intervalo_fluxo(
    apartamento_id: int,
    start_date: datetime | None,
    end_date: datetime | None,
) -> tuple[datetime, datetime]:
    """Período do fluxo operacional — só usa datas da própria tela (não o preset do painel BI)."""
    _ = apartamento_id
    hoje = datetime.now()
    fim_padrao = hoje.replace(hour=23, minute=59, second=59, microsecond=0)
    inicio_padrao = datetime(hoje.year, hoje.month, 1)
    if start_date and end_date:
        if start_date > end_date:
            start_date, end_date = end_date, start_date
        if end_date.hour == 0 and end_date.minute == 0 and end_date.second == 0:
            end_date = end_date.replace(hour=23, minute=59, second=59)
        return start_date, end_date
    if start_date and not end_date:
        fim = start_date.replace(hour=23, minute=59, second=59)
        return start_date, fim
    if end_date and not start_date:
        ini = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
        return ini, end_date
    return inicio_padrao, fim_padrao


FLUXO_QUERY_KEYS = frozenset({
    "start_date",
    "end_date",
    "comprovante",
    "mdfe",
    "historico",
    "placa",
    "sync",
})

FLUXO_PANEL_QUERY_KEYS = frozenset({
    "filial",
    "tipo_negocio",
    "embarcador",
    "unidade_embarque",
})


def url_tem_filtros_painel(args) -> bool:
    """True se a URL ainda carrega filtros exclusivos do painel BI."""
    if any(k in args for k in FLUXO_PANEL_QUERY_KEYS):
        return True
    if args.get("placa") and args.get("historico") != "1":
        return True
    return False


def extrair_query_fluxo(args, *, ignorar_datas_painel: bool = False):
    """Remove filtros do painel principal (filial, placa BI, tipo negócio, etc.)."""
    from werkzeug.datastructures import ImmutableMultiDict

    pairs: list[tuple[str, str]] = []
    for key in FLUXO_QUERY_KEYS:
        if ignorar_datas_painel and key in ("start_date", "end_date"):
            continue
        if key == "placa" and args.get("historico") != "1":
            continue
        if key not in args:
            continue
        for val in args.getlist(key):
            if val is not None and str(val).strip() != "":
                pairs.append((key, str(val).strip()))
    return ImmutableMultiDict(pairs)


def obter_cod_proprietario_filtro(apartamento_id: int) -> int | None:
    """Código do proprietário no painel de licenças (vazio = sem filtro)."""
    try:
        from app.utils.proprietario_filtro import CHAVE_CONFIG, normalizar_cod_proprietario
    except ImportError:
        from utils.proprietario_filtro import CHAVE_CONFIG, normalizar_cod_proprietario
    try:
        cfg = ler_configuracoes_robo(apartamento_id)
        return normalizar_cod_proprietario(cfg.get(CHAVE_CONFIG))
    except Exception:
        return None


def _placas_cod_proprietario(
    apartamento_id: int,
    cod_prop: int | None = None,
) -> set[str]:
    """Placas do cadastro veiculo com codproprietario configurado no painel."""
    if cod_prop is None:
        cod_prop = obter_cod_proprietario_filtro(apartamento_id)
    if cod_prop is None:
        return set()
    return set(_mapa_veiculos_sati(apartamento_id, cod_prop).keys())


def _filtrar_df_placas_proprietario(
    df: pd.DataFrame,
    apartamento_id: int,
    cod_prop: int | None = None,
) -> pd.DataFrame:
    """
    Modo proprietário: mantém a lógica do BI por placa — somente veículos do cod_proprietario.
    Sem cod_proprietario no painel, retorna o DataFrame sem alteração.
    """
    if df is None or df.empty:
        return df if df is not None else pd.DataFrame()
    if cod_prop is None:
        cod_prop = obter_cod_proprietario_filtro(apartamento_id)
    if cod_prop is None:
        return df
    placas = _placas_cod_proprietario(apartamento_id, cod_prop)
    if not placas:
        return df.iloc[0:0].copy()
    col_map = _get_case_insensitive_column_map(df.columns)
    col_placa = col_map.get("placaveiculo")
    if not col_placa:
        return df.iloc[0:0].copy()
    return df[
        df[col_placa].astype(str).str.strip().str.upper().isin(placas)
    ].copy()


def _filtrar_df_cod_proprietario(
    df: pd.DataFrame,
    cod_prop: int,
    apartamento_id: int | None = None,
    incluir_placa_veiculo: bool = True,
) -> pd.DataFrame:
    if df is None or df.empty or cod_prop is None:
        return df
    col_map = _get_case_insensitive_column_map(df.columns)
    col_p = col_map.get("codproprietario") or col_map.get("codprop")
    mask = None
    if col_p:
        nums = pd.to_numeric(df[col_p], errors="coerce")
        mask = nums == cod_prop
    col_placa = col_map.get("placaveiculo")
    if incluir_placa_veiculo and apartamento_id is not None and col_placa:
        placas_prop = set(_mapa_veiculos_sati(apartamento_id, cod_prop).keys())
        if placas_prop:
            por_placa = (
                df[col_placa].astype(str).str.strip().str.upper().isin(placas_prop)
            )
            mask = por_placa if mask is None else (mask | por_placa)
    if mask is None:
        return df
    return df[mask].copy()


def _acertos_de_despesas(df_despesas: pd.DataFrame) -> set[int]:
    """Acertos de proprietário presentes nas despesas já filtradas por placa."""
    if df_despesas is None or df_despesas.empty:
        return set()
    col_map = _get_case_insensitive_column_map(df_despesas.columns)
    col_a = col_map.get("codacertoproprietario")
    if not col_a:
        return set()
    vals = pd.to_numeric(df_despesas[col_a], errors="coerce").dropna()
    return {int(v) for v in vals if int(v) > 0}


def _acertos_proprietario_de_despesas(df_despesas: pd.DataFrame, cod_prop: int) -> set[int]:
    if df_despesas is None or df_despesas.empty or cod_prop is None:
        return set()
    col_map = _get_case_insensitive_column_map(df_despesas.columns)
    col_p = col_map.get("codproprietario")
    col_a = col_map.get("codacertoproprietario")
    if not col_p:
        return set()
    mask = pd.to_numeric(df_despesas[col_p], errors="coerce") == cod_prop
    if not mask.any():
        return set()
    acertos: set[int] = set()
    if col_a:
        vals = pd.to_numeric(df_despesas.loc[mask, col_a], errors="coerce").dropna()
        acertos = {int(v) for v in vals}
    return acertos


def _filtrar_df_cod_acerto_proprietario(df: pd.DataFrame, acertos: set[int]) -> pd.DataFrame:
    if df is None or df.empty or not acertos:
        return df if df is not None else pd.DataFrame()
    col_map = _get_case_insensitive_column_map(df.columns)
    col_a = col_map.get("codacertoproprietario")
    if not col_a:
        return df
    nums = pd.to_numeric(df[col_a], errors="coerce")
    return df[nums.isin(acertos)].copy()


def _numeros_viagens_cod_proprietario(
    apartamento_id: int,
    start_date: datetime,
    end_date: datetime,
    cod_prop: int,
) -> set[int]:
    df = get_data_as_dataframe(
        "relFilViagensCliente", apartamento_id, start_date, end_date
    )
    df = _filtrar_df_placas_proprietario(df, apartamento_id, cod_prop)
    col_map = _get_case_insensitive_column_map(df.columns)
    col_num = col_map.get("numero")
    if not col_num or df.empty:
        return set()
    vals = pd.to_numeric(df[col_num], errors="coerce").dropna()
    return {int(v) for v in vals}


def _refiltrar_fat_acerto_por_viagens(pacote: dict) -> dict:
    df_viagens = pacote.get("df_viagens_cliente")
    if df_viagens is None or df_viagens.empty:
        pacote["df_fat_filtrado"] = pd.DataFrame()
        pacote["df_acerto_motorista_raw"] = pd.DataFrame()
        return pacote
    col_viag = _get_case_insensitive_column_map(df_viagens.columns)
    col_num_viag = col_viag.get("numero")
    if not col_num_viag:
        return pacote
    viagens_ids = df_viagens[col_num_viag].unique()

    df_fat_raw = pacote.get("df_fat_filtrado")
    if df_fat_raw is not None and not df_fat_raw.empty:
        col_fat = _get_case_insensitive_column_map(df_fat_raw.columns)
        col_num_fat = col_fat.get("numero")
        if col_num_fat:
            pacote["df_fat_filtrado"] = df_fat_raw[
                df_fat_raw[col_num_fat].isin(viagens_ids)
            ].copy()

    df_acerto = pacote.get("df_acerto_motorista_raw")
    if df_acerto is not None and not df_acerto.empty:
        col_acerto = _get_case_insensitive_column_map(df_acerto.columns)
        col_num_acerto = col_acerto.get("numero")
        if col_num_acerto:
            pacote["df_acerto_motorista_raw"] = df_acerto[
                df_acerto[col_num_acerto].isin(viagens_ids)
            ].copy()
    return pacote


def _aplicar_filtro_cod_proprietario_mestre(
    pacote: dict,
    apartamento_id: int,
    start_date: datetime,
    end_date: datetime,
    usar_snapshot: bool = False,
) -> dict:
    cod_prop = obter_cod_proprietario_filtro(apartamento_id)
    if cod_prop is None:
        return pacote

    df_desp_raw = pacote.get("df_despesas_raw")
    pacote["df_despesas_raw"] = _filtrar_df_placas_proprietario(
        df_desp_raw, apartamento_id, cod_prop
    )
    acertos = _acertos_de_despesas(pacote["df_despesas_raw"])

    pacote["df_despesas_filtrado"] = _filtrar_df_placas_proprietario(
        pacote.get("df_despesas_filtrado"), apartamento_id, cod_prop
    )

    if acertos:
        pacote["df_contas_pagar_raw"] = _filtrar_df_cod_acerto_proprietario(
            pacote.get("df_contas_pagar_raw"), acertos
        )
        pacote["df_contas_receber_raw"] = _filtrar_df_cod_acerto_proprietario(
            pacote.get("df_contas_receber_raw"), acertos
        )
    # Sem acerto nas despesas por placa: mantém contas do SQL (acertoproprietario).

    df_viagens = pacote.get("df_viagens_cliente")
    if usar_snapshot:
        numeros = _numeros_viagens_cod_proprietario(
            apartamento_id, start_date, end_date, cod_prop
        )
        if df_viagens is not None and not df_viagens.empty:
            col_viag = _get_case_insensitive_column_map(df_viagens.columns)
            col_num = col_viag.get("numero")
            if col_num and numeros:
                nums = pd.to_numeric(df_viagens[col_num], errors="coerce")
                pacote["df_viagens_cliente"] = df_viagens[nums.isin(numeros)].copy()
            elif col_num:
                pacote["df_viagens_cliente"] = df_viagens.iloc[0:0].copy()
        try:
            from app.data import bi_snapshot as bi_snap
        except ImportError:
            import bi_snapshot as bi_snap  # type: ignore
        pacote["df_fat_filtrado"] = bi_snap._fat_from_viagens(pacote["df_viagens_cliente"])
    else:
        pacote["df_viagens_cliente"] = _filtrar_df_placas_proprietario(
            df_viagens, apartamento_id, cod_prop
        )

    pacote = _refiltrar_fat_acerto_por_viagens(pacote)
    return pacote


def _filtrar_periodos_para_grafico(monthly_df: pd.DataFrame) -> pd.DataFrame:
    """Remove meses só com despesa futura / sem receita no intervalo útil."""
    if monthly_df.empty or "Periodo" not in monthly_df.columns:
        return monthly_df
    df = monthly_df.copy()
    cols_valor = [c for c in ("Faturamento", "Custo", "DespesasGerais", "DespesaTipoD", "TotalDespesas") if c in df.columns]
    if not cols_valor:
        return df
    df["_total"] = df[cols_valor].fillna(0).sum(axis=1)
    df = df[df["_total"] > 0].drop(columns=["_total"])
    if df.empty:
        return monthly_df
    if "Faturamento" in df.columns:
        com_fat = df["Faturamento"] > 0
        if com_fat.any():
            ultimo = df.loc[com_fat, "Periodo"].max()
            df = df[df["Periodo"] <= ultimo]
    return df.sort_values("Periodo").reset_index(drop=True)


def _agrupar_valores_por_periodo(df: pd.DataFrame, periodo_format: str, nome_serie: str) -> pd.Series:
    if df.empty or "valor_calculado" not in df.columns:
        return pd.Series(dtype=float, name=nome_serie)
    col_map = _get_case_insensitive_column_map(df.columns)
    datas = _serie_data_controle(df, col_map)
    mask = datas.notna()
    if not mask.any():
        return pd.Series(dtype=float, name=nome_serie)
    temp = df.loc[mask].copy()
    temp["_periodo"] = datas.loc[mask].dt.to_period(periodo_format)
    agrupado = temp.groupby("_periodo")["valor_calculado"].sum()
    agrupado.name = nome_serie
    return agrupado


def _fator_rateio_placas_proprias(placa_filter, apartamento_id: int) -> float:
    """Rateio tipo D: somente veículos com veiculo.incluirateio = S."""
    placas_selecionadas = placa_filter if isinstance(placa_filter, list) else [placa_filter]
    placas_selecionadas = [str(p).strip().upper() for p in placas_selecionadas if str(p).strip().upper() != "TODOS"]
    if not placas_selecionadas:
        return 1.0
    lista_rateio = _lista_placas_rateio(apartamento_id)
    if not lista_rateio:
        return 0.0
    placas_selec_rateio = [p for p in placas_selecionadas if p in lista_rateio]
    if not placas_selec_rateio:
        return 0.0
    return len(placas_selec_rateio) / len(lista_rateio)


def _dataframe_tipo_d_grupos_marcados(
    df: pd.DataFrame,
    df_flags: pd.DataFrame,
    col_map: dict,
) -> pd.DataFrame:
    """
    Tipo D (ved=D): soma somente se o grupo tiver incluir_em_tipo_d.
    is_despesa / is_custo_viagem do grupo não alteram itens diversos.
    """
    if df.empty or "ved" not in col_map:
        return pd.DataFrame()
    df_src = _filtrar_nota_contabiliza_despesa(df, col_map)
    df_src = _filtrar_ved_diversos(df_src, col_map)
    if df_src.empty:
        return pd.DataFrame()
    cm = _get_case_insensitive_column_map(df_src.columns)
    df_src = _valor_calculado_itemnota_df(df_src, cm)
    cm = _get_case_insensitive_column_map(df_src.columns)
    merged = _merge_flags_itemnota(df_src, df_flags, cm)
    return _excluir_itens_comercio_operacional(
        merged[merged["incluir_em_tipo_d"]].copy(), cm
    )


def _calcular_df_tipo_d(
    df_despesas_raw: pd.DataFrame,
    df_flags: pd.DataFrame,
    start_date,
    end_date,
    filial_filter,
    tipo_negocio_filter: str,
    unidade_embarque_filter: list | None = None,
) -> pd.DataFrame:
    """Despesas tipo D com flags incluir_em_tipo_d (mesma regra do KPI)."""
    if df_despesas_raw.empty:
        return pd.DataFrame()
    col_map = _get_case_insensitive_column_map(df_despesas_raw.columns)
    df_pre = df_despesas_raw.copy()
    if tipo_negocio_filter and tipo_negocio_filter != "Todos":
        df_pre = _filtrar_despesas_por_tipo_negocio(df_pre, col_map, tipo_negocio_filter)
    df_sem_placa = apply_filters_to_df(
        df_pre, start_date, end_date, "Todos", filial_filter, unidade_embarque_filter
    )
    col_map = _get_case_insensitive_column_map(df_sem_placa.columns)
    return _dataframe_tipo_d_grupos_marcados(df_sem_placa, df_flags, col_map)


def _total_tipo_d_com_rateio(
    df_tipo_d: pd.DataFrame,
    placa_filter,
    apartamento_id: int,
) -> float:
    if df_tipo_d.empty:
        return 0.0
    total = float(df_tipo_d["valor_calculado"].sum()) if "valor_calculado" in df_tipo_d.columns else 0.0
    return total * _fator_rateio_placas_proprias(placa_filter, apartamento_id)


def _col_tiponfe(col_map: dict) -> str | None:
    return col_map.get("tiponfe")


def _col_tipo_nota(col_map: dict) -> str | None:
    return col_map.get("tipo")


def _filtrar_nota_despesa_n(df: pd.DataFrame, col_map: dict) -> pd.DataFrame:
    """Somente notas com flag despesa = N (venda / entrada estoque — não entram como despesa operacional)."""
    if df.empty or "despesa" not in col_map:
        return df.iloc[0:0].copy()
    return df[df[col_map["despesa"]].astype(str).str.upper().str.strip() == "N"].copy()


def _filtrar_tipo_nota_zero(df: pd.DataFrame, col_map: dict) -> pd.DataFrame:
    """nota.tipo = 0 (nota venda no SATI)."""
    if df.empty:
        return df
    col = _col_tipo_nota(col_map)
    if not col:
        return df.iloc[0:0].copy()
    tipo = pd.to_numeric(df[col], errors="coerce")
    return df[tipo == 0].copy()


def _filtrar_nota_contabiliza_despesa(df: pd.DataFrame, col_map: dict) -> pd.DataFrame:
    """
    Notas que entram no custo operacional:
      - despesa=S + tiponfe=0 (compra despesa NF-e), ou
      - despesa=S + serie=RQ + tiponfe vazio (saída estoque como despesa).
    Entrada estoque (despesa=N, tiponfe=0, tipo vazio) fica excluída.
    """
    if df.empty or "despesa" not in col_map:
        return df.iloc[0:0].copy()
    desp = df[col_map["despesa"]].astype(str).str.upper().str.strip()
    mask = desp == "S"
    tiponfe_col = _col_tiponfe(col_map)
    if tiponfe_col:
        tiponfe = pd.to_numeric(df[tiponfe_col], errors="coerce")
        mask_nfe = tiponfe == 0
        mask_rq = pd.Series(False, index=df.index)
        serie_col = col_map.get("serie")
        if serie_col:
            mask_rq = df[serie_col].astype(str).str.upper().str.strip() == "RQ"
        mask = mask & (mask_nfe | (tiponfe.isna() & mask_rq))
    return df[mask].copy()


def _filtrar_itens_receita_comercio(df: pd.DataFrame, col_map: dict) -> pd.DataFrame:
    """Ramo COMERCIO + despesa=N + tiponfe=0 + tipo=0 (nota venda)."""
    df = _filtrar_ramo_comercio(df, col_map)
    df = _filtrar_nota_despesa_n(df, col_map)
    df = _filtrar_tiponfe_venda(df, col_map)
    df = _filtrar_tipo_nota_zero(df, col_map)
    return df


def _filtrar_itens_despesa_comercio(df: pd.DataFrame, col_map: dict) -> pd.DataFrame:
    """Ramo COMERCIO + despesa=S + tiponfe=0 ou série RQ (compra/saída estoque)."""
    df = _filtrar_ramo_comercio(df, col_map)
    df = _filtrar_nota_contabiliza_despesa(df, col_map)
    return df


def _filtrar_ramo_comercio(df: pd.DataFrame, col_map: dict) -> pd.DataFrame:
    """Itens cujo ramo de negócio (negocio.descricao) é COMERCIO."""
    if df.empty or "descnegocio" not in col_map:
        return df.iloc[0:0].copy()
    desc = df[col_map["descnegocio"]].astype(str).str.upper().str.strip()
    return df[desc == RAMO_NEGOCIO_COMERCIO].copy()


def _normalizar_texto_grupo(series: pd.Series) -> pd.Series:
    """Uppercase sem acento — comparação de descgrupod (ex.: VENDA, COMBUSTIVEL)."""
    return (
        series.astype(str)
        .str.upper()
        .str.normalize("NFKD")
        .str.encode("ascii", errors="ignore")
        .str.decode("ascii")
        .str.strip()
    )


def _mask_grupo_contem_venda(df: pd.DataFrame, col_map: dict) -> pd.Series:
    """Grupo do item (descgrupod) contém VENDA."""
    if df.empty or "descgrupod" not in col_map:
        return pd.Series(False, index=df.index)
    grp = _normalizar_texto_grupo(df[col_map["descgrupod"]])
    return grp.str.contains(GRUPO_VENDA_MARCADOR, na=False)


def _mask_ramo_comercio(df: pd.DataFrame, col_map: dict) -> pd.Series:
    if df.empty or "descnegocio" not in col_map:
        return pd.Series(False, index=df.index)
    desc = df[col_map["descnegocio"]].astype(str).str.upper().str.strip()
    return desc == RAMO_NEGOCIO_COMERCIO


def _mask_item_classificado_comercio(df: pd.DataFrame, col_map: dict) -> pd.Series:
    """Comércio (grupo VENDA ou ramo COMERCIO) — não entra em despesa/custo comum."""
    return _mask_grupo_contem_venda(df, col_map) | _mask_ramo_comercio(df, col_map)


def _filtrar_grupo_venda(df: pd.DataFrame, col_map: dict) -> pd.DataFrame:
    """Itens cujo grupo de despesa contém VENDA."""
    if df.empty:
        return df.iloc[0:0].copy()
    return df[_mask_grupo_contem_venda(df, col_map)].copy()


def _excluir_itens_comercio_operacional(df: pd.DataFrame, col_map: dict) -> pd.DataFrame:
    """Remove itens classificados como comércio dos totais de despesa e custo."""
    if df.empty:
        return df
    return df[~_mask_item_classificado_comercio(df, col_map)].copy()


def _mask_tiponfe_venda_comercio(df: pd.DataFrame, col_map: dict) -> pd.Series:
    """tiponfe=0 (NFe venda) ou série RQ com tiponfe vazio (saída estoque / venda SATI)."""
    if df.empty:
        return pd.Series(False, index=df.index)
    col = _col_tiponfe(col_map)
    if not col:
        return pd.Series(False, index=df.index)
    tiponfe = pd.to_numeric(df[col], errors="coerce")
    mask = tiponfe == 0
    serie_col = col_map.get("serie")
    if serie_col:
        rq = df[serie_col].astype(str).str.upper().str.strip() == "RQ"
        mask = mask | (rq & tiponfe.isna())
    return mask


def _filtrar_tiponfe_venda(df: pd.DataFrame, col_map: dict) -> pd.DataFrame:
    """nota.tiponfe = 0 ou saída RQ sem tiponfe (venda no SATI)."""
    if df.empty:
        return df
    return df[_mask_tiponfe_venda_comercio(df, col_map)].copy()


def _filtrar_tiponfe_nulo(df: pd.DataFrame, col_map: dict) -> pd.DataFrame:
    """nota.tiponfe IS NULL (entrada sem classificação de tipo NFe)."""
    if df.empty:
        return df
    col = _col_tiponfe(col_map)
    if not col:
        return df.copy()
    tiponfe = pd.to_numeric(df[col], errors="coerce")
    return df[tiponfe.isna()].copy()


def _total_itens_comercio(
    df_raw: pd.DataFrame,
    start_date,
    end_date,
    filial_filter,
    tiponfe_mode: str,
    unidade_embarque_filter: list | None = None,
) -> float:
    """
    Soma itens de nota do ramo COMERCIO.
    receita (venda): despesa=N + (tiponfe=0 ou série RQ) + tipo=0.
    despesa (null): despesa=S + (tiponfe=0 ou série RQ).
    """
    if df_raw.empty:
        return 0.0
    df = apply_filters_to_df(
        df_raw, start_date, end_date, "Todos", filial_filter, unidade_embarque_filter
    )
    col_map = _get_case_insensitive_column_map(df.columns)
    if tiponfe_mode == "venda":
        df = _filtrar_itens_receita_comercio(df, col_map)
    elif tiponfe_mode == "null":
        df = _filtrar_itens_despesa_comercio(df, col_map)
    else:
        return 0.0
    if df.empty:
        return 0.0
    df = _valor_calculado_itemnota_df(df, col_map)
    return float(df["valor_calculado"].sum()) if "valor_calculado" in df.columns else 0.0


def _filtrar_itens_investimento(df: pd.DataFrame, col_map: dict) -> pd.DataFrame:
    """Itens com flag investimento = S no cadastro (tabela item)."""
    if df.empty or "investimento" not in col_map:
        return df.iloc[0:0].copy()
    flag = df[col_map["investimento"]].astype(str).str.upper().str.strip()
    return df[flag == "S"].copy()


def _total_itens_investimento(
    df_raw: pd.DataFrame,
    start_date,
    end_date,
    filial_filter,
    unidade_embarque_filter: list | None = None,
) -> float:
    """
    Soma itens de nota despesa=S cujo cadastro (item) tem investimento marcado.
    Informativo: os mesmos valores continuam nos KPIs de custo/despesa operacional.
    """
    if df_raw.empty:
        return 0.0
    df = apply_filters_to_df(
        df_raw, start_date, end_date, "Todos", filial_filter, unidade_embarque_filter
    )
    col_map = _get_case_insensitive_column_map(df.columns)
    df = _filtrar_nota_contabiliza_despesa(df, col_map)
    df = _filtrar_itens_investimento(df, col_map)
    if df.empty:
        return 0.0
    df = _valor_calculado_itemnota_df(df, col_map)
    return float(df["valor_calculado"].sum()) if "valor_calculado" in df.columns else 0.0


def get_itens_investimento_df(
    df_raw: pd.DataFrame,
    start_date,
    end_date,
    filial_filter,
    unidade_embarque_filter: list | None = None,
) -> pd.DataFrame:
    """Itens de nota investimento para auditoria (mesma regra do KPI)."""
    if df_raw.empty:
        return pd.DataFrame()
    df = apply_filters_to_df(
        df_raw, start_date, end_date, "Todos", filial_filter, unidade_embarque_filter
    )
    col_map = _get_case_insensitive_column_map(df.columns)
    df = _filtrar_nota_contabiliza_despesa(df, col_map)
    df = _filtrar_itens_investimento(df, col_map)
    if df.empty:
        return pd.DataFrame()
    return _valor_calculado_itemnota_df(df, col_map)


def get_investimento_estoque_df(apartamento_id: int) -> pd.DataFrame:
    """Itens investimento=S com saldo > 0 (posição atual do estoque SATI)."""
    if not sati_enabled_for_apartment(engine, apartamento_id):
        return pd.DataFrame()
    schema = get_sati_schema(apartamento_id)
    sql = query_investimento_estoque(schema)
    try:
        with get_sati_engine().connect() as conn:
            df = pd.read_sql_query(text(sql), conn, params={"apartamento_id": apartamento_id})
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except Exception as exc:
        print(f"ERRO ao carregar investimento estoque SATI: {exc}")
        return pd.DataFrame()


def _total_investimento_estoque(apartamento_id: int) -> float:
    """Valor do estoque de itens investimento=S (saldo × custo). Não entra na despesa operacional."""
    df = get_investimento_estoque_df(apartamento_id)
    if df.empty or "valor_estoque" not in df.columns:
        return 0.0
    return float(pd.to_numeric(df["valor_estoque"], errors="coerce").fillna(0.0).sum())


def get_itens_comercio_df(
    df_raw: pd.DataFrame,
    start_date,
    end_date,
    filial_filter,
    tiponfe_mode: str,
    unidade_embarque_filter: list | None = None,
) -> pd.DataFrame:
    """Itens de nota do ramo COMERCIO para auditoria (mesma regra dos KPIs)."""
    if df_raw.empty:
        return pd.DataFrame()
    df = apply_filters_to_df(
        df_raw, start_date, end_date, "Todos", filial_filter, unidade_embarque_filter
    )
    col_map = _get_case_insensitive_column_map(df.columns)
    if tiponfe_mode == "venda":
        df = _filtrar_itens_receita_comercio(df, col_map)
    elif tiponfe_mode == "null":
        df = _filtrar_itens_despesa_comercio(df, col_map)
    else:
        return pd.DataFrame()
    if df.empty:
        return pd.DataFrame()
    return _valor_calculado_itemnota_df(df, col_map)


def get_comercio_mensal(
    df_raw: pd.DataFrame,
    start_date,
    end_date,
    filial_filter,
) -> pd.DataFrame:
    """Receita e despesa do ramo COMERCIO por mês (regras SATI de tipo de nota)."""
    cols = ["periodo", "receita", "despesa"]
    if df_raw.empty:
        return pd.DataFrame(columns=cols)
    df = apply_filters_to_df(df_raw, start_date, end_date, "Todos", filial_filter)
    col_map = _get_case_insensitive_column_map(df.columns)
    col_dt = col_map.get("datacontrole") or col_map.get("dataemissao")
    if not col_dt:
        return pd.DataFrame(columns=cols)
    df = _valor_calculado_itemnota_df(df, col_map)
    df = df.copy()
    df["_dt"] = pd.to_datetime(df[col_dt], errors="coerce")
    df = df.dropna(subset=["_dt"])
    if df.empty:
        return pd.DataFrame(columns=cols)
    df_rec = _filtrar_itens_receita_comercio(df, col_map)
    df_desp = _filtrar_itens_despesa_comercio(df, col_map)
    df_rec["mes"] = df_rec["_dt"].dt.to_period("M")
    df_desp["mes"] = df_desp["_dt"].dt.to_period("M")
    rec = df_rec.groupby("mes")["valor_calculado"].sum()
    des = df_desp.groupby("mes")["valor_calculado"].sum()
    meses = sorted(set(rec.index) | set(des.index))
    if not meses:
        return pd.DataFrame(columns=cols)
    pivot = pd.DataFrame(
        {
            "mes": meses,
            "receita": [float(rec.get(m, 0.0)) for m in meses],
            "despesa": [float(des.get(m, 0.0)) for m in meses],
        }
    )
    pivot["periodo"] = pivot["mes"].astype(str)
    return pivot[["periodo", "receita", "despesa"]].sort_values("periodo")


def _filtrar_despesas_por_tipo_negocio(df: pd.DataFrame, col_map: dict, tipo_negocio_filter: str) -> pd.DataFrame:
    """Despesas: ramo do cadastro do item (negocio.descricao via item/itemnota)."""
    if df.empty or not tipo_negocio_filter or tipo_negocio_filter == "Todos":
        return df
    if "descnegocio" not in col_map:
        return df
    tipo = tipo_negocio_filter.upper().strip()
    desc = df[col_map["descnegocio"]].astype(str).str.upper().str.strip()
    if tipo == TIPO_NEGOCIO_FROTA:
        return df[desc == TIPO_NEGOCIO_FROTA].copy()
    if tipo == TIPO_NEGOCIO_FRETE.upper() or "FRETE" in tipo or "AGENCIAMENTO" in tipo:
        return df[desc.str.contains("FRETE", na=False) | desc.str.contains("AGENCIAMENTO", na=False)].copy()
    return df[desc == tipo].copy()


def get_unique_negocios(apartamento_id: int) -> list[str]:
    """Tipos de negócio para o filtro do dashboard (FROTA e FRETE/AGENCIAMENTO)."""
    if sati_enabled_for_apartment(engine, apartamento_id):
        return list(TIPOS_NEGOCIO_PADRAO)
    df_despesas = get_data_as_dataframe("relFilDespesasGerais", apartamento_id)
    if df_despesas.empty:
        return list(TIPOS_NEGOCIO_PADRAO)
    col_map = _get_case_insensitive_column_map(df_despesas.columns)
    if "descnegocio" not in col_map:
        return list(TIPOS_NEGOCIO_PADRAO)
    valores = (
        df_despesas[col_map["descnegocio"]]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
        .tolist()
    )
    prioritarios = [t for t in TIPOS_NEGOCIO_PADRAO if t in valores]
    outros = sorted(v for v in valores if v and v not in prioritarios)
    return prioritarios + outros

def apply_filters_to_df(
    df: pd.DataFrame,
    start_date: datetime,
    end_date: datetime,
    placa_filter: str,
    filial_filter: list,
    unidade_embarque_filter: list | None = None,
) -> pd.DataFrame:
    """
    Aplica filtros de data, placa e uma LISTA de filiais a um DataFrame de forma case-insensitive e inteligente.
    """
    if df.empty:
        return df
    
    df_filtrado = df.copy()
    col_map = _get_case_insensitive_column_map(df_filtrado.columns)
    
    # Filtragem por Data
    possible_date_cols = ['datacontrole', 'dataviagemmotorista', 'datavenc']
    date_column_for_filter_lower = next((col for col in possible_date_cols if col in col_map), None)
    if date_column_for_filter_lower:
        original_date_col_name = col_map[date_column_for_filter_lower]
        df_filtrado[original_date_col_name] = pd.to_datetime(df_filtrado[original_date_col_name], errors='coerce', dayfirst=True)
        if start_date or end_date:
            df_filtrado.dropna(subset=[original_date_col_name], inplace=True)
        if not df_filtrado.empty:
            if start_date:
                df_filtrado = df_filtrado[df_filtrado[original_date_col_name].dt.date >= start_date.date()]
            if end_date:
                df_filtrado = df_filtrado[df_filtrado[original_date_col_name].dt.date <= end_date.date()]

    # Filtragem por Placa (CORRIGIDA CIRURGICAMENTE PARA LISTA MULTISELECT)
    if placa_filter and placa_filter != "Todos":
        placa_cols_lower = [c.lower() for c in config.FILTER_COLUMN_MAPS.get("placa", [])]
        placa_col_found_lower = next((col for col in placa_cols_lower if col in col_map), None)
        if placa_col_found_lower:
            original_placa_col = col_map[placa_col_found_lower]
            # --- INÍCIO DA CORREÇÃO ---
            if isinstance(placa_filter, list):
                placas_limpas = [str(p).strip().upper() for p in placa_filter if p != 'Todos']
                if placas_limpas:
                    df_filtrado = df_filtrado[df_filtrado[original_placa_col].astype(str).str.strip().str.upper().isin(placas_limpas)]
            else:
                placa_filter_limpa = str(placa_filter).strip().upper()
                df_filtrado = df_filtrado[df_filtrado[original_placa_col].astype(str).str.strip().str.upper() == placa_filter_limpa]
            # --- FIM DA CORREÇÃO ---

    # Filtragem por Filial (Apenas ignora se vier a palavra "Todos")
    df_filtrado = _aplicar_filtro_lista_colunas(df_filtrado, col_map, filial_filter, "filial")

    # Filtragem por Unidade de Embarque
    df_filtrado = _aplicar_filtro_lista_colunas(
        df_filtrado, col_map, unidade_embarque_filter or [], "unidade_embarque"
    )

    return df_filtrado

def _fix_invalid_dates(df: pd.DataFrame, table_name: str) -> pd.DataFrame:
    """
    Encontra colunas de data, converte-as e preenche valores inválidos (NaT)
    com o último valor válido (forward fill) de forma robusta.
    """
    if df.empty:
        return df

    date_cols_map = config.TABLE_COLUMN_MAPS.get(table_name, {}).get('date_formats', {})
    if not date_cols_map:
        return df

    col_map = _get_case_insensitive_column_map(df.columns)
    date_cols_in_df = [col_map[key] for key in date_cols_map.keys() if key in col_map]
    if not date_cols_in_df:
        return df

    # Converte todas as colunas de data de uma vez e descarta anos inválidos
    for col in date_cols_in_df:
        df[col] = pd.to_datetime(df[col], errors="coerce")
        if hasattr(df[col].dt, "year"):
            invalid = (df[col].dt.year < 1900) | (df[col].dt.year > 2100)
            df.loc[invalid, col] = pd.NaT

    # Identifica uma coluna primária para ordenação cronológica (geralmente 'datacontrole')
    primary_sort_col = next((col_map[key] for key in ['datacontrole', 'dataviagemmotorista'] if key in col_map), None)
    
    if primary_sort_col:
        # Ordena o DataFrame UMA VEZ pela data primária
        df = df.sort_values(by=primary_sort_col).reset_index(drop=True)
    
    # Aplica o forward fill em todas as colunas de data
    for col in date_cols_in_df:
        df[col] = df[col].ffill()
            
    return df
def _prepare_final_cost_and_expense_dfs(df_viagens_cliente, df_despesas_filtrado, df_flags, flags_dict):
    """
    Função auxiliar que centraliza a lógica de composição dos DataFrames
    finais de Custo e Despesa, aplicando todas as regras de negócio.
    VERSÃO CORRIGIDA: Garante que os DataFrames de retorno tenham sempre as colunas corretas.
    """
    col_map_viagens_cli = _get_case_insensitive_column_map(df_viagens_cliente.columns)
    col_map_despesas = _get_case_insensitive_column_map(df_despesas_filtrado.columns)
    
    # --- INÍCIO DA CORREÇÃO ---
    # Define as colunas esperadas para garantir a consistência
    colunas_esperadas = df_despesas_filtrado.columns.tolist() + ['valor_calculado', 'group_name', 'is_despesa', 'is_custo_viagem', 'incluir_em_tipo_d']
    
    if df_despesas_filtrado.empty:
        df_custos = pd.DataFrame(columns=colunas_esperadas)
        df_despesas_gerais = pd.DataFrame(columns=colunas_esperadas)
    else:
        if 'valor_calculado' not in df_despesas_filtrado.columns:
             if all(c in col_map_despesas for c in ['serie', 'liquido', 'vlcontabil']):
                df_despesas_filtrado.loc[:, 'valor_calculado'] = np.where(df_despesas_filtrado[col_map_despesas['serie']] == 'RQ', df_despesas_filtrado[col_map_despesas['liquido']], df_despesas_filtrado[col_map_despesas['vlcontabil']])
             elif 'vlcontabil' in col_map_despesas:
                df_despesas_filtrado.loc[:, 'valor_calculado'] = df_despesas_filtrado[col_map_despesas['vlcontabil']]
             else:
                df_despesas_filtrado.loc[:, 'valor_calculado'] = 0
            
        df_com_flags = pd.merge(df_despesas_filtrado, df_flags, left_on=col_map_despesas.get('descgrupod'), right_on='group_name', how='left')
        df_com_flags['is_custo_viagem'] = df_com_flags['is_custo_viagem'].fillna('N')
        df_com_flags['is_despesa'] = df_com_flags['is_despesa'].fillna('S')
        df_custos = df_com_flags[df_com_flags['is_custo_viagem'] == 'S'].copy()
        df_despesas_gerais = df_com_flags[df_com_flags['is_despesa'] == 'S'].copy()
    # --- FIM DA CORREÇÃO ---
        
    filial_col_found = next((col for col in ['nomeFil', 'nomeFilial'] if col.lower() in col_map_viagens_cli), None)
    df_viagens_cliente_copy = df_viagens_cliente.copy()
    if not filial_col_found:
        df_viagens_cliente_copy['nomefil_placeholder'] = 'Filial Desconhecida'
        filial_col_to_use = 'nomefil_placeholder'
    else:
        filial_col_to_use = filial_col_found

    if not df_viagens_cliente_copy.empty and all(c in col_map_viagens_cli for c in ['tipofrete', 'fretemotorista', 'comissao', 'dataviagemmotorista']):
        # LEGADO — não usado no KPI atual (custo prévia vem de _dataframe_custo_previa_dre / DRE).
        # Comissão e quebra do conhecimento NÃO são somadas aqui para evitar duplicidade e regra antiga
        # (fretemotorista × % sem descontar quebra).
        pass

    if not df_viagens_cliente_copy.empty and 'valorquebra' in col_map_viagens_cli:
        pass

    return df_custos, df_despesas_gerais


def _valor_calculado_itemnota_df(df: pd.DataFrame, col_map: dict) -> pd.DataFrame:
    df = df.copy()
    if df.empty:
        df["valor_calculado"] = pd.Series(dtype=float)
        return df
    if all(c in col_map for c in ["serie", "liquido", "vlcontabil"]):
        df["valor_calculado"] = np.where(
            df[col_map["serie"]].astype(str).str.upper() == "RQ",
            pd.to_numeric(df[col_map["liquido"]], errors="coerce"),
            pd.to_numeric(df[col_map["vlcontabil"]], errors="coerce"),
        )
    elif "vlcontabil" in col_map:
        df["valor_calculado"] = pd.to_numeric(df[col_map["vlcontabil"]], errors="coerce")
    else:
        df["valor_calculado"] = 0.0
    df["valor_calculado"] = df["valor_calculado"].fillna(0.0)
    return df


def _filtrar_nota_despesa_s(df: pd.DataFrame, col_map: dict) -> pd.DataFrame:
    """Somente lançamentos da nota com flag despesa = S (atalho; preferir _filtrar_nota_contabiliza_despesa)."""
    if df.empty or "despesa" not in col_map:
        return df.copy() if not df.empty else df
    return df[df[col_map["despesa"]].astype(str).str.upper().str.strip() == "S"].copy()


# itemnota.ved — campo SATI que define o fluxo no BI (sempre consultado primeiro):
#   D → diversos (Despesa Tipo D, se o grupo tiver incluir_em_tipo_d)
#   V → despesa geral ou custo de viagem (grupo + placa); despesa=S + tiponfe=0 (ou RQ)
#   E → movimentação de estoque; não entra no custo operacional deste pipeline
VED_DIVERSOS = "D"
VED_ESTOQUE = "E"
VED_VEICULO = "V"
VED_CUSTO_DESPESA = frozenset({VED_VEICULO})


def _col_ved(col_map: dict) -> str | None:
    return col_map.get("ved")


def _mask_ved_veiculo_ou_estoque(df: pd.DataFrame, col_map: dict) -> pd.Series:
    ved_col = _col_ved(col_map)
    if not ved_col or df.empty:
        return pd.Series(False, index=df.index)
    return _normalizar_ved_series(df[ved_col]).isin(VED_CUSTO_DESPESA)


def _mask_ved_diversos(df: pd.DataFrame, col_map: dict) -> pd.Series:
    ved_col = _col_ved(col_map)
    if not ved_col or df.empty:
        return pd.Series(False, index=df.index)
    return _normalizar_ved_series(df[ved_col]) == VED_DIVERSOS


def _normalizar_ved_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.upper().str.strip()


def _filtrar_ved_diversos(df: pd.DataFrame, col_map: dict) -> pd.DataFrame:
    if df.empty or "ved" not in col_map:
        return df.iloc[0:0].copy()
    return df[_normalizar_ved_series(df[col_map["ved"]]) == VED_DIVERSOS].copy()


def _filtrar_ved_veiculo_ou_estoque(df: pd.DataFrame, col_map: dict) -> pd.DataFrame:
    """Itens ved=V entram em custo ou despesa geral conforme o grupo (ved=E fica de fora)."""
    if df.empty or "ved" not in col_map:
        return df.iloc[0:0].copy()
    return df[_normalizar_ved_series(df[col_map["ved"]]).isin(VED_CUSTO_DESPESA)].copy()


def _excluir_ved_tipo_d(df: pd.DataFrame, col_map: dict) -> pd.DataFrame:
    """Remove diversos (D) — vão só para Despesa Tipo D quando o grupo estiver marcado."""
    if df.empty or "ved" not in col_map:
        return df
    return df[_normalizar_ved_series(df[col_map["ved"]]) != VED_DIVERSOS].copy()


def _merge_flags_itemnota(df: pd.DataFrame, df_flags: pd.DataFrame, col_map: dict) -> pd.DataFrame:
    if df.empty:
        return df
    grp_col = col_map.get("descgrupod")
    if not grp_col:
        out = df.copy()
        out["is_custo_viagem"] = "N"
        out["is_despesa"] = "N"
        out["incluir_em_tipo_d"] = False
        return out
    merged = pd.merge(df, df_flags, left_on=grp_col, right_on="group_name", how="left")
    merged["is_custo_viagem"] = merged["is_custo_viagem"].fillna("N")
    merged["is_despesa"] = merged["is_despesa"].fillna("N")
    merged["incluir_em_tipo_d"] = merged["incluir_em_tipo_d"].fillna(False).astype(bool)
    return merged


def _aplicar_classificacao_grupo_para_ved_ve(
    df: pd.DataFrame,
    col_map: dict,
) -> pd.DataFrame:
    """
    Grupo altera KPI só para itens ved=V.
    Padrão: despesa geral. Custo de viagem apenas se is_custo_viagem=S no grupo.
    """
    if df.empty or not _col_ved(col_map):
        return df
    df = df.copy()
    mask_ve = _mask_ved_veiculo_ou_estoque(df, col_map)
    custo = mask_ve & (df["is_custo_viagem"].astype(str).str.upper() == "S")
    df.loc[mask_ve, "is_despesa"] = "N"
    df.loc[custo, "is_despesa"] = "N"
    df.loc[mask_ve & ~custo, "is_despesa"] = "S"
    return df


def _dataframe_custo_despesa_ved_ve(
    df: pd.DataFrame,
    df_flags: pd.DataFrame,
    col_map: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Itens ved=V: roteados para custo ou despesa conforme classificação do grupo."""
    if df.empty or not _col_ved(col_map):
        return pd.DataFrame(), pd.DataFrame()
    df_src = _filtrar_nota_contabiliza_despesa(df, col_map)
    df_src = _filtrar_ved_veiculo_ou_estoque(df_src, col_map)
    if df_src.empty:
        return pd.DataFrame(), pd.DataFrame()
    cm = _get_case_insensitive_column_map(df_src.columns)
    df_src = _valor_calculado_itemnota_df(df_src, cm)
    cm = _get_case_insensitive_column_map(df_src.columns)
    merged = _merge_flags_itemnota(df_src, df_flags, cm)
    merged = _aplicar_classificacao_grupo_para_ved_ve(merged, cm)
    grp_col = cm.get("descgrupod")
    if grp_col:
        grupos_dre = {g.upper() for g in dre.GRUPOS_DRE_CONHECIMENTO}
        sem_duplicar_dre = ~merged[grp_col].astype(str).str.upper().isin(grupos_dre)
    else:
        sem_duplicar_dre = pd.Series(True, index=merged.index)
    custos = merged[(merged["is_custo_viagem"].astype(str).str.upper() == "S") & sem_duplicar_dre].copy()
    despesas = merged[merged["is_despesa"].astype(str).str.upper() == "S"].copy()
    custos = _excluir_itens_comercio_operacional(custos, cm)
    despesas = _excluir_itens_comercio_operacional(despesas, cm)
    return custos, despesas


def _dataframe_custo_previa_dre(
    df_viagens: pd.DataFrame, df_acerto: pd.DataFrame | None
) -> pd.DataFrame:
    """
    Custo prévia do conhecimento (DRE): frete motorista líquido + ICMS + seguro.
    Líquido motorista via dre.calcular_frete_motorista_liquido (regra universal).
    """
    if df_viagens.empty:
        return pd.DataFrame()
    cv = _get_case_insensitive_column_map(df_viagens.columns)
    if "custo_previa_conhecimento" in cv:
        df_dre = df_viagens
    else:
        df_dre = dre.aplicar_dre_em_dataframe(
            df_viagens, df_acerto if df_acerto is not None else pd.DataFrame()
        )
    col_dt = cv.get("dataviagemmotorista") or cv.get("dataemissao")
    col_fil = cv.get("nomefil") or cv.get("nomefilial")
    out = pd.DataFrame()
    out["valor_calculado"] = pd.to_numeric(
        df_dre["custo_previa_conhecimento"], errors="coerce"
    ).fillna(0.0)
    out["datacontrole"] = df_dre[col_dt] if col_dt and col_dt in df_dre.columns else pd.NaT
    out["descgrupod"] = "CUSTO PRÉVIA CONHECIMENTO"
    if col_fil and col_fil in df_dre.columns:
        out["nomefil"] = df_dre[col_fil]
    return out[out["valor_calculado"] > 0].copy()


def _get_final_expense_dataframes(df_viagens_cliente, df_despesas_filtrado, df_flags, df_acerto_motorista):
    """
    Roteamento por itemnota.ved (campo SATI):
      D → diversos / Despesa Tipo D (grupo.incluir_em_tipo_d)
      V → despesa geral (padrão) ou custo de viagem (se o grupo mudar); ved=E não entra aqui
    """
    col_map_raw = (
        _get_case_insensitive_column_map(df_despesas_filtrado.columns)
        if not df_despesas_filtrado.empty
        else {}
    )

    df_tipo_d = _normalizar_coluna_filial(
        _dataframe_tipo_d_grupos_marcados(df_despesas_filtrado, df_flags, col_map_raw)
    )
    df_custos_nota, df_despesas_nota = _dataframe_custo_despesa_ved_ve(
        df_despesas_filtrado, df_flags, col_map_raw
    )
    df_custos_nota = _normalizar_coluna_filial(df_custos_nota)
    df_despesas_nota = _normalizar_coluna_filial(df_despesas_nota)

    df_custo_previa = _normalizar_coluna_filial(
        _dataframe_custo_previa_dre(df_viagens_cliente, df_acerto_motorista)
    )

    partes_custo = [df for df in (df_custo_previa, df_custos_nota) if not df.empty]
    df_custos_final = pd.concat(partes_custo, ignore_index=True) if partes_custo else pd.DataFrame()

    return {
        "custos": df_custos_final,
        "despesas": df_despesas_nota,
        "tipo_d": df_tipo_d,
        "custo_previa": df_custo_previa,
        "custo_nota": df_custos_nota,
    }

def _obter_dados_filtrados_mestre(
    apartamento_id: int,
    start_date: datetime,
    end_date: datetime,
    placa_filter: str,
    filial_filter: list,
    tipo_negocio_filter: str,
    unidade_embarque_filter: list | None = None,
    embarcador_filter: str = "Todos",
):
    """
    Função mestre que carrega todos os dados brutos necessários e aplica filtros.
    Viagens: usa snapshot BI (DRE pré-calculado) quando disponível — filtros iguais ao SATI.
    """
    from app.data import bi_snapshot as bi_snap

    df_flags = get_all_group_flags(apartamento_id)
    usar_snapshot = bi_snap.snapshot_is_ready(apartamento_id) and not bi_snap.snapshot_is_building(
        apartamento_id
    )

    if usar_snapshot:
        df_snapshot_all = bi_snap.load_viagens_dre_dataframe(apartamento_id)
        df_viagens_cliente = bi_snap.filtrar_viagens_snapshot(
            df_snapshot_all,
            start_date,
            end_date,
            placa_filter,
            filial_filter,
            tipo_negocio_filter,
            unidade_embarque_filter,
            embarcador_filter,
        )
        df_fat_filtrado = bi_snap._fat_from_viagens(df_viagens_cliente)

        col_map_desp_raw = {}
        df_despesas_raw = get_data_as_dataframe(
            "relFilDespesasGerais", apartamento_id, start_date, end_date
        )
        col_map_desp_raw = _get_case_insensitive_column_map(df_despesas_raw.columns)
        df_despesas_pre_filtrado = df_despesas_raw
        if tipo_negocio_filter and tipo_negocio_filter != "Todos":
            df_despesas_pre_filtrado = _filtrar_despesas_por_tipo_negocio(
                df_despesas_raw, col_map_desp_raw, tipo_negocio_filter
            )
        df_despesas_filtrado = apply_filters_to_df(
            df_despesas_pre_filtrado,
            start_date,
            end_date,
            placa_filter,
            filial_filter,
            unidade_embarque_filter,
        )

        df_contas_pagar_raw = get_data_as_dataframe("relFilContasPagarDet", apartamento_id)
        df_contas_receber_raw = get_data_as_dataframe("relFilContasReceber", apartamento_id)
        df_acerto_motorista_raw = get_data_as_dataframe(
            "relFilAcertoMot", apartamento_id, start_date, end_date
        )

        col_viag = _get_case_insensitive_column_map(df_viagens_cliente.columns)
        col_num_viag = col_viag.get("numero")
        if col_num_viag and not df_viagens_cliente.empty:
            viagens_filtradas_ids = df_viagens_cliente[col_num_viag].unique()
        else:
            viagens_filtradas_ids = []

        col_acerto = _get_case_insensitive_column_map(df_acerto_motorista_raw.columns)
        col_num_acerto = col_acerto.get("numero")
        if col_num_acerto and not df_acerto_motorista_raw.empty and len(viagens_filtradas_ids) > 0:
            df_acerto_motorista_filtrado = df_acerto_motorista_raw[
                df_acerto_motorista_raw[col_num_acerto].isin(viagens_filtradas_ids)
            ]
        else:
            df_acerto_motorista_filtrado = pd.DataFrame()

        pacote = {
            "df_viagens_cliente": df_viagens_cliente,
            "df_despesas_filtrado": df_despesas_filtrado,
            "df_fat_filtrado": df_fat_filtrado,
            "df_contas_pagar_raw": df_contas_pagar_raw,
            "df_contas_receber_raw": df_contas_receber_raw,
            "df_flags": df_flags,
            "df_despesas_raw": df_despesas_raw,
            "df_acerto_motorista_raw": df_acerto_motorista_filtrado,
        }
        return _finalizar_pacote_mestre(
            pacote, apartamento_id, start_date, end_date, usar_snapshot=True
        )

    # 1. Carrega DataFrames brutos (período no SQL quando SATI ativo)
    df_viagens_raw = get_data_as_dataframe(
        "relFilViagensCliente", apartamento_id, start_date, end_date
    )
    df_fat_raw = get_data_as_dataframe(
        "relFilViagensFatCliente", apartamento_id, start_date, end_date
    )
    df_despesas_raw = get_data_as_dataframe(
        "relFilDespesasGerais", apartamento_id, start_date, end_date
    )
    df_contas_pagar_raw = get_data_as_dataframe("relFilContasPagarDet", apartamento_id)
    df_contas_receber_raw = get_data_as_dataframe("relFilContasReceber", apartamento_id)
    df_acerto_motorista_raw = get_data_as_dataframe(
        "relFilAcertoMot", apartamento_id, start_date, end_date
    )
    df_flags = get_all_group_flags(apartamento_id)

    # 2. Pré-filtra por Tipo de Negócio (se aplicável)
    df_despesas_pre_filtrado = df_despesas_raw
    df_viagens_pre_filtrado = df_viagens_raw
    
    col_map_desp_raw = _get_case_insensitive_column_map(df_despesas_raw.columns)
    col_map_viag_raw = _get_case_insensitive_column_map(df_viagens_raw.columns)

    if tipo_negocio_filter and tipo_negocio_filter != "Todos":
        df_despesas_pre_filtrado = _filtrar_despesas_por_tipo_negocio(
            df_despesas_raw, col_map_desp_raw, tipo_negocio_filter
        )
        df_viagens_pre_filtrado = _filtrar_viagens_por_tipo_negocio(
            df_viagens_raw, col_map_viag_raw, tipo_negocio_filter
        )

    # 3. Aplica os filtros principais (data, placa, filial, unidade) sobre os dados pré-filtrados
    df_viagens_cliente = apply_filters_to_df(
        df_viagens_pre_filtrado,
        start_date,
        end_date,
        placa_filter,
        filial_filter,
        unidade_embarque_filter,
    )
    df_viagens_cliente = _aplicar_filtro_embarcador(df_viagens_cliente, embarcador_filter)
    df_despesas_filtrado = apply_filters_to_df(
        df_despesas_pre_filtrado,
        start_date,
        end_date,
        placa_filter,
        filial_filter,
        unidade_embarque_filter,
    )

    # 4. Filtra o faturamento e o acerto do motorista com base nas viagens já filtradas
    col_viag = _get_case_insensitive_column_map(df_viagens_cliente.columns)
    col_num_viag = col_viag.get("numero")
    if col_num_viag and not df_viagens_cliente.empty:
        viagens_filtradas_ids = df_viagens_cliente[col_num_viag].unique()
    else:
        viagens_filtradas_ids = []

    col_map_fat_temp = _get_case_insensitive_column_map(df_fat_raw.columns)
    col_num_fat = col_map_fat_temp.get("numero")
    if (
        col_num_fat
        and not df_fat_raw.empty
        and len(viagens_filtradas_ids) > 0
    ):
        if "permitefaturar" in col_map_fat_temp:
            df_fat_raw = df_fat_raw[df_fat_raw[col_map_fat_temp["permitefaturar"]] == "S"]
        df_fat_filtrado = df_fat_raw[df_fat_raw[col_num_fat].isin(viagens_filtradas_ids)]
    else:
        df_fat_filtrado = pd.DataFrame()

    col_acerto = _get_case_insensitive_column_map(df_acerto_motorista_raw.columns)
    col_num_acerto = col_acerto.get("numero")
    if col_num_acerto and not df_acerto_motorista_raw.empty and len(viagens_filtradas_ids) > 0:
        df_acerto_motorista_filtrado = df_acerto_motorista_raw[
            df_acerto_motorista_raw[col_num_acerto].isin(viagens_filtradas_ids)
        ]
    else:
        df_acerto_motorista_filtrado = pd.DataFrame()

    # 5. Retorna o dicionário completo com todos os DataFrames necessários
    pacote = {
        "df_viagens_cliente": df_viagens_cliente,
        "df_despesas_filtrado": df_despesas_filtrado,
        "df_fat_filtrado": df_fat_filtrado,
        "df_contas_pagar_raw": df_contas_pagar_raw,
        "df_contas_receber_raw": df_contas_receber_raw,
        "df_flags": df_flags,
        "df_despesas_raw": df_despesas_raw,
        "df_acerto_motorista_raw": df_acerto_motorista_filtrado,
    }
    return _finalizar_pacote_mestre(
        pacote, apartamento_id, start_date, end_date, usar_snapshot=False
    )


def _finalizar_pacote_mestre(
    pacote: dict,
    apartamento_id: int,
    start_date: datetime,
    end_date: datetime,
    usar_snapshot: bool,
) -> dict:
    pacote = _aplicar_filtro_cod_proprietario_mestre(
        pacote, apartamento_id, start_date, end_date, usar_snapshot=usar_snapshot
    )
    pacote["df_viagens_cliente"] = _anexar_colunas_dre_viagens(
        pacote.get("df_viagens_cliente"),
        pacote.get("df_acerto_motorista_raw"),
        apartamento_id,
    )
    return pacote


def _anexar_colunas_dre_viagens(
    df_viagens: pd.DataFrame,
    df_acerto: pd.DataFrame | None,
    apartamento_id: int,
) -> pd.DataFrame:
    """Colunas receita / custo prévia (regras por tenant, ex. jeremias)."""
    if df_viagens is None or df_viagens.empty:
        return df_viagens if df_viagens is not None else pd.DataFrame()
    cv = _get_case_insensitive_column_map(df_viagens.columns)
    num_col = cv.get("numero")
    if not num_col:
        return df_viagens
    df_base = _viagens_base_dre(df_viagens)
    if df_base.empty:
        return df_viagens
    df_dre = dre.aplicar_dre_em_dataframe(
        df_base,
        df_acerto if df_acerto is not None else pd.DataFrame(),
        dre_opts=obter_dre_opts(apartamento_id),
    )
    cm_dre = {str(c).lower(): c for c in df_dre.columns}
    dre_num = cm_dre.get("numero", num_col)
    extras = [
        cm_dre[k]
        for k in (
            "receita",
            "custo_previa_conhecimento",
            "custo_icms",
            "custo_motorista",
            "frete_empresa",
            "fretemotorista_bruto",
        )
        if k in cm_dre
    ]
    dre_slim = df_dre[[dre_num] + extras].drop_duplicates(subset=[dre_num])
    drop_dre = [
        cv[k]
        for k in (
            "receita",
            "custo_previa_conhecimento",
            "custo_icms",
            "custo_motorista",
            "frete_empresa",
            "fretemotorista_bruto",
            "tipo_frete",
        )
        if k in cv
    ]
    base = df_viagens.drop(columns=drop_dre, errors="ignore")
    out = base.merge(dre_slim, left_on=num_col, right_on=dre_num, how="left")
    if dre_num != num_col and dre_num in out.columns:
        out = out.drop(columns=[dre_num], errors="ignore")
    return out


def _df_viagens_com_receita(
    df_viagens: pd.DataFrame,
    apartamento_id: int,
    df_acerto: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Viagens com receita DRE > 0 (campo configurável por tenant)."""
    df_work = _anexar_colunas_dre_viagens(df_viagens, df_acerto, apartamento_id)
    cv = _get_case_insensitive_column_map(df_work.columns)
    col_rec = cv.get("receita")
    if not col_rec:
        return pd.DataFrame()
    rec = pd.to_numeric(df_work[col_rec], errors="coerce").fillna(0)
    return df_work[rec > 0].copy()


def _serie_receita_por_periodo(
    df_viagens: pd.DataFrame,
    apartamento_id: int,
    df_acerto: pd.DataFrame | None,
    periodo_format: str,
) -> pd.Series:
    df_work = _anexar_colunas_dre_viagens(df_viagens, df_acerto, apartamento_id)
    cv = _get_case_insensitive_column_map(df_work.columns)
    col_dt = cv.get("dataviagemmotorista")
    col_rec = cv.get("receita")
    if not col_dt or not col_rec:
        return pd.Series(dtype=float)
    tmp = df_work[[col_dt, col_rec]].copy()
    tmp["_rec"] = pd.to_numeric(tmp[col_rec], errors="coerce").fillna(0)
    tmp = tmp[tmp["_rec"] > 0]
    if tmp.empty:
        return pd.Series(dtype=float)
    tmp["Periodo"] = pd.to_datetime(tmp[col_dt], errors="coerce").dt.to_period(periodo_format)
    tmp.dropna(subset=["Periodo"], inplace=True)
    return tmp.groupby("Periodo")["_rec"].sum()
   
def _viagens_base_dre(df_viagens_cliente: pd.DataFrame) -> pd.DataFrame:
    """Viagens com frete > 0 e colunas para DRE (mesma base da visão comercial)."""
    if df_viagens_cliente.empty:
        return pd.DataFrame()
    cv = _get_case_insensitive_column_map(df_viagens_cliente.columns)
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
    df = df_viagens_cliente[cols_v].drop_duplicates(subset=[cv["numero"]]).copy()
    fe_col = cv["freteempresa"]
    fm_col = cv.get("fretemotorista")
    mask = pd.to_numeric(df[fe_col], errors="coerce").fillna(0) > 0
    if fm_col:
        mask = mask | (pd.to_numeric(df[fm_col], errors="coerce").fillna(0) > 0)
    df = df[mask]
    return df


def _faturamento_dre_summary(
    df_viagens_cliente, df_fat_filtrado, df_acerto, apartamento_id: int
) -> tuple[float, list]:
    cv_all = _get_case_insensitive_column_map(df_viagens_cliente.columns)
    if "receita" in cv_all:
        rec = pd.to_numeric(df_viagens_cliente[cv_all["receita"]], errors="coerce").fillna(0)
        df_dre = df_viagens_cliente[rec > 0].copy()
    else:
        df_base = _viagens_base_dre(df_viagens_cliente)
        if df_base.empty:
            return 0.0, []
        df_dre = dre.aplicar_dre_em_dataframe(df_base, df_acerto, dre_opts=obter_dre_opts(apartamento_id))
    if df_dre.empty:
        return 0.0, []
    total = float(df_dre["receita"].sum())
    cv = _get_case_insensitive_column_map(df_dre.columns)
    col_num = cv.get("numero", "numero")
    df_ctes = df_dre[df_dre["receita"] > 0].copy()
    if df_ctes.empty:
        return total, []
    cm_fat = _get_case_insensitive_column_map(df_fat_filtrado.columns) if not df_fat_filtrado.empty else {}
    col_nc = cm_fat.get("numconhec")
    records = []
    for _, row in df_ctes.iterrows():
        numero = row[col_num]
        num_conhec = None
        if col_nc and not df_fat_filtrado.empty:
            fat_row = df_fat_filtrado[df_fat_filtrado[cm_fat["numero"]] == numero]
            if not fat_row.empty:
                num_conhec = fat_row.iloc[0][col_nc]
        display = str(int(numero)) if pd.notna(numero) else str(numero)
        if num_conhec is not None and pd.notna(num_conhec):
            try:
                nc = int(float(num_conhec))
                if nc != 0:
                    display = f"{display} ({nc})"
            except (TypeError, ValueError):
                pass
        records.append({"id": int(numero) if pd.notna(numero) else numero, "display": display})
    return total, records


def get_dashboard_summary(
    apartamento_id: int,
    start_date: datetime = None,
    end_date: datetime = None,
    placa_filter: str = "Todos",
    filial_filter: list = None,
    tipo_negocio_filter: str = "Todos",
    unidade_embarque_filter: list | None = None,
    embarcador_filter: str = "Todos",
) -> dict:
    """
    Calcula os KPIs para o dashboard principal usando a nova função mestre de filtragem.
    """
    sync_expense_groups_if_needed(apartamento_id)
    
    filtered_data = _obter_dados_filtrados_mestre(
        apartamento_id,
        start_date,
        end_date,
        placa_filter,
        filial_filter,
        tipo_negocio_filter,
        unidade_embarque_filter,
        embarcador_filter,
    )
    df_viagens_cliente = filtered_data["df_viagens_cliente"]
    df_despesas_filtrado = filtered_data["df_despesas_filtrado"]
    df_fat_filtrado = filtered_data["df_fat_filtrado"]
    df_contas_pagar_raw = filtered_data["df_contas_pagar_raw"]
    df_contas_receber_raw = filtered_data["df_contas_receber_raw"]
    df_flags = filtered_data["df_flags"]
    df_despesas_raw = filtered_data["df_despesas_raw"]
    df_acerto_motorista_raw = filtered_data["df_acerto_motorista_raw"]

    summary = {}
    
    summary['faturamento_total_viagens'], summary['faturamento_conhecimentos'] = _faturamento_dre_summary(
        df_viagens_cliente, df_fat_filtrado, df_acerto_motorista_raw, apartamento_id
    )

    expense_data = _get_final_expense_dataframes(df_viagens_cliente, df_despesas_filtrado, df_flags, df_acerto_motorista_raw)
    df_custos = expense_data["custos"]
    df_despesas_gerais = expense_data["despesas"]
    df_custo_previa = expense_data.get("custo_previa", pd.DataFrame())
    df_custo_nota = expense_data.get("custo_nota", pd.DataFrame())

    summary["custo_previa_conhecimento"] = (
        float(df_custo_previa["valor_calculado"].sum()) if not df_custo_previa.empty else 0.0
    )
    summary["custo_nota_itemnota"] = (
        float(df_custo_nota["valor_calculado"].sum()) if not df_custo_nota.empty else 0.0
    )
    summary["custo_total_viagem"] = summary["custo_previa_conhecimento"] + summary["custo_nota_itemnota"]
    summary["total_despesas_gerais"] = (
        float(df_despesas_gerais["valor_calculado"].sum()) if not df_despesas_gerais.empty else 0.0
    )
    
    df_tipo_d_kpi = _calcular_df_tipo_d(
        df_despesas_raw,
        df_flags,
        start_date,
        end_date,
        filial_filter,
        tipo_negocio_filter,
        unidade_embarque_filter,
    )
    summary['total_despesas_tipo_d'] = _total_tipo_d_com_rateio(df_tipo_d_kpi, placa_filter, apartamento_id)

    summary['saldo_contas_a_pagar_pendentes'] = _calcular_contas_pagar_pendentes(df_contas_pagar_raw)
    summary['saldo_contas_a_receber_pendentes'] = _calcular_contas_receber_pendentes(df_contas_receber_raw)
    summary["financeiro_pagar"] = _resumo_financeiro_pendente(df_contas_pagar_raw, "pagar")
    summary["financeiro_receber"] = _resumo_financeiro_pendente(df_contas_receber_raw, "receber")

    summary["receita_comercio"] = _total_itens_comercio(
        df_despesas_raw, start_date, end_date, filial_filter, "venda", unidade_embarque_filter
    )
    summary["despesa_comercio"] = _total_itens_comercio(
        df_despesas_raw, start_date, end_date, filial_filter, "null", unidade_embarque_filter
    )
    summary["total_investimento"] = _total_itens_investimento(
        df_despesas_raw, start_date, end_date, filial_filter, unidade_embarque_filter
    )
    summary["total_investimento_estoque"] = _total_investimento_estoque(apartamento_id)

    custo_operacional_total = summary['custo_total_viagem'] + summary['total_despesas_gerais'] + summary['total_despesas_tipo_d']
    summary['saldo_geral'] = summary['faturamento_total_viagens'] - custo_operacional_total
    summary['margem_frete'] = (summary['saldo_geral'] / summary['faturamento_total_viagens'] * 100) if summary.get('faturamento_total_viagens', 0) > 0 else 0

    n_ctes = len(summary.get("faturamento_conhecimentos") or [])
    summary["qtd_ctes"] = n_ctes
    summary["custo_por_cte"] = (
        float(custo_operacional_total) / n_ctes if n_ctes > 0 else 0.0
    )
    summary["ticket_medio"] = (
        float(summary["faturamento_total_viagens"]) / n_ctes if n_ctes > 0 else 0.0
    )

    metas = obter_metas_bi(apartamento_id)
    summary["meta_margem_pct"] = metas.get("meta_margem_pct")
    summary["meta_r_km"] = metas.get("meta_r_km")
    summary["meta_margem_status"] = status_vs_meta(
        float(summary["margem_frete"]), metas.get("meta_margem_pct"), maior_melhor=True
    )

    # Comparativo MoM: período anterior de mesma duração (sem recursão)
    if start_date is not None and end_date is not None:
        try:
            dur = end_date - start_date
            prev_end = start_date - timedelta(microseconds=1)
            prev_start = prev_end - dur
            prev_summary = _dashboard_summary_core(
                apartamento_id,
                prev_start,
                prev_end,
                placa_filter,
                filial_filter,
                tipo_negocio_filter,
                unidade_embarque_filter,
                embarcador_filter,
            )
            summary["comparativo"] = {
                "receita": formatar_delta_pct(
                    summary["faturamento_total_viagens"],
                    prev_summary.get("faturamento_total_viagens", 0),
                ),
                "custo": formatar_delta_pct(
                    custo_operacional_total,
                    prev_summary.get("custo_operacional", 0),
                ),
                "resultado": formatar_delta_pct(
                    summary["saldo_geral"],
                    prev_summary.get("saldo_geral", 0),
                ),
                "margem": formatar_delta_pct(
                    summary["margem_frete"],
                    prev_summary.get("margem_frete", 0),
                ),
                "custo_por_cte": formatar_delta_pct(
                    summary["custo_por_cte"],
                    prev_summary.get("custo_por_cte", 0),
                ),
                "periodo_anterior": {
                    "inicio": prev_start.strftime("%Y-%m-%d"),
                    "fim": prev_end.strftime("%Y-%m-%d"),
                },
            }
        except Exception as e:
            print(f"[BI] MoM comparativo falhou: {e}")
            summary["comparativo"] = None
    else:
        summary["comparativo"] = None

    return summary


def _dashboard_summary_core(
    apartamento_id: int,
    start_date: datetime = None,
    end_date: datetime = None,
    placa_filter: str = "Todos",
    filial_filter: list = None,
    tipo_negocio_filter: str = "Todos",
    unidade_embarque_filter: list | None = None,
    embarcador_filter: str = "Todos",
) -> dict:
    """KPIs do período sem MoM (usado no comparativo)."""
    filtered_data = _obter_dados_filtrados_mestre(
        apartamento_id,
        start_date,
        end_date,
        placa_filter,
        filial_filter,
        tipo_negocio_filter,
        unidade_embarque_filter,
        embarcador_filter,
    )
    df_viagens_cliente = filtered_data["df_viagens_cliente"]
    df_despesas_filtrado = filtered_data["df_despesas_filtrado"]
    df_fat_filtrado = filtered_data["df_fat_filtrado"]
    df_flags = filtered_data["df_flags"]
    df_despesas_raw = filtered_data["df_despesas_raw"]
    df_acerto_motorista_raw = filtered_data["df_acerto_motorista_raw"]

    fat, ctes = _faturamento_dre_summary(
        df_viagens_cliente, df_fat_filtrado, df_acerto_motorista_raw, apartamento_id
    )
    expense_data = _get_final_expense_dataframes(
        df_viagens_cliente, df_despesas_filtrado, df_flags, df_acerto_motorista_raw
    )
    df_custo_previa = expense_data.get("custo_previa", pd.DataFrame())
    df_custo_nota = expense_data.get("custo_nota", pd.DataFrame())
    df_despesas_gerais = expense_data["despesas"]
    custo_previa = float(df_custo_previa["valor_calculado"].sum()) if not df_custo_previa.empty else 0.0
    custo_nota = float(df_custo_nota["valor_calculado"].sum()) if not df_custo_nota.empty else 0.0
    custo_viagem = custo_previa + custo_nota
    desp_gerais = float(df_despesas_gerais["valor_calculado"].sum()) if not df_despesas_gerais.empty else 0.0
    df_tipo_d = _calcular_df_tipo_d(
        df_despesas_raw, df_flags, start_date, end_date, filial_filter, tipo_negocio_filter, unidade_embarque_filter
    )
    tipo_d = _total_tipo_d_com_rateio(df_tipo_d, placa_filter, apartamento_id)
    custo_op = custo_viagem + desp_gerais + tipo_d
    saldo = fat - custo_op
    margem = (saldo / fat * 100) if fat > 0 else 0.0
    n = len(ctes or [])
    return {
        "faturamento_total_viagens": fat,
        "custo_operacional": custo_op,
        "saldo_geral": saldo,
        "margem_frete": margem,
        "custo_por_cte": (custo_op / n) if n > 0 else 0.0,
        "qtd_ctes": n,
    }


def get_monthly_summary(
    apartamento_id: int,
    start_date,
    end_date,
    placa_filter,
    filial_filter,
    tipo_negocio_filter,
    unidade_embarque_filter: list | None = None,
    embarcador_filter: str = "Todos",
) -> pd.DataFrame:
    start_date, end_date = resolver_intervalo_consulta(apartamento_id, start_date, end_date)
    periodo_format = 'M'
    if (end_date - start_date).days <= 62:
        periodo_format = 'D'

    filtered_data = _obter_dados_filtrados_mestre(
        apartamento_id,
        start_date,
        end_date,
        placa_filter,
        filial_filter,
        tipo_negocio_filter,
        unidade_embarque_filter,
        embarcador_filter,
    )
    df_viagens_cliente = filtered_data["df_viagens_cliente"]
    df_despesas_filtrado = filtered_data["df_despesas_filtrado"]
    df_fat_filtrado = filtered_data["df_fat_filtrado"]
    df_flags = filtered_data["df_flags"]
    df_acerto_motorista_raw = filtered_data["df_acerto_motorista_raw"]
    df_despesas_raw = filtered_data["df_despesas_raw"]

    col_map_viagens_cli = _get_case_insensitive_column_map(df_viagens_cliente.columns)
    col_map_fat = _get_case_insensitive_column_map(df_fat_filtrado.columns)
    
    faturamento = _serie_receita_por_periodo(
        df_viagens_cliente, apartamento_id, df_acerto_motorista_raw, periodo_format
    )
    faturamento.name = 'Faturamento'

    expense_data = _get_final_expense_dataframes(df_viagens_cliente, df_despesas_filtrado, df_flags, df_acerto_motorista_raw)
    df_custos = expense_data["custos"]
    df_despesas_gerais = expense_data["despesas"]

    df_tipo_d = _calcular_df_tipo_d(
        df_despesas_raw, df_flags, start_date, end_date, filial_filter, tipo_negocio_filter
    )
    fator_tipo_d = _fator_rateio_placas_proprias(placa_filter, apartamento_id)
    if not df_tipo_d.empty and fator_tipo_d != 1.0:
        df_tipo_d = df_tipo_d.copy()
        df_tipo_d["valor_calculado"] = df_tipo_d["valor_calculado"] * fator_tipo_d

    custos_agrupados = _agrupar_valores_por_periodo(df_custos, periodo_format, "Custo")
    despesas_agrupadas = _agrupar_valores_por_periodo(df_despesas_gerais, periodo_format, "DespesasGerais")
    tipo_d_agrupado = _agrupar_valores_por_periodo(df_tipo_d, periodo_format, "DespesaTipoD")

    monthly_df = pd.concat([faturamento, custos_agrupados, despesas_agrupadas, tipo_d_agrupado], axis=1).fillna(0)
    if not monthly_df.empty:
        monthly_df["TotalDespesas"] = monthly_df.get("Custo", 0) + monthly_df.get("DespesasGerais", 0) + monthly_df.get("DespesaTipoD", 0)
    
    if not monthly_df.empty:
        monthly_df = monthly_df.reset_index()
        monthly_df.rename(columns={'index': 'Periodo'}, inplace=True)
        monthly_df['Periodo'] = monthly_df['Periodo'].dt.to_timestamp()
        date_format_str = '%d/%m/%Y' if periodo_format == 'D' else '%b/%Y'
        monthly_df['PeriodoLabel'] = monthly_df['Periodo'].dt.strftime(date_format_str)
        monthly_df = monthly_df.sort_values(by='Periodo', ascending=True)
        monthly_df = _filtrar_periodos_para_grafico(monthly_df)

    return monthly_df

def sync_expense_groups(apartamento_id: int):
    """
    Sincroniza os grupos de despesa, adicionando novos grupos encontrados nos dados,
    mas NUNCA removendo os existentes (exceto grupos DRE do conhecimento — ver abaixo).
    """
    print(f"Sincronizando grupos de despesa para o apartamento {apartamento_id}...")
    excluir_ui = {g.upper() for g in dre.GRUPOS_DRE_CONHECIMENTO}

    df_despesas = get_data_as_dataframe("relFilDespesasGerais", apartamento_id)
    col_map = _get_case_insensitive_column_map(df_despesas.columns)

    grupos_dinamicos = set()
    grupos_com_diversos = set()
    if not df_despesas.empty and "descgrupod" in col_map:
        grp_col = col_map["descgrupod"]
        for grupo in df_despesas[grp_col].dropna().unique():
            if str(grupo).strip().upper() not in excluir_ui:
                grupos_dinamicos.add(grupo)
        if "ved" in col_map:
            ved = _normalizar_ved_series(df_despesas[col_map["ved"]])
            grupos_com_diversos = {
                g
                for g in df_despesas.loc[ved == VED_DIVERSOS, grp_col].dropna().unique()
                if str(g).strip().upper() not in excluir_ui
            }

    todos_os_grupos_encontrados = grupos_dinamicos

    try:
        if todos_os_grupos_encontrados:
            with engine.connect() as conn:
                with conn.begin():
                    sql_insert = text("""
                        INSERT INTO "static_expense_groups"
                            (apartamento_id, group_name, is_despesa, is_custo_viagem, incluir_em_tipo_d)
                        VALUES (:apt_id, :group_name, :is_despesa, 'N', :incluir_tipo_d)
                        ON CONFLICT (apartamento_id, group_name) DO NOTHING
                    """)
                    for group_name in todos_os_grupos_encontrados:
                        if not group_name:
                            continue
                        marcar_tipo_d = group_name in grupos_com_diversos
                        conn.execute(
                            sql_insert,
                            {
                                "apt_id": apartamento_id,
                                "group_name": group_name,
                                "is_despesa": "S",
                                "incluir_tipo_d": marcar_tipo_d,
                            },
                        )
            print(
                "Sincronização de grupos concluída: Novos grupos foram adicionados, "
                "existentes foram preservados."
            )
        else:
            print("Nenhum grupo de despesa novo para sincronizar.")

        with engine.connect() as conn:
            with conn.begin():
                for nome in excluir_ui:
                    conn.execute(
                        text(
                            """
                            DELETE FROM "static_expense_groups"
                            WHERE apartamento_id = :apt_id
                              AND UPPER(TRIM(group_name)) = :nome
                            """
                        ),
                        {"apt_id": apartamento_id, "nome": nome},
                    )
    except Exception as e:
        print(f"ERRO CRÍTICO durante a sincronização de grupos: {e}")

def get_all_group_flags(apartamento_id: int):

    try:
        with db.engine.connect() as conn:
            query = text('SELECT "group_name", "is_despesa", "is_custo_viagem", "incluir_em_tipo_d" FROM "static_expense_groups" WHERE "apartamento_id" = :apt_id')
            df = pd.read_sql(query, conn, params={"apt_id": apartamento_id})
            if not df.empty:
                excluir = {g.upper() for g in dre.GRUPOS_DRE_CONHECIMENTO}
                df = df[
                    ~df["group_name"].astype(str).str.upper().isin(excluir)
                ].copy()
            return df
    except Exception as e:
        print(f"Erro ao buscar flags de grupo: {e}")
        return pd.DataFrame(columns=['group_name', 'is_despesa', 'is_custo_viagem'])

def get_all_expense_groups(apartamento_id: int):
    df_flags = get_all_group_flags(apartamento_id)
    if df_flags.empty:
        return []
    return df_flags['group_name'].dropna().unique().tolist()

def update_all_group_flags(apartamento_id: int, update_data: dict):
    print(f"DEBUG: Dados recebidos do formulário para atualização: {update_data}")
    try:
        # --- INÍCIO DA CORREÇÃO ---
        # Adiciona o bloco 'with' para garantir que a variável 'conn' seja definida
        with engine.connect() as conn:
            with conn.begin():
                sql_update_flags = text("""
                    UPDATE "static_expense_groups" 
                    SET "is_despesa" = :is_despesa, "is_custo_viagem" = :is_custo, "incluir_em_tipo_d" = :incluir_tipo_d
                    WHERE "group_name" = :group_name AND "apartamento_id" = :apt_id
                """)
                for group_name, data in update_data.items():
                    classification = data['classification']
                    is_despesa = 'S' if classification == 'despesa' else 'N'
                    is_custo = 'S' if classification == 'custo_viagem' else 'N'
                    incluir_tipo_d = data['incluir_tipo_d']

                    conn.execute(sql_update_flags, {
                        "is_despesa": is_despesa, "is_custo": is_custo,
                        "incluir_tipo_d": incluir_tipo_d,
                        "group_name": group_name, "apt_id": apartamento_id
                    })
        # --- FIM DA CORREÇÃO ---
        sync_expense_groups(apartamento_id)
        print(f"Flags de grupo atualizadas com sucesso para o apartamento {apartamento_id}.")
    except Exception as e:
        print(f"Erro ao atualizar flags de grupo de despesa: {e}")
        raise e


def get_unique_filiais(apartamento_id: int) -> list[str]:
    return _cached_filter_options(
        apartamento_id,
        "filiais",
        lambda: _get_unique_filiais_uncached(apartamento_id),
    )


def _get_unique_filiais_uncached(apartamento_id: int) -> list[str]:
    if sati_enabled_for_apartment(engine, apartamento_id):
        try:
            schema = get_sati_schema(apartamento_id)
            if re.match(r"^c\d+$", schema or "", re.I):
                sql = text(
                    f"""
                    SELECT DISTINCT c.codfilial, TRIM(COALESCE(f.nome, '')) AS nome
                    FROM {schema}.conhecimento c
                    INNER JOIN {schema}.filial f ON f.codfilial = c.codfilial
                    WHERE c.cancelado IS DISTINCT FROM 'S'
                    ORDER BY c.codfilial
                    """
                )
                with get_sati_engine().connect() as conn:
                    rows = conn.execute(sql).fetchall()
                labels = [
                    _filial_display_label(r[0], r[1]) for r in rows if r[0] is not None
                ]
                if labels:
                    unique_filiais = sorted({lbl.strip() for lbl in labels if lbl and lbl.strip()})
                    return ["Todos"] + unique_filiais
        except Exception as exc:
            print(f"Aviso get_unique_filiais SATI: {exc}")

    table_names = [
        "relFilViagensFatCliente",
        "relFilDespesasGerais",
        "relFilContasPagarDet",
        "relFilContasReceber",
        "relFilViagensCliente",
    ]

    labels: list[str] = []
    for name in table_names:
        df = get_data_as_dataframe(name, apartamento_id)
        if df.empty:
            continue
        col_map = _get_case_insensitive_column_map(df.columns)
        labels.extend(_coletar_filiais_de_df(df, col_map))

    if not labels:
        return ["Todos"]

    unique_filiais = sorted({lbl.strip() for lbl in labels if lbl and lbl.strip()})
    return ["Todos"] + unique_filiais



def get_unique_unidades_embarque(apartamento_id: int) -> list[str]:
    return _cached_filter_options(
        apartamento_id,
        "unidades_embarque",
        lambda: _get_unique_unidades_embarque_uncached(apartamento_id),
    )


def _get_unique_unidades_embarque_uncached(apartamento_id: int) -> list[str]:
    if sati_enabled_for_apartment(engine, apartamento_id):
        try:
            schema = get_sati_schema(apartamento_id)
            if re.match(r"^c\d+$", schema or "", re.I):
                sql = text(
                    f"""
                    SELECT DISTINCT ue.codunidadeembarque,
                           TRIM(COALESCE(ue.descricao, '')) AS nome
                    FROM {schema}.unidadeembarque ue
                    WHERE ue.codunidadeembarque IS NOT NULL
                    ORDER BY ue.codunidadeembarque
                    """
                )
                with get_sati_engine().connect() as conn:
                    rows = conn.execute(sql).fetchall()
                labels = [
                    _filial_display_label(r[0], r[1])
                    for r in rows
                    if r[0] is not None and (r[1] or "").strip()
                ]
                if labels:
                    unique = sorted({lbl.strip() for lbl in labels if lbl and lbl.strip()})
                    return ["Todos"] + unique
        except Exception as exc:
            print(f"Aviso get_unique_unidades_embarque SATI: {exc}")

    if sati_enabled_for_apartment(engine, apartamento_id):
        return ["Todos"]

    table_names = [
        "relFilViagensCliente",
        "relFilViagensFatCliente",
        "relFilDespesasGerais",
    ]
    labels: list[str] = []
    for name in table_names:
        df = get_data_as_dataframe(name, apartamento_id)
        if df.empty:
            continue
        col_map = _get_case_insensitive_column_map(df.columns)
        labels.extend(_coletar_unidades_embarque_de_df(df, col_map))

    if not labels:
        return ["Todos"]

    unique = sorted({lbl.strip() for lbl in labels if lbl and lbl.strip()})
    return ["Todos"] + unique


def _merge_embarcadores_lista(items: list[dict]) -> list[dict]:
    vistos: dict[str, dict] = {}
    for item in items:
        cod = str(item.get("cod") or "").strip()
        if not cod or cod in vistos:
            continue
        vistos[cod] = item
    return sorted(vistos.values(), key=lambda x: (x.get("label") or x["cod"]).upper())


def get_unique_embarcadores(apartamento_id: int) -> list[dict]:
    return _cached_filter_options(
        apartamento_id,
        "embarcadores",
        lambda: _get_unique_embarcadores_uncached(apartamento_id),
    )


def _get_unique_embarcadores_uncached(apartamento_id: int) -> list[dict]:
    """Embarcadores do cadastro SATI + distintos nos CT-es (fallback Excel)."""
    items: list[dict] = []
    sati_on = False
    try:
        from sati_integration.db.sati_source import (
            fetch_embarcadores_catalog,
            sati_enabled_for_apartment,
        )
        from app.data.database import engine as app_engine

        sati_on = sati_enabled_for_apartment(app_engine, apartamento_id)
        if sati_on:
            items.extend(fetch_embarcadores_catalog(apartamento_id))
            if items:
                return _merge_embarcadores_lista(items)
    except Exception as exc:
        print(f"AVISO: fetch_embarcadores_catalog: {exc}")

    # Com SATI ativo, não varrer relFilViagens* inteiro (minutos em bases grandes).
    if sati_on:
        return _merge_embarcadores_lista(items)

    for table in ("relFilViagensCliente", "relFilViagensFatCliente"):
        df = get_data_as_dataframe(table, apartamento_id)
        if df.empty:
            continue
        col_map = _get_case_insensitive_column_map(df.columns)
        items.extend(_coletar_embarcadores_de_df(df, col_map))

    return _merge_embarcadores_lista(items)


def get_faturamento_details_dashboard_data(apartamento_id: int, start_date, end_date, placa_filter, filial_filter, tipo_negocio_filter):
    dashboard_data = {}
    start_date, end_date = resolver_intervalo_consulta(apartamento_id, start_date, end_date)

    filtered_data = _obter_dados_filtrados_mestre(apartamento_id, start_date, end_date, placa_filter, filial_filter, tipo_negocio_filter)
    df_viagens_cliente = filtered_data["df_viagens_cliente"]
    df_despesas_filtrado = filtered_data["df_despesas_filtrado"]
    df_fat_filtrado = filtered_data["df_fat_filtrado"]
    df_flags = filtered_data["df_flags"]
    df_acerto_motorista_raw = filtered_data["df_acerto_motorista_raw"]
    df_despesas_raw = filtered_data["df_despesas_raw"]

    if df_viagens_cliente.empty:
        return {}

    col_map_viagens_cli = _get_case_insensitive_column_map(df_viagens_cliente.columns)
    col_map_fat = _get_case_insensitive_column_map(df_fat_filtrado.columns)

    periodo = 'D' if (end_date - start_date).days <= 62 else 'M'
    
    fat_evolucao = _serie_receita_por_periodo(
        df_viagens_cliente, apartamento_id, df_acerto_motorista_raw, periodo
    )
    df_rec = _df_viagens_com_receita(df_viagens_cliente, apartamento_id, df_acerto_motorista_raw)
    cv_rec = _get_case_insensitive_column_map(df_rec.columns) if not df_rec.empty else {}
    col_receita = cv_rec.get("receita", "receita")

    expense_data = _get_final_expense_dataframes(df_viagens_cliente, df_despesas_filtrado, df_flags, df_acerto_motorista_raw)
    df_custos = expense_data["custos"]
    df_despesas_gerais = expense_data["despesas"]

    df_tipo_d = _calcular_df_tipo_d(
        df_despesas_raw, df_flags, start_date, end_date, filial_filter, tipo_negocio_filter
    )
    fator_tipo_d = _fator_rateio_placas_proprias(placa_filter, apartamento_id)
    if not df_tipo_d.empty and fator_tipo_d != 1.0:
        df_tipo_d = df_tipo_d.copy()
        df_tipo_d["valor_calculado"] = df_tipo_d["valor_calculado"] * fator_tipo_d

    dfs_to_concat = [df for df in (df_custos, df_despesas_gerais, df_tipo_d) if not df.empty]
    custo_evolucao = pd.Series(dtype=float)
    if dfs_to_concat:
        df_todos_custos = pd.concat(dfs_to_concat, ignore_index=True)
        custo_evolucao = _agrupar_valores_por_periodo(df_todos_custos, periodo, "Custo")
        custo_evolucao.index.name = "Periodo"

    evolucao_df = pd.DataFrame({"Faturamento": fat_evolucao, "Custo": custo_evolucao}).fillna(0)
    evolucao_df.index.name = "Periodo"
    evolucao_df = evolucao_df.reset_index()
    if "index" in evolucao_df.columns:
        evolucao_df.rename(columns={"index": "Periodo"}, inplace=True)

    if not evolucao_df.empty and "Periodo" in evolucao_df.columns:
        evolucao_df["Periodo"] = pd.to_datetime(
            evolucao_df["Periodo"].apply(
                lambda p: p.to_timestamp() if hasattr(p, "to_timestamp") else p
            ),
            errors="coerce",
        )
        fmt = "%d/%m/%Y" if periodo == "D" else "%b/%Y"
        evolucao_df = _filtrar_periodos_para_grafico(evolucao_df)
        if not evolucao_df.empty:
            evolucao_df = evolucao_df.sort_values("Periodo")
            evolucao_df["Periodo"] = evolucao_df["Periodo"].dt.strftime(fmt)
            dashboard_data["evolucao_faturamento_custo"] = evolucao_df[
                ["Periodo", "Faturamento", "Custo"]
            ].to_dict(orient="records")

    if not df_rec.empty and cv_rec.get("nomecliente"):
        top_clientes = (
            df_rec.groupby(cv_rec["nomecliente"])[col_receita]
            .sum()
            .nlargest(10)
            .sort_values(ascending=False)
            .reset_index()
        )
        top_clientes.columns = ["nomeCliente", "freteEmpresa"]
        dashboard_data["top_clientes"] = top_clientes.to_dict(orient="records")

    filial_col = cv_rec.get("nomefilial") or col_map_viagens_cli.get("nomefilial")
    if not df_rec.empty and filial_col and filial_col in df_rec.columns:
        fat_filial = df_rec.groupby(filial_col)[col_receita].sum().reset_index()
        fat_filial.columns = ["nomeFilial", "freteEmpresa"]
        fat_filial = fat_filial.sort_values("freteEmpresa", ascending=False)
        dashboard_data["faturamento_filial"] = fat_filial.to_dict(orient="records")

    if 'cidorigemformat' in col_map_viagens_cli and 'ciddestinoformat' in col_map_viagens_cli:
        df_viagens_cliente['rota'] = df_viagens_cliente[col_map_viagens_cli['cidorigemformat']] + ' -> ' + df_viagens_cliente[col_map_viagens_cli['ciddestinoformat']]
        top_rotas = df_viagens_cliente['rota'].value_counts().nlargest(10).sort_values(ascending=False).reset_index()
        top_rotas.columns = ['rota', 'contagem']
        dashboard_data['top_rotas'] = top_rotas.to_dict(orient='records')
        
        if 'pesosaida' in col_map_viagens_cli:
            peso_col = col_map_viagens_cli['pesosaida']
            df_peso = df_viagens_cliente.copy()
            df_peso['_peso_num'] = pd.to_numeric(df_peso[peso_col], errors='coerce').fillna(0)
            volume_rota = (
                df_peso.groupby('rota')['_peso_num']
                .sum()
                .nlargest(10)
                .sort_values(ascending=False)
                .reset_index()
            )
            volume_rota.columns = ['rota', 'pesoSaida']
            dashboard_data['volume_por_rota'] = volume_rota.to_dict(orient='records')
    
    if 'placaveiculo' in col_map_viagens_cli:
        viagens_veiculo = df_viagens_cliente[col_map_viagens_cli['placaveiculo']].value_counts().nlargest(10).sort_values(ascending=False).reset_index()
        viagens_veiculo.columns = ['placa', 'contagem']
        dashboard_data['viagens_por_veiculo'] = viagens_veiculo.to_dict(orient='records')
        
    if not df_rec.empty and cv_rec.get("nomemotorista"):
        fat_motorista = (
            df_rec.groupby(cv_rec["nomemotorista"])[col_receita]
            .sum()
            .nlargest(10)
            .sort_values(ascending=False)
            .reset_index()
        )
        fat_motorista.columns = ["nomeMotorista", "faturamento"]
        dashboard_data["faturamento_motorista"] = fat_motorista.to_dict(orient="records")

    if not df_rec.empty and cv_rec.get("descricaomercadoria"):
        fat_por_mercadoria = (
            df_rec.groupby(cv_rec["descricaomercadoria"])[col_receita]
            .sum()
            .nlargest(7)
            .reset_index()
        )
        fat_por_mercadoria.columns = ["mercadoria", "faturamento"]
        dashboard_data["faturamento_por_mercadoria"] = fat_por_mercadoria.to_dict(orient="records")

    return dashboard_data

_ROBO_ENV_FALLBACK = {
    "URL_LOGIN": ("URL_LOGIN", "ROBO_URL_LOGIN"),
    "USUARIO_ROBO": ("USUARIO_ROBO", "ROBO_USUARIO"),
    "SENHA_ROBO": ("SENHA_ROBO", "ROBO_SENHA"),
}


def normalizar_url_login(url: str | None) -> str:
    import re

    u = (url or "").strip()
    if not u:
        return u
    if not re.match(r"^https?://", u, re.I):
        u = "https://" + u.lstrip("/")
    return u


def _merge_robo_env_defaults(configs: dict) -> dict:
    """Preenche credenciais do robô a partir do .env quando não estão no banco."""
    merged = dict(configs or {})
    for chave, env_names in _ROBO_ENV_FALLBACK.items():
        if str(merged.get(chave) or "").strip():
            continue
        for env_name in env_names:
            val = os.getenv(env_name, "").strip()
            if val:
                merged[chave] = val
                break
    if merged.get("URL_LOGIN"):
        merged["URL_LOGIN"] = normalizar_url_login(merged["URL_LOGIN"])
    return merged


def robo_credenciais_configuradas(configs: dict) -> bool:
    c = _merge_robo_env_defaults(configs)
    return bool(c.get("URL_LOGIN") and c.get("USUARIO_ROBO") and c.get("SENHA_ROBO"))


def ler_configuracoes_robo(apartamento_id: int):
    """Lê credenciais sempre do banco do app (dashboard_db), não do SATI."""
    try:
        with db.engine.connect() as conn:
            df = pd.read_sql_query(
                text(
                    'SELECT chave, valor FROM configuracoes_robo '
                    "WHERE apartamento_id = :apt_id"
                ),
                conn,
                params={"apt_id": apartamento_id},
            )
        if df.empty:
            return _merge_robo_env_defaults({})
        df.columns = [str(c).lower() for c in df.columns]
        cfg = pd.Series(df.valor.values, index=df.chave).to_dict()
        return _merge_robo_env_defaults(cfg)
    except Exception as e:
        print(f"ERRO ao ler configuracoes_robo (apt {apartamento_id}): {e}")
        return _merge_robo_env_defaults({})

def salvar_configuracoes_robo(apartamento_id: int, configs: dict):
    try:
        with db.engine.connect() as conn:
            with conn.begin() as trans:
                sql = text("""
                    INSERT INTO "configuracoes_robo" (apartamento_id, chave, valor) 
                    VALUES (:apt_id, :chave, :valor)
                    ON CONFLICT (apartamento_id, chave) 
                    DO UPDATE SET valor = EXCLUDED.valor
                """)
                for chave, valor in configs.items():
                    if valor is not None:
                        v = str(valor)
                        if chave == "URL_LOGIN":
                            v = normalizar_url_login(v)
                        conn.execute(sql, {
                            "apt_id": apartamento_id,
                            "chave": chave,
                            "valor": v,
                        })
        print(f"Configurações salvas com sucesso para o apartamento {apartamento_id}.")
    except Exception as e:
        print(f"ERRO CRÍTICO ao salvar configurações para o apartamento {apartamento_id}: {e}")

def get_users_for_apartment(apartamento_id: int):
    with engine.connect() as conn:
        sql = text("""
            SELECT id, nome, email, role 
            FROM usuarios 
            WHERE apartamento_id = :apt_id
        """)
        df = pd.read_sql(sql, conn, params={"apt_id": apartamento_id})
        return df.to_dict(orient='records')
    
def add_user_to_apartment(apartamento_id: int, nome: str, email: str, password_hash: str, role: str):
    try:
        with engine.connect() as conn:
            with conn.begin() as trans:
                query = text('INSERT INTO usuarios (apartamento_id, nome, email, password_hash, role) VALUES (:apt_id, :nome, :email, :hash, :role)')
                conn.execute(query, {
                    "apt_id": apartamento_id, "nome": nome, "email": email, "hash": password_hash, "role": role
                })
        return True, "Utilizador adicionado com sucesso."
    except Exception as e:
        if "usuarios_email_key" in str(e):
             return False, "Erro: Este email já está registado."
        return False, f"Erro ao adicionar utilizador: {e}"

def update_user_in_apartment(user_id: int, apartamento_id: int, nome: str, email: str, role: str, new_password_hash: str = None):
    try:
        with engine.connect() as conn:
            with conn.begin() as trans:
                if new_password_hash:
                    sql = text("""
                        UPDATE usuarios SET nome = :nome, email = :email, role = :role, password_hash = :hash
                        WHERE id = :user_id AND apartamento_id = :apt_id
                    """)
                    conn.execute(sql, {
                        "nome": nome, "email": email, "role": role, "hash": new_password_hash,
                        "user_id": user_id, "apt_id": apartamento_id
                    })
                else:
                    sql = text("""
                        UPDATE usuarios SET nome = :nome, email = :email, role = :role
                        WHERE id = :user_id AND apartamento_id = :apt_id
                    """)
                    conn.execute(sql, {
                        "nome": nome, "email": email, "role": role,
                        "user_id": user_id, "apt_id": apartamento_id
                    })
        return True, "Utilizador atualizado com sucesso."
    except Exception as e:
        if "usuarios_email_key" in str(e):
             return False, "Erro: Este email já pertence a outro utilizador."
        return False, f"Erro ao atualizar utilizador: {e}"

def delete_user_from_apartment(user_id: int, apartamento_id: int):
    try:
        with engine.connect() as conn:
            with conn.begin() as trans:
                sql = text("DELETE FROM usuarios WHERE id = :user_id AND apartamento_id = :apt_id")
                conn.execute(sql, {"user_id": user_id, "apt_id": apartamento_id})
        return True, "Utilizador apagado com sucesso."
    except Exception as e:
        return False, f"Erro ao apagar utilizador: {e}"

def get_user_by_id(user_id: int, apartamento_id: int):
    try:
        with engine.connect() as conn:
            sql = text('SELECT id, nome, email, role FROM usuarios WHERE id = :user_id AND apartamento_id = :apt_id')
            result = conn.execute(sql, {"user_id": user_id, "apt_id": apartamento_id})
            user_data = result.mappings().first()
            if user_data:
                return dict(user_data)
            return None
    except Exception as e:
        print(f"Erro ao buscar utilizador por ID: {e}")
        return None
    
def get_all_apartments():
    try:
        with engine.connect() as conn:
            df = pd.read_sql('SELECT id, nome_empresa, status, data_criacao FROM apartamentos', conn)
            return df.to_dict(orient='records')
    except Exception as e:
        print(f"Erro ao buscar apartamentos: {e}")
        return []

def create_apartment_and_admin(nome_empresa: str, admin_nome: str, admin_email: str, password_hash: str):
    try:
        with engine.connect() as conn:
            with conn.begin() as trans:
                now = datetime.now().isoformat()
                apartamento_slug = slugify(nome_empresa)
                sql_apartamento = text('INSERT INTO apartamentos (nome_empresa, status, data_criacao, slug) VALUES (:nome, :status, :data, :slug) RETURNING id')
                result = conn.execute(sql_apartamento, {
                    "nome": nome_empresa, 
                    "status": 'ativo', 
                    "data": now,
                    "slug": apartamento_slug
                })
                apartamento_id = result.scalar_one()
                sql_usuario = text('INSERT INTO usuarios (apartamento_id, nome, email, password_hash, role) VALUES (:apt_id, :nome, :email, :hash, :role)')
                conn.execute(sql_usuario, {
                    "apt_id": apartamento_id, "nome": admin_nome, "email": admin_email,
                    "hash": password_hash, "role": 'admin'
                })
        return True, f"Apartamento '{nome_empresa}' e admin '{admin_email}' criados com sucesso."
    except Exception as e:
        if "unique_slug" in str(e):
            return False, "Erro: Já existe uma empresa com um nome muito parecido. Por favor, escolha outro nome."
        if "usuarios_email_key" in str(e):
             return False, "Erro: O email do administrador já existe na base de dados."
        return False, f"Ocorreu um erro inesperado: {e}"

def get_apartment_details(apartamento_id: int):
    try:
        with db.engine.connect() as conn:
            query = text('SELECT * FROM apartamentos WHERE id = :apt_id')
            result = conn.execute(query, {"apt_id": apartamento_id})
            apartamento = result.mappings().first()
            return apartamento
    except Exception as e:
        print(f"Erro ao buscar detalhes do apartamento: {e}")
        return None

def update_apartment_details(apartamento_id: int, nome_empresa: str, status: str, data_vencimento: str, notas: str):
    try:
        with db.engine.connect() as conn:
            with conn.begin():
                query = text("""
                    UPDATE apartamentos 
                    SET nome_empresa = :nome, status = :status, 
                        data_vencimento = :venc, notas_admin = :notas 
                    WHERE id = :apt_id
                """)
                conn.execute(query, {
                    "nome": nome_empresa,
                    "status": status,
                    "venc": data_vencimento,
                    "notas": notas,
                    "apt_id": apartamento_id
                })
        return True, "Apartamento atualizado com sucesso."
    except Exception as e:
        return False, f"Ocorreu um erro ao atualizar o apartamento: {e}"

def get_apartments_with_usage_stats():
    data_tables = [info["table"] for info in config.EXCEL_FILES_CONFIG.values()]
    try:
        with engine.connect() as conn:
            # A query principal não muda
            df_apartamentos = pd.read_sql('SELECT id, nome_empresa, status, data_criacao, slug FROM apartamentos', conn)
            if df_apartamentos.empty:
                return []
            
            apartamentos_list = df_apartamentos.to_dict(orient='records')

            for apt in apartamentos_list:
                total_registos = 0
                apt_id = apt['id']
                for table in data_tables:
                    if db.table_exists(table):
                        query_count = text(f'SELECT COUNT(*) FROM "{table}" WHERE "apartamento_id" = :apt_id')
                        count = conn.execute(query_count, {"apt_id": apt_id}).scalar_one_or_none()
                        if count:
                            total_registos += count
                apt['total_registos'] = total_registos

                # --- INÍCIO DA CORREÇÃO (LÓGICA PARA BUSCAR O VALOR) ---
                # Para cada apartamento, busca suas configurações de robô
                configs = ler_configuracoes_robo(apt_id) 
                # Adiciona o valor do intervalo ao dicionário do apartamento
                apt['live_monitoring_interval_minutes'] = configs.get('live_monitoring_interval_minutes', '')
                # --- FIM DA CORREÇÃO ---

            return apartamentos_list
    except Exception as e:
        print(f"Erro ao buscar apartamentos com estatísticas de uso: {e}")
        return []

def get_apartment_by_slug(slug: str):
    try:
        with engine.connect() as conn:
            sql = text("SELECT * FROM apartamentos WHERE slug = :slug")
            result = conn.execute(sql, {"slug": slug}).mappings().first()
            return dict(result) if result else None
    except Exception as e:
        print(f"Erro ao buscar apartamento por slug: {e}")
        return None

# SUBSTITUA ESTA FUNÇÃO EM data_manager.py

def get_group_flags_with_tipo_d_status(apartamento_id: int):
    """
    Flags de classificação por grupo + indicadores de VED no SATI:
    - has_tipo_d: grupo tem itens D (diversos) → checkbox Despesa Tipo D
    - has_tipo_v: itens V → rádio Custo de Viagem ou Despesa Geral (entram no KPI operacional)
    - has_tipo_e: itens E no grupo (estoque; não entram no KPI operacional)
    """
    df_flags = get_all_group_flags(apartamento_id)
    df_despesas_raw = get_data_as_dataframe("relFilDespesasGerais", apartamento_id)

    if df_flags.empty:
        return pd.DataFrame()

    df_flags["has_tipo_d"] = False
    df_flags["has_tipo_v"] = False
    df_flags["has_tipo_e"] = False

    if not df_despesas_raw.empty:
        col_map_desp = _get_case_insensitive_column_map(df_despesas_raw.columns)

        if "ved" in col_map_desp and "descgrupod" in col_map_desp:
            ved = _normalizar_ved_series(df_despesas_raw[col_map_desp["ved"]])
            grp_col = col_map_desp["descgrupod"]
            grupos_com_tipo_d = df_despesas_raw.loc[ved == VED_DIVERSOS, grp_col].dropna().unique()
            grupos_com_tipo_v = df_despesas_raw.loc[ved == VED_VEICULO, grp_col].dropna().unique()
            grupos_com_tipo_e = df_despesas_raw.loc[ved == VED_ESTOQUE, grp_col].dropna().unique()

            df_flags["has_tipo_d"] = df_flags["group_name"].isin(grupos_com_tipo_d)
            df_flags["has_tipo_v"] = df_flags["group_name"].isin(grupos_com_tipo_v)
            df_flags["has_tipo_e"] = df_flags["group_name"].isin(grupos_com_tipo_e)

    excluir = {g.upper() for g in dre.GRUPOS_DRE_CONHECIMENTO}
    df_flags = df_flags[
        ~df_flags["group_name"].astype(str).str.upper().isin(excluir)
    ].copy()

    return df_flags

def get_unique_plates_with_types(apartamento_id: int, tipo_negocio_filter: str = "Todos") -> list:
    """
    Placas classificadas por veiculo.veiculoproprio (cadastro SATI).
    FROTA = S/F; demais = frete/agenciamento. Receita usa conhecimento.tipofrete (DRE).
    Com BI_COD_PROPRIETARIO, lista só veículos do proprietário (veiculo.codproprietario).
    """
    cod_prop = obter_cod_proprietario_filtro(apartamento_id)
    placas_meta: dict[str, dict] = {}
    mapa_veiculos = _mapa_veiculos_sati(apartamento_id, cod_prop)

    for placa, meta in mapa_veiculos.items():
        placas_meta[placa] = {
            "tipo": meta["tipo"],
            "veiculoproprio": meta["veiculoproprio"],
            "incluirateio": meta.get("incluirateio", ""),
        }

    if not mapa_veiculos and sati_enabled_for_apartment(engine, apartamento_id):
        pass
    elif mapa_veiculos:
        # Cadastro SATI já lista as placas — evita carregar relFilViagensCliente inteiro.
        lista_final = [
            {
                "placa": placa,
                "tipo": meta["tipo"],
                "veiculoproprio": meta.get("veiculoproprio", ""),
                "incluirateio": meta.get("incluirateio", ""),
            }
            for placa, meta in placas_meta.items()
        ]
        lista_final = _filtrar_lista_placas_por_tipo_negocio(lista_final, tipo_negocio_filter)
        lista_final.sort(key=lambda x: (x["tipo"], x["placa"]))
        return lista_final

    df_viagens = get_data_as_dataframe("relFilViagensCliente", apartamento_id)
    if cod_prop is not None:
        df_viagens = _filtrar_df_placas_proprietario(df_viagens, apartamento_id, cod_prop)
    if not df_viagens.empty:
        col_map_viagens = _get_case_insensitive_column_map(df_viagens.columns)
        if "placaveiculo" in col_map_viagens:
            col_placa = col_map_viagens["placaveiculo"]
            col_vp = col_map_viagens.get("veiculoproprio")
            for _, row in df_viagens.iterrows():
                placa = row[col_placa]
                if pd.isna(placa) or not str(placa).strip():
                    continue
                placa_limpa = str(placa).strip().upper()
                if placa_limpa in placas_meta:
                    continue
                cad = mapa_veiculos.get(placa_limpa, {})
                codigo = _normalizar_veiculoproprio(row[col_vp]) if col_vp else cad.get("veiculoproprio", "")
                placas_meta[placa_limpa] = {
                    "tipo": _label_tipo_placa_veiculoproprio(codigo),
                    "veiculoproprio": codigo,
                    "incluirateio": cad.get("incluirateio", ""),
                }

    df_despesas = get_data_as_dataframe("relFilDespesasGerais", apartamento_id)
    if cod_prop is not None:
        df_despesas = _filtrar_df_placas_proprietario(
            df_despesas, apartamento_id, cod_prop
        )
    if not df_despesas.empty:
        col_map_despesas = _get_case_insensitive_column_map(df_despesas.columns)
        if "placaveiculo" in col_map_despesas:
            if "veiculoproprio" in col_map_despesas:
                vp_col = col_map_despesas["veiculoproprio"]
                vp = df_despesas[vp_col].astype(str).str.strip().str.upper()
                df_apoio = df_despesas[vp.isin(VEICULOPROPRIO_COD_FROTA)]
                placas_despesa = df_apoio[col_map_despesas["placaveiculo"]].dropna().unique()
            else:
                placas_despesa = df_despesas[col_map_despesas["placaveiculo"]].dropna().unique()

            for placa in placas_despesa:
                if pd.notna(placa) and str(placa).strip():
                    placa_limpa = str(placa).strip().upper()
                    if placa_limpa not in placas_meta:
                        cad = mapa_veiculos.get(placa_limpa, {})
                        codigo = cad.get("veiculoproprio", "F")
                        placas_meta[placa_limpa] = {
                            "tipo": "Apoio/Despesa",
                            "veiculoproprio": codigo,
                            "incluirateio": cad.get("incluirateio", ""),
                        }

    lista_final = [
        {
            "placa": placa,
            "tipo": meta["tipo"],
            "veiculoproprio": meta.get("veiculoproprio", ""),
            "incluirateio": meta.get("incluirateio", ""),
        }
        for placa, meta in placas_meta.items()
    ]
    lista_final = _filtrar_lista_placas_por_tipo_negocio(lista_final, tipo_negocio_filter)
    lista_final.sort(key=lambda x: (x["tipo"], x["placa"]))
    return lista_final

# SUBSTITUA ESTA FUNÇÃO EM data_manager.py

def get_despesas_details_dashboard_data(apartamento_id: int, start_date, end_date, placa_filter, filial_filter, tipo_negocio_filter):
    dashboard_data = {}
    
    filtered_data = _obter_dados_filtrados_mestre(apartamento_id, start_date, end_date, placa_filter, filial_filter, tipo_negocio_filter)
    df_viagens_cliente = filtered_data["df_viagens_cliente"]
    df_despesas_filtrado = filtered_data["df_despesas_filtrado"]
    df_flags = filtered_data["df_flags"]
    df_acerto_motorista_raw = filtered_data["df_acerto_motorista_raw"]
    df_despesas_raw = filtered_data["df_despesas_raw"]

    expense_data = _get_final_expense_dataframes(df_viagens_cliente, df_despesas_filtrado, df_flags, df_acerto_motorista_raw)
    df_custos = expense_data['custos']
    df_despesas_gerais = expense_data['despesas']
    
    # --- CORREÇÃO TIPO D: Ignorar placa no início para buscar custo fixo geral ---
    col_map_desp_raw = _get_case_insensitive_column_map(df_despesas_raw.columns)
    df_despesas_pre = df_despesas_raw.copy()
    if tipo_negocio_filter and tipo_negocio_filter != "Todos":
        df_despesas_pre = _filtrar_despesas_por_tipo_negocio(df_despesas_pre, col_map_desp_raw, tipo_negocio_filter)
        
    df_despesas_sem_placa = apply_filters_to_df(df_despesas_pre, start_date, end_date, "Todos", filial_filter)
    expense_data_sem_placa = _get_final_expense_dataframes(pd.DataFrame(), df_despesas_sem_placa, df_flags, pd.DataFrame())
    df_tipo_d = expense_data_sem_placa['tipo_d']
    
    col_map = _get_case_insensitive_column_map(
        df_despesas_filtrado.columns
        if not df_despesas_filtrado.empty
        else df_despesas_sem_placa.columns
    )

    df_composicao_total = pd.concat([
        _bloco_composicao_despesa(df_custos, "Custo de Viagem"),
        _bloco_composicao_despesa(df_despesas_gerais, "Despesa Geral"),
        _bloco_composicao_despesa(df_tipo_d, "Despesa Tipo D"),
    ], ignore_index=True)

    if not df_composicao_total.empty and df_composicao_total["nomefil"].notna().any():
        df_grouped = df_composicao_total.groupby(["nomefil", "categoria"])["valor_calculado"].sum().unstack(fill_value=0)
        
        if placa_filter and placa_filter != 'Todos':
            if 'Despesa Tipo D' in df_grouped.columns:
                fator = _fator_rateio_placas_proprias(placa_filter, apartamento_id)
                if fator <= 0:
                    df_grouped['Despesa Tipo D'] = 0
                elif fator != 1.0:
                    df_grouped['Despesa Tipo D'] = df_grouped['Despesa Tipo D'] * fator

        if not df_grouped.empty:
            colors = {'Custo de Viagem': 'rgba(230, 126, 34, 0.7)', 'Despesa Geral': 'rgba(231, 76, 60, 0.7)', 'Despesa Tipo D': 'rgba(142, 68, 173, 0.7)'}
            datasets = []
            for categoria in ['Custo de Viagem', 'Despesa Geral', 'Despesa Tipo D']:
                if categoria in df_grouped.columns:
                    datasets.append({'label': categoria, 'data': df_grouped[categoria].tolist(), 'backgroundColor': colors.get(categoria)})
            dashboard_data['despesas_por_filial_e_grupo'] = {'labels': df_grouped.index.tolist(), 'datasets': datasets}

    if 'descgrupod' in col_map and not df_despesas_gerais.empty:
        grupo_df = df_despesas_gerais.groupby(col_map['descgrupod'])['valor_calculado'].sum().nlargest(10).reset_index()
        grupo_df.rename(columns={col_map['descgrupod']: 'descSuperGrupoD', 'valor_calculado': 'vlcontabil'}, inplace=True)
        dashboard_data['despesa_super_grupo'] = grupo_df.to_dict(orient='records')
        
    df_desp_norm = _normalizar_coluna_filial(df_despesas_gerais)
    if not df_desp_norm.empty and 'nomefil' in df_desp_norm.columns:
        filial_df = df_desp_norm.groupby('nomefil')['valor_calculado'].sum().sort_values(ascending=False).reset_index()
        filial_df.rename(columns={'nomefil': 'nomeFil', 'valor_calculado': 'vlcontabil'}, inplace=True)
        dashboard_data['despesa_filial'] = filial_df.to_dict(orient='records')

    df_despesas_completo = pd.concat([
        _normalizar_coluna_filial(df_custos),
        _normalizar_coluna_filial(df_despesas_gerais),
        _normalizar_coluna_filial(df_tipo_d),
    ], ignore_index=True)
    
    def normalize_text(series):
        return series.astype(str).str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8').str.upper()

    if 'descgrupod' in col_map and 'placaveiculo' in col_map:
        df_manutencao = df_despesas_completo[normalize_text(df_despesas_completo[col_map['descgrupod']]).str.contains("MANUTENCAO")]
        if not df_manutencao.empty:
            manutencao_veiculo = df_manutencao.groupby(col_map['placaveiculo'])['valor_calculado'].sum().sort_values(ascending=False).reset_index()
            manutencao_veiculo.rename(columns={'valor_calculado': 'vlcontabil', col_map['placaveiculo']: 'placaVeiculo'}, inplace=True)
            dashboard_data['custo_manutencao_veiculo'] = manutencao_veiculo.to_dict(orient='records')
            
    if 'descgrupod' in col_map and 'descitemd' in col_map:
        df_combustivel = df_despesas_completo[normalize_text(df_despesas_completo[col_map['descgrupod']]).str.contains("COMBUSTIVEL")].copy()
        if not df_combustivel.empty:
            gastos_por_item = df_combustivel.groupby(col_map['descitemd'])['valor_calculado'].sum().sort_values(ascending=False).reset_index()
            gastos_por_item.rename(columns={col_map['descitemd']: 'item', 'valor_calculado': 'valor_total'}, inplace=True)
            dashboard_data['gastos_por_combustivel'] = gastos_por_item.to_dict(orient='records')
    
    if 'descgrupod' in col_map and 'placaveiculo' in col_map:
        df_combustivel_veiculo = df_despesas_completo[normalize_text(df_despesas_completo[col_map['descgrupod']]).str.contains("COMBUSTIVEL")].copy()
        if not df_combustivel_veiculo.empty:
            placa_col = col_map['placaveiculo']
            df_combustivel_veiculo = df_combustivel_veiculo[
                df_combustivel_veiculo[placa_col].notna()
                & (df_combustivel_veiculo[placa_col].astype(str).str.strip() != '')
                & (df_combustivel_veiculo[placa_col].astype(str).str.strip() != '...')
            ]
            if not df_combustivel_veiculo.empty:
                agg_spec = {'valor_total': ('valor_calculado', 'sum')}
                if 'quantidade' in col_map:
                    agg_spec['litros_total'] = (col_map['quantidade'], 'sum')
                combustivel_agg = (
                    df_combustivel_veiculo.groupby(placa_col)
                    .agg(**agg_spec)
                    .sort_values(by='valor_total', ascending=False)
                    .reset_index()
                )
                combustivel_agg.rename(columns={placa_col: 'placaVeiculo'}, inplace=True)
                dashboard_data['combustivel_por_veiculo'] = combustivel_agg.to_dict(orient='records')

    return dashboard_data


def _sati_flag_ok(val) -> bool:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return False
    s = str(val).strip().upper()
    return s in ("S", "1", "T", "SIM", "Y", "TRUE")


def _fluxo_step_done(val) -> bool:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return False
    if isinstance(val, (int, float)) and not pd.isna(val):
        return val != 0
    s = str(val).strip()
    return len(s) > 0 and s.upper() not in ("N", "0", "NAO", "NÃO")


def _ctestatus_autorizado(status) -> bool:
    s = str(status or "").strip().lower()
    return "autor" in s or s in ("100", "135", "autorizado")


def _mdfestatus_autorizado(status) -> bool:
    s = str(status or "").strip().lower()
    return "autor" in s or s in ("100", "135", "autorizado")


def _fluxo_flag_sim(val) -> bool:
    """Campo SATI tipo S/N (ex.: ordemcar.emitida = NFE emitida)."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return False
    s = str(val).strip().upper()
    if s in ("", "N", "0", "NAO", "NÃO", "FALSE", "F"):
        return False
    if s in ("S", "SIM", "1", "Y", "TRUE", "T"):
        return True
    return _fluxo_step_done(val)


def _fluxo_int_or_none(val):
    if not _fluxo_step_done(val):
        return None
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None


def _fluxo_int_flag(val, default: int = 0) -> int:
    """Converte flags 0/1 do SATI/pandas sem falhar em NaN."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return default
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _fluxo_format_mdfe_numero(raw: dict) -> str:
    """Número do MDF-e na tabela manif (não confundir com mdfestatus)."""
    num = raw.get("numeromdfe")
    ser = raw.get("seriemdfe")
    num_s = ""
    ser_s = ""
    if num is not None and not (isinstance(num, float) and pd.isna(num)):
        try:
            num_s = str(int(float(num)))
        except (TypeError, ValueError):
            num_s = str(num).strip()
    if ser is not None and not (isinstance(ser, float) and pd.isna(ser)):
        try:
            ser_s = str(int(float(ser)))
        except (TypeError, ValueError):
            ser_s = str(ser).strip()
    if num_s and ser_s:
        return f"{ser_s}/{num_s}"
    return num_s or ser_s or ""


def _fluxo_resolve_ciot(raw: dict) -> str:
    """CIOT: do CT-e, ou o mesmo número de outro CT-e/manifxml do mesmo manifesto (manif)."""
    return str(raw.get("ciot") or "").strip()


def _fluxo_usa_vale_pedagio(raw: dict) -> bool:
    """Operação com vale-pedágio (tag no CT-e ou valor no manifesto manif)."""
    tp = str(raw.get("tpvalepedagio") or "").strip()
    if tp not in ("", "0", "None", "nan"):
        return True
    return _fluxo_manif_valor_pedagio(raw) > 0


def _fluxo_manif_valor_pedagio(raw: dict) -> float:
    for key in ("manif_valorpedagio", "valorpedagio"):
        try:
            v = raw.get(key)
            if v is None or (isinstance(v, float) and pd.isna(v)):
                continue
            n = float(v)
            if n > 0:
                return n
        except (TypeError, ValueError):
            continue
    return 0.0


def _fluxo_resolve_pedagio_numero(raw: dict) -> str:
    """Nº viagem/tag pedágio (conhecimento, replicado no manif via manifconhecimento)."""
    return str(raw.get("numeropedagio") or "").strip()


def _fluxo_format_pedagio_label(raw: dict, steps_partial: dict | None = None) -> str:
    numero = _fluxo_resolve_pedagio_numero(raw)
    if numero:
        return numero
    valor = _fluxo_manif_valor_pedagio(raw)
    if valor > 0:
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if _fluxo_usa_vale_pedagio(raw):
        if steps_partial and steps_partial.get("mdfe_autorizado"):
            return "Vale pedágio · MDF-e"
        return "Pendente"
    return ""


def _fluxo_pedagio_emitido(raw: dict, steps_partial: dict | None = None) -> bool:
    if _fluxo_step_done(_fluxo_resolve_pedagio_numero(raw)):
        return True
    if _fluxo_manif_valor_pedagio(raw) > 0:
        return True
    if not _fluxo_usa_vale_pedagio(raw):
        return True
    if steps_partial and steps_partial.get("mdfe_autorizado"):
        return True
    return False


def _fluxo_ciot_emitido(raw: dict, steps_partial: dict | None = None) -> bool:
    if _fluxo_step_done(_fluxo_resolve_ciot(raw)):
        return True
    # Viagem já encerrada no SATI sem campo ciot preenchido (comum em agenciamento).
    if steps_partial and steps_partial.get("mdfe_encerrado"):
        if steps_partial.get("cte_autorizado") and steps_partial.get("carga_averbada"):
            return True
    return False


def _fluxo_tem_documento_descarga(raw: dict) -> bool:
    return _fluxo_int_flag(raw.get("tem_documento")) > 0


def _fluxo_format_nome_documento_trilha(nomearq: str | None) -> str:
    """Exibe só o nome do arquivo na etapa Documento da trilha."""
    n = str(nomearq or "").strip().replace("\\", "/")
    if not n:
        return ""
    base = n.split("/")[-1].strip()
    return (base or n)[:48]


def _fluxo_mapa_nomes_documento(
    comprovantes_cache: list, raw: dict
) -> dict[int, str]:
    """Número interno → nomearq (cache do painel ou SATI)."""
    mapa: dict[int, str] = {}
    for c in comprovantes_cache or []:
        n = _fluxo_int_or_none(c.get("numero_conhecimento"))
        na = (c.get("nomearq") or "").strip()
        if n is not None and na:
            mapa[n] = na
    for item in raw.get("documentos_nome_list") or []:
        n = _fluxo_int_or_none(item.get("numero"))
        na = (item.get("nomearq") or "").strip()
        if n is not None and na:
            mapa[n] = na
    ni = _fluxo_int_or_none(raw.get("numero"))
    na = (raw.get("nomearq_descarga_cte") or "").strip()
    if ni is not None and na and ni not in mapa:
        mapa[ni] = na
    return mapa


def _fluxo_nome_documento_descarga(comprovantes_cache: list, raw: dict) -> str:
    """Primeiro nome de documento disponível para exibir na trilha."""
    mapa = _fluxo_mapa_nomes_documento(comprovantes_cache, raw)
    if not mapa:
        return ""
    return next(iter(mapa.values()))


def _fluxo_numeros_coletar_comprovante(
    steps: dict,
    comprovantes_cache: list,
    raw: dict,
    numeros_list: list,
) -> list[int]:
    """
    CT-es que o robô deve buscar: MDF-e ok, nome do documento conhecido na trilha,
    PDF/texto ainda não baixado localmente.
    """
    if not steps.get("mdfe_autorizado"):
        return []
    try:
        from sati_integration.robos.comprovante_descarga import comprovante_completo_no_cache
    except Exception:
        def comprovante_completo_no_cache(_item):
            return False

    cache_by_num = {
        _fluxo_int_or_none(c.get("numero_conhecimento")): c
        for c in (comprovantes_cache or [])
        if _fluxo_int_or_none(c.get("numero_conhecimento")) is not None
    }
    mapa_nome = _fluxo_mapa_nomes_documento(comprovantes_cache, raw)
    nums_alvo = numeros_list or list(mapa_nome.keys())
    resultado: list[int] = []
    for n in nums_alvo:
        ni = _fluxo_int_or_none(n)
        if ni is None:
            continue
        if not mapa_nome.get(ni):
            continue
        if comprovante_completo_no_cache(cache_by_num.get(ni)):
            continue
        resultado.append(ni)
    return sorted(set(resultado))


def _aplicar_cache_comprovantes_painel(apartamento_id: int, raw_rows: list[dict]) -> None:
    """Marca tem_documento e anexa metadados do Painel de Documentos por CT-e."""
    try:
        from sati_integration.robos.comprovante_descarga import mapa_cache_por_numero

        cache_map = mapa_cache_por_numero(apartamento_id)
    except Exception:
        return
    if not cache_map:
        return
    for rec in raw_rows:
        nums = set(rec.get("numeros_list") or [])
        n = _fluxo_int_or_none(rec.get("numero"))
        if n is not None:
            nums.add(n)
        docs = [cache_map[k] for k in nums if k in cache_map]
        if docs:
            rec["tem_documento"] = 1
            rec["comprovantes_cache"] = docs


def _fluxo_linha_status_viagem(
    numero_txt: str,
    steps: dict,
    status_comprovante: str,
) -> str:
    """
    Texto do banner superior — reflete a próxima etapa pendente na trilha.
    Ordem sem número no SATI não prevalece se CT-e/MDF-e já existem.
    """
    num = (numero_txt or "").strip() or "—"

    if not steps.get("ordem_carregamento") and not steps.get("cte_autorizado"):
        return f"{num} · Aguardando ordem de carregamento"

    if not steps.get("cte_autorizado"):
        if not steps.get("nfe_emitida"):
            return f"{num} · Aguardando NFE"
        return f"{num} · Aguardando CT-e"

    if not steps.get("mdfe_autorizado"):
        return f"{num} · Aguardando MDF-e"

    doc_pronto = steps.get("documento_descarga") or status_comprovante == "arquivo_ok"
    if doc_pronto:
        if steps.get("mdfe_encerrado"):
            return f"{num} · MDF-e encerrado"
        return f"{num} · Aguardando encerramento MDF-e"

    rotulos_descarga = {
        "arquivo_ok": f"{num} · Comprov. descarga (arquivo OK)",
        "identificado_banco": f"{num} · Comprov. no banco (buscar arquivo)",
        "identificado_painel": f"{num} · Comprov. listado (buscar arquivo)",
        "pendente_coleta": f"{num} · Aguardando comprovante de descarga",
    }
    if status_comprovante in rotulos_descarga:
        return rotulos_descarga[status_comprovante]

    if steps.get("mdfe_encerrado"):
        return f"{num} · MDF-e encerrado"

    return f"{num} · Aguardando comprovante de descarga"


def _fluxo_linha_descarga(
    numero_txt: str,
    status_comprovante: str,
) -> str:
    """Compatibilidade — preferir _fluxo_linha_status_viagem."""
    num = (numero_txt or "").strip() or "—"
    rotulos = {
        "arquivo_ok": f"{num} · Comprov. descarga (arquivo OK)",
        "identificado_banco": f"{num} · Comprov. no banco (buscar arquivo)",
        "identificado_painel": f"{num} · Comprov. listado (buscar arquivo)",
        "pendente_coleta": f"{num} · Aguardando comprovante de descarga",
        "aguardando_mdfe": f"{num} · Aguardando MDF-e",
    }
    return rotulos.get(status_comprovante, f"{num} · Sem documento de descarga")


def _fluxo_status_comprovante_descarga(
    steps: dict, tem_doc: bool, comprovantes_cache: list, nome_documento: str = ""
) -> str:
    """
    arquivo_ok — PDF/texto já no cache local (robô não precisa ir ao SATI).
    identificado_banco — vínculo no PostgreSQL/SATI com nomearq, sem PDF local.
    identificado_painel — só nomearq no cache do painel, sem PDF.
    pendente_coleta — sem nome de documento na trilha (robô não busca).
    aguardando_mdfe — ainda não na fase de descarga.
    """
    if not steps.get("mdfe_autorizado"):
        return "aguardando_mdfe"
    try:
        from sati_integration.robos.comprovante_descarga import comprovante_completo_no_cache

        if any(comprovante_completo_no_cache(c) for c in (comprovantes_cache or [])):
            return "arquivo_ok"
    except Exception:
        pass
    tem_nome = bool((nome_documento or "").strip()) or any(
        (c.get("nomearq") or "").strip() for c in (comprovantes_cache or [])
    )
    if not tem_nome:
        return "pendente_coleta"
    if any((c.get("nomearq") or "").strip() for c in (comprovantes_cache or [])):
        return "identificado_painel"
    if tem_doc or (nome_documento or "").strip():
        return "identificado_banco"
    return "pendente_coleta"


def _fluxo_precisa_coletar_comprovante(
    steps: dict,
    comprovantes_cache: list,
    raw: dict,
    numeros_list: list,
) -> bool:
    """Robô só busca CT-es com nome do documento na trilha e sem PDF/texto local."""
    return bool(
        _fluxo_numeros_coletar_comprovante(steps, comprovantes_cache, raw, numeros_list)
    )


def coletar_numeros_pendentes_comprovante(rows: list[dict]) -> list[int]:
    """Números internos com nome na trilha e sem PDF local (robô Painel de Documentos)."""
    nums: set[int] = set()
    for row in rows or []:
        for n in row.get("numeros_coleta_comprovante") or []:
            try:
                nums.add(int(n))
            except (TypeError, ValueError):
                pass
    return sorted(nums)


FLUXO_FILTRO_COMPROVANTE_OPCOES = (
    ("todos", "Todas as viagens"),
    ("com_comprovante", "Com comprovante de descarga"),
    ("com_anexo", "Comprovante com anexo (PDF)"),
    ("sem_anexo", "Comprovante sem anexo"),
)

FLUXO_FILTRO_MDFE_OPCOES = (
    ("todos", "Todos os MDF-e"),
    ("encerrado", "MDF-e encerrado"),
    ("nao_encerrado", "MDF-e não encerrado"),
)


def normalizar_filtro_comprovante_fluxo(valor: str | None) -> str:
    chave = (valor or "todos").strip().lower()
    validos = {k for k, _ in FLUXO_FILTRO_COMPROVANTE_OPCOES}
    return chave if chave in validos else "todos"


def _fluxo_row_tem_comprovante_descarga(row: dict) -> bool:
    """Documento de descarga identificado no SATI/painel (com ou sem PDF local)."""
    st = str(row.get("status_comprovante_descarga") or "").strip()
    if st in ("arquivo_ok", "identificado_banco", "identificado_painel"):
        return True
    return bool(row.get("tem_documento_descarga")) or bool(
        (row.get("nome_documento_descarga") or "").strip()
    )


def _fluxo_row_comprovante_com_anexo(row: dict) -> bool:
    return str(row.get("status_comprovante_descarga") or "").strip() == "arquivo_ok"


def _fluxo_row_comprovante_sem_anexo(row: dict) -> bool:
    """Nome do comprovante conhecido, PDF ainda não baixado."""
    return str(row.get("status_comprovante_descarga") or "").strip() in (
        "identificado_banco",
        "identificado_painel",
    )


def filtrar_fluxo_por_comprovante(rows: list[dict], filtro: str | None) -> list[dict]:
    """Filtra linhas da trilha por situação do comprovante de descarga."""
    chave = normalizar_filtro_comprovante_fluxo(filtro)
    if chave == "todos":
        return list(rows or [])
    if chave == "com_comprovante":
        return [r for r in (rows or []) if _fluxo_row_tem_comprovante_descarga(r)]
    if chave == "com_anexo":
        return [r for r in (rows or []) if _fluxo_row_comprovante_com_anexo(r)]
    if chave == "sem_anexo":
        return [r for r in (rows or []) if _fluxo_row_comprovante_sem_anexo(r)]
    return list(rows or [])


def normalizar_filtro_mdfe_fluxo(valor: str | None) -> str:
    chave = (valor or "todos").strip().lower()
    validos = {k for k, _ in FLUXO_FILTRO_MDFE_OPCOES}
    return chave if chave in validos else "todos"


def fluxo_query_string_para_async(args, start_date: str = "", end_date: str = "") -> str:
    """Query string só com parâmetros do fluxo (datas + filtros locais)."""
    from urllib.parse import urlencode

    clean = extrair_query_fluxo(args)
    pairs: list[tuple[str, str]] = []
    for key in clean.keys():
        for val in clean.getlist(key):
            if val is not None and str(val).strip() != "":
                pairs.append((key, str(val).strip()))
    keys = {k for k, _ in pairs}
    if start_date and "start_date" not in keys:
        pairs.append(("start_date", start_date))
    if end_date and "end_date" not in keys:
        pairs.append(("end_date", end_date))
    if "mdfe" not in keys:
        pairs.append(("mdfe", "todos"))
    if "comprovante" not in keys:
        pairs.append(("comprovante", "todos"))
    return urlencode(pairs)


def _raw_tem_mdfe_emitido(raw: dict) -> bool:
    """MDF-e autorizado no manifesto (manif) — viagem entra no fluxo."""
    return _mdfestatus_autorizado(raw.get("mdfestatus")) or _fluxo_step_done(raw.get("mdfeprot"))


def filtrar_fluxo_por_mdfe(rows: list[dict], filtro: str | None) -> list[dict]:
    """Filtra linhas por situação de encerramento do MDF-e."""
    chave = normalizar_filtro_mdfe_fluxo(filtro)
    if chave == "todos":
        return list(rows or [])
    out = []
    for row in rows or []:
        steps = row.get("steps") or {}
        if not steps.get("mdfe_autorizado"):
            continue
        enc = bool(steps.get("mdfe_encerrado"))
        if chave == "encerrado" and enc:
            out.append(row)
        elif chave == "nao_encerrado" and not enc:
            out.append(row)
    return out


def _fluxo_parse_km(val) -> float | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        n = float(val)
    except (TypeError, ValueError):
        return None
    if n < 0 or n > 9_999_999:
        return None
    return n


def _fluxo_fmt_km(val) -> str:
    n = _fluxo_parse_km(val)
    if n is None:
        return ""
    if abs(n - round(n)) < 0.05:
        return f"{int(round(n)):,}".replace(",", ".")
    return f"{n:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fluxo_km_rodado_valor(raw: dict) -> float | None:
    ki = _fluxo_parse_km(raw.get("km_inicial"))
    kf = _fluxo_parse_km(raw.get("km_final"))
    if ki is not None and kf is not None and kf >= ki:
        return kf - ki
    kr = _fluxo_parse_km(raw.get("km_rodado"))
    if kr is not None and kr > 0:
        return kr
    kp = _fluxo_parse_km(raw.get("km_previsto"))
    if kp is not None and kp > 0:
        return kp
    return None


def _fluxo_km_rodado_label(raw: dict) -> str:
    ki = _fluxo_parse_km(raw.get("km_inicial"))
    kf = _fluxo_parse_km(raw.get("km_final"))
    if ki is not None and kf is not None and kf >= ki:
        return f"KM rodado: {_fluxo_fmt_km(kf - ki)}"
    kr = _fluxo_parse_km(raw.get("km_rodado"))
    if kr is not None and kr > 0:
        return f"KM rodado: {_fluxo_fmt_km(kr)}"
    kp = _fluxo_parse_km(raw.get("km_previsto"))
    if kp is not None and kp > 0:
        return f"KM rodado (prev.): {_fluxo_fmt_km(kp)}"
    return ""


def _fluxo_km_manifesto(raw: dict) -> tuple[float | None, float | None, float | None, float | None]:
    """KM ini/fim (agregado), km carregado (fim − ini) e km vazio (kmini − kmfim anterior)."""
    fontes = list(raw.get("ctes_raw_list") or [])
    if not fontes:
        fontes = [raw]
    kmis, kmfs = [], []
    for r in fontes:
        ki = _fluxo_parse_km(r.get("km_inicial"))
        kf = _fluxo_parse_km(r.get("km_final"))
        if ki is not None:
            kmis.append(ki)
        if kf is not None:
            kmfs.append(kf)
    ki = min(kmis) if kmis else _fluxo_parse_km(raw.get("km_inicial"))
    kf = max(kmfs) if kmfs else _fluxo_parse_km(raw.get("km_final"))
    carregado = _fluxo_km_rodado_valor(raw)
    if carregado is None:
        for r in fontes:
            carregado = _fluxo_km_rodado_valor(r)
            if carregado is not None:
                break
    vazios = []
    for r in fontes:
        vv = _fluxo_parse_km(r.get("km_vazio"))
        if vv is not None and vv > 0:
            vazios.append(vv)
    if vazios:
        vazio = float(sum(vazios))
    else:
        vazio = _fluxo_parse_km(raw.get("km_vazio"))
    return ki, kf, carregado, vazio


def _fluxo_cte_contexto(raw: dict) -> dict:
    """Cliente, remetente e rota origem \\ destino para exibição no fluxo."""
    cliente = str(raw.get("nomecliente") or "").strip()
    remetente = str(raw.get("nome_remetente") or "").strip()
    origem = str(raw.get("cidorigemformat") or "").strip()
    destino = str(raw.get("ciddestinoformat") or "").strip()
    rota = ""
    if origem and destino:
        rota = f"{origem} \\ {destino}"
    elif origem:
        rota = origem
    elif destino:
        rota = destino
    partes = []
    if cliente:
        partes.append(f"Cliente: {cliente}")
    if remetente:
        partes.append(f"Remetente: {remetente}")
    if rota:
        partes.append(rota)
    ki = _fluxo_parse_km(raw.get("km_inicial"))
    kf = _fluxo_parse_km(raw.get("km_final"))
    if ki is not None:
        partes.append(f"KM ini.: {_fluxo_fmt_km(ki)}")
    if kf is not None:
        partes.append(f"KM fim: {_fluxo_fmt_km(kf)}")
    rodado_lbl = _fluxo_km_rodado_label(raw)
    if rodado_lbl:
        partes.append(rodado_lbl)
    km_vazio = _fluxo_parse_km(raw.get("km_vazio"))
    if km_vazio is not None and km_vazio > 0:
        partes.append(f"KM vazio: {_fluxo_fmt_km(km_vazio)}")
    rodado = _fluxo_km_rodado_valor(raw)
    return {
        "cliente": cliente,
        "remetente": remetente,
        "origem": origem,
        "destino": destino,
        "rota": rota,
        "linha": " · ".join(partes),
        "km_inicial": ki,
        "km_final": kf,
        "km_rodado": rodado,
        "km_vazio": km_vazio,
    }


def _fluxo_cte_status_label(raw: dict) -> str:
    st = str(raw.get("ctestatus") or "").strip()
    if st and st.lower() not in ("none", "nan"):
        return st
    if _ctestatus_autorizado(st) or _fluxo_step_done(raw.get("ctechave")):
        return "Autorizado"
    prot = str(raw.get("protocolo_cte") or "").strip()
    if prot:
        return "Com protocolo"
    return "Pendente"


def _fluxo_build_cte_detalhe(raw: dict) -> dict:
    nc = _fluxo_int_or_none(raw.get("num_cte"))
    ni = _fluxo_int_or_none(raw.get("numero"))
    auth = (
        _ctestatus_autorizado(str(raw.get("ctestatus") or ""))
        or _fluxo_step_done(raw.get("ctechave"))
        or bool(str(raw.get("protocolo_cte") or "").strip())
    )
    dv_fmt = ""
    dv_raw = raw.get("data_viagem_motorista")
    if dv_raw is not None and not (isinstance(dv_raw, float) and pd.isna(dv_raw)):
        dv = pd.to_datetime(dv_raw, errors="coerce")
        if pd.notna(dv):
            dv_fmt = dv.strftime("%d/%m/%Y")
    return {
        "num_cte": nc,
        "numero": ni,
        "exibicao": _fluxo_format_cte_com_interno([], [], num_cte=nc, numero=ni) or "—",
        "contexto": _fluxo_cte_contexto(raw),
        "status": _fluxo_cte_status_label(raw),
        "autorizado": auth,
        "averbacao": bool(
            _fluxo_step_done(raw.get("protocolo_averbacao"))
            or str(raw.get("protocolo_cte") or "").strip()
        ),
        "data_motorista": dv_fmt,
    }


def _fluxo_format_lista_numeros(valores) -> str:
    nums = []
    for v in valores or []:
        n = _fluxo_int_or_none(v)
        if n is not None:
            nums.append(n)
    if not nums:
        return ""
    return ", ".join(str(n) for n in sorted(set(nums)))


def _fluxo_format_cte_com_interno(
    ctes_list: list,
    numeros_list: list,
    *,
    num_cte=None,
    numero=None,
    pares: list | None = None,
) -> str:
    """
    CT-e fiscal \\ número interno (conhecimento.numero).
    Ex.: 23346 \\ 7965
    """
    linhas: list[str] = []
    if pares:
        for item in pares:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                fiscal, interno = item[0], item[1]
            elif isinstance(item, dict):
                fiscal = item.get("num_cte") or item.get("fiscal")
                interno = item.get("numero") or item.get("interno")
            else:
                continue
            f = _fluxo_int_or_none(fiscal)
            if f is None:
                continue
            i = _fluxo_int_or_none(interno)
            if i is not None:
                linhas.append(f"{f} \\ {i}")
            else:
                linhas.append(str(f))
    elif num_cte is not None or numero is not None or (ctes_list and numeros_list and len(ctes_list) == 1 and len(numeros_list) == 1):
        f = _fluxo_int_or_none(num_cte) or (_fluxo_int_or_none(ctes_list[0]) if ctes_list else None)
        i = _fluxo_int_or_none(numero) or (_fluxo_int_or_none(numeros_list[0]) if numeros_list else None)
        if f is not None:
            if i is not None:
                linhas.append(f"{f} \\ {i}")
            else:
                linhas.append(str(f))
    elif ctes_list:
        linhas.append(_fluxo_format_lista_numeros(ctes_list))
    # deduplica mantendo ordem
    vistos: set[str] = set()
    unicos = []
    for ln in linhas:
        if ln not in vistos:
            vistos.add(ln)
            unicos.append(ln)
    return ", ".join(unicos)


def _fluxo_build_cte_subtrack(raw: dict) -> dict:
    """Trilha compacta por CT-e (ordem → NFE → CT-e → averbação)."""
    num_ordem = _fluxo_int_or_none(raw.get("num_ordem"))
    cod_ordem = _fluxo_int_or_none(raw.get("codordemcar"))
    num_cte = _fluxo_int_or_none(raw.get("num_cte"))
    n_raw = _fluxo_int_or_none(raw.get("numero"))
    ctestatus_raw = str(raw.get("ctestatus") or "").strip()
    protocolo_cte = str(raw.get("protocolo_cte") or "").strip()
    tem_ordem = num_ordem is not None or cod_ordem is not None
    cte_autorizado = (
        _ctestatus_autorizado(ctestatus_raw)
        or _fluxo_step_done(raw.get("ctechave"))
        or bool(protocolo_cte)
    )
    nfe_ok = (
        _fluxo_flag_sim(raw.get("nfe_emitida"))
        or _fluxo_flag_sim(raw.get("nfe_notaxml_ok"))
        or bool(str(raw.get("nfe_numero_notaxml") or "").strip())
    )
    nfe_num = str(raw.get("nfe_numero_notaxml") or "").strip()
    if nfe_ok and nfe_num:
        nfe_label = nfe_num
    elif nfe_ok:
        nfe_label = "Emitida"
    else:
        nfe_label = "—"
    steps = {
        "ordem_carregamento": tem_ordem,
        "nfe_emitida": nfe_ok,
        "cte_autorizado": cte_autorizado,
        "carga_averbada": _fluxo_step_done(raw.get("protocolo_averbacao")) or bool(protocolo_cte),
    }
    titulo = _fluxo_format_cte_com_interno([], [], num_cte=num_cte, numero=n_raw) or "CT-e"
    ordem_txt = str(num_ordem) if num_ordem is not None else (str(cod_ordem) if cod_ordem else "")
    data_mot = ""
    dv_raw = raw.get("data_viagem_motorista")
    if dv_raw is not None and not (isinstance(dv_raw, float) and pd.isna(dv_raw)):
        dv = pd.to_datetime(dv_raw, errors="coerce")
        if pd.notna(dv):
            data_mot = dv.strftime("%d/%m/%Y")
    labels = {
        "ordem": ordem_txt,
        "nfe": nfe_label,
        "cte": titulo,
        "cte_status": ctestatus_raw or ("Autorizado" if cte_autorizado else "Pendente"),
        "averbacao": str(raw.get("protocolo_averbacao") or protocolo_cte or "").strip(),
        "data_viagem_motorista": data_mot,
    }
    comprovantes_cte = list(raw.get("comprovantes_cache") or [])
    tem_doc_banco = _fluxo_tem_documento_descarga(raw)
    nome_documento = _fluxo_nome_documento_descarga(comprovantes_cte, raw)
    if cte_autorizado:
        status_comprovante = _fluxo_status_comprovante_descarga(
            {"mdfe_autorizado": True},
            tem_doc_banco,
            comprovantes_cte,
            nome_documento,
        )
    else:
        status_comprovante = "aguardando_cte"
    steps["documento_descarga"] = status_comprovante == "arquivo_ok"
    detalhe_descarga = "—"
    if status_comprovante == "arquivo_ok":
        detalhe_descarga = "Arquivo OK"
        for c in comprovantes_cte:
            nt = _fluxo_format_nome_documento_trilha(c.get("nomearq"))
            if nt:
                detalhe_descarga = nt
                break
        if detalhe_descarga == "Arquivo OK":
            nome_trilha = _fluxo_format_nome_documento_trilha(nome_documento)
            if nome_trilha:
                detalhe_descarga = nome_trilha
    elif status_comprovante in ("identificado_banco", "identificado_painel"):
        detalhe_descarga = _fluxo_format_nome_documento_trilha(nome_documento) or "Identificado"
    elif status_comprovante == "pendente_coleta":
        detalhe_descarga = "Pendente"
    labels["documento_descarga"] = detalhe_descarga
    doc_numeros = [n_raw] if n_raw is not None else []
    contexto = _fluxo_cte_contexto(raw)
    return {
        "titulo": titulo,
        "contexto": contexto,
        "numero": n_raw,
        "doc_numeros": doc_numeros,
        "steps": steps,
        "flux_anim": _build_flux_cte_subtrack_anim(steps, labels),
    }


def _flux_truck_index_for_keys(steps: dict, keys: tuple) -> int:
    n = len(keys)
    furthest_done = -1
    first_pending = n
    for i, key in enumerate(keys):
        if steps.get(key):
            furthest_done = i
        elif first_pending == n:
            first_pending = i
    if furthest_done < 0:
        return 0
    if furthest_done > 0:
        return furthest_done
    return first_pending if first_pending < n else furthest_done


_CTE_SUBTRACK_KEYS = (
    "ordem_carregamento",
    "nfe_emitida",
    "cte_autorizado",
    "carga_averbada",
    "documento_descarga",
)

_MDFE_TRACK_KEYS = (
    "ciot_emitido",
    "pedagio_emitido",
    "mdfe_autorizado",
    "mdfe_encerrado",
)


def _build_flux_cte_subtrack_anim(steps: dict, labels: dict) -> dict:
    tem_ordem = bool(steps.get("ordem_carregamento"))

    def node_state(key: str) -> str:
        return "done" if steps.get(key) else "pending"

    pipeline = [
        {
            "id": "ordem_carregamento",
            "label": "Ordem",
            "short": "Ordem",
            "state": "done" if tem_ordem else "alert",
            "dual_status": True,
            "sem_ordem": not tem_ordem,
            "ordem_emitida": tem_ordem,
            "detail": labels.get("ordem") or "",
        },
        {
            "id": "nfe_emitida",
            "label": "NFE",
            "short": "NFE",
            "state": node_state("nfe_emitida"),
            "detail": labels.get("nfe") or ("OK" if steps.get("nfe_emitida") else "—"),
        },
        {
            "id": "cte_autorizado",
            "label": "CT-e",
            "short": "CT-e",
            "state": node_state("cte_autorizado"),
            "detail": labels.get("cte_status") or "—",
            "detail_sub": labels.get("data_viagem_motorista") or "",
        },
        {
            "id": "carga_averbada",
            "label": "Averbação",
            "short": "Averb.",
            "state": node_state("carga_averbada"),
            "detail": labels.get("averbacao") or "—",
        },
        {
            "id": "documento_descarga",
            "label": "Comprovante de descarga",
            "short": "Descarga",
            "state": node_state("documento_descarga"),
            "detail": labels.get("documento_descarga") or "",
            "clickable": True,
            "icon": "📄",
        },
    ]
    n = len(pipeline)
    truck_index = _flux_truck_index_for_keys(steps, _CTE_SUBTRACK_KEYS)
    return {
        "stages": pipeline,
        "truck_index": truck_index,
        "truck_percent": round((truck_index / max(n - 1, 1)) * 100, 2),
        "tem_ordem": tem_ordem,
        "tem_cte": bool(steps.get("cte_autorizado")),
        "truck_on_top": False,
        # Só "dispensa" visual quando CT-e já saiu e a NFE ainda não foi vinculada
        "pula_nfe": tem_ordem and bool(steps.get("cte_autorizado")) and not nfe_ok,
        "mdfe_encerrado": False,
        "mdfe_autorizado": False,
        "is_subtrack": True,
    }


def _build_flux_mdfe_track_anim(steps: dict, labels: dict) -> dict:
    """Trilha do manifesto: CIOT → pedágio → MDF-e → encerramento."""
    mdfe_encerrado = bool(steps.get("mdfe_encerrado"))

    def node_state(key: str) -> str:
        return "done" if steps.get(key) else "pending"

    pipeline = [
        {
            "id": "ciot_emitido",
            "label": "CIOT emitido",
            "short": "CIOT",
            "state": node_state("ciot_emitido"),
            "detail": labels.get("ciot") or "",
        },
        {
            "id": "pedagio_emitido",
            "label": "Pedágio emitido",
            "short": "Pedágio",
            "state": node_state("pedagio_emitido"),
            "detail": labels.get("pedagio") or "",
        },
        {
            "id": "mdfe_autorizado",
            "label": "MDF-e autorizado",
            "short": "MDF-e",
            "state": node_state("mdfe_autorizado"),
            "detail": labels.get("mdfe_numero") or labels.get("mdfe_status") or "",
        },
        {
            "id": "mdfe_encerrado",
            "label": "MDF-e encerrado",
            "short": "Encerr.",
            "state": node_state("mdfe_encerrado"),
            "detail": labels.get("mdfe_enc") or "",
        },
    ]
    n = len(pipeline)
    truck_index = _flux_truck_index_for_keys(steps, _MDFE_TRACK_KEYS)
    return {
        "stages": pipeline,
        "truck_index": truck_index,
        "truck_percent": round((truck_index / max(n - 1, 1)) * 100, 2),
        "tem_ordem": True,
        "tem_nfe": True,
        "tem_cte": True,
        "mdfe_encerrado": mdfe_encerrado,
        "mdfe_autorizado": bool(steps.get("mdfe_autorizado")),
        "truck_on_top": bool(steps.get("mdfe_autorizado")),
        "pula_nfe": False,
        "is_mdfe_track": True,
    }


def _fluxo_group_key(raw: dict) -> tuple:
    """Uma linha do painel = um MDF-e (manif). CT-es sem manifesto ficam em bucket solo."""
    cm = raw.get("codmanif")
    if cm is not None and not (isinstance(cm, float) and pd.isna(cm)):
        try:
            return ("manif", int(cm))
        except (TypeError, ValueError):
            pass
    placa = str(raw.get("placa") or "").strip().upper()
    numero = _fluxo_int_or_none(raw.get("numero")) or 0
    return ("solo", placa, numero)


def _merge_raw_fluxo_viagem(group: list[dict]) -> dict:
    """Uma viagem (manifesto) com vários CT-es → um único registro agregado."""
    group = sorted(group, key=lambda r: str(r.get("emissao") or ""), reverse=True)
    base = dict(group[0])
    ordens, ctes, numeros, codordens = [], [], [], set()
    pares_cte: list[tuple[int | None, int | None]] = []
    ctes_detalhe: list[dict] = []
    ctes_raw_list: list[dict] = []
    vistos_cte: set[tuple] = set()
    any_cte_auth = False
    any_cte_chave = False
    any_averb = False
    any_nfe = False

    for r in group:
        no = _fluxo_int_or_none(r.get("num_ordem"))
        if no is not None:
            ordens.append(no)
        co = _fluxo_int_or_none(r.get("codordemcar"))
        if co is not None:
            codordens.add(co)
        nc = _fluxo_int_or_none(r.get("num_cte"))
        if nc is not None:
            ctes.append(nc)
        n_doc = _fluxo_int_or_none(r.get("numero"))
        if n_doc is not None:
            numeros.append(n_doc)
        if nc is not None or n_doc is not None:
            pares_cte.append((nc, n_doc))
            cte_key = (nc, n_doc)
            if cte_key not in vistos_cte:
                vistos_cte.add(cte_key)
                ctes_detalhe.append(_fluxo_build_cte_detalhe(r))
                ctes_raw_list.append(dict(r))
        if _ctestatus_autorizado(str(r.get("ctestatus") or "")) or _fluxo_step_done(r.get("ctechave")):
            any_cte_auth = True
        if _fluxo_step_done(r.get("ctechave")):
            any_cte_chave = True
        if _fluxo_step_done(r.get("protocolo_averbacao")) or _fluxo_step_done(r.get("protocolo_cte")):
            any_averb = True
        if _fluxo_flag_sim(r.get("nfe_emitida")):
            any_nfe = True
        tp = str(r.get("tpvalepedagio") or "").strip()
        if tp not in ("", "0", "None", "nan"):
            base["tpvalepedagio"] = r.get("tpvalepedagio")
        np = str(r.get("numeropedagio") or "").strip()
        if np and not str(base.get("numeropedagio") or "").strip():
            base["numeropedagio"] = r.get("numeropedagio")
        try:
            vp = float(r.get("manif_valorpedagio") or 0)
            if vp > float(base.get("manif_valorpedagio") or 0):
                base["manif_valorpedagio"] = r.get("manif_valorpedagio")
        except (TypeError, ValueError):
            pass
        if _fluxo_int_flag(r.get("tem_documento")) > 0:
            base["tem_documento"] = 1

    base_num = _fluxo_int_or_none(base.get("numero"))
    for r in group:
        if _fluxo_int_or_none(r.get("numero")) != base_num:
            continue
        dv = r.get("data_viagem_motorista")
        if dv is not None and not (isinstance(dv, float) and pd.isna(dv)):
            base["data_viagem_motorista"] = dv
        break

    docs_nome_list: list[dict] = []
    for r in group:
        ni = _fluxo_int_or_none(r.get("numero"))
        na = (r.get("nomearq_descarga_cte") or "").strip()
        if ni is not None and na:
            docs_nome_list.append({"numero": ni, "nomearq": na})
    base["documentos_nome_list"] = docs_nome_list
    if docs_nome_list and not (base.get("nomearq_descarga_cte") or "").strip():
        base["nomearq_descarga_cte"] = docs_nome_list[0]["nomearq"]

    base["ordens_list"] = sorted(set(ordens))
    base["ctes_list"] = sorted(set(ctes))
    base["codordens_list"] = sorted(codordens)
    base["numeros_list"] = numeros
    base["ctes_pares_list"] = pares_cte
    base["ctes_detalhe_list"] = sorted(
        ctes_detalhe,
        key=lambda x: (x.get("num_cte") or 0, x.get("numero") or 0),
    )
    base["ctes_raw_list"] = ctes_raw_list
    base["qtd_ctes_manifesto"] = len(base["ctes_list"]) or len(ctes_detalhe) or len(group)
    if any_cte_auth:
        base["ctestatus"] = base.get("ctestatus") or "AUTORIZADO"
    if any_cte_chave and not base.get("ctechave"):
        for r in group:
            if _fluxo_step_done(r.get("ctechave")):
                base["ctechave"] = r.get("ctechave")
                break
    if any_averb and not _fluxo_step_done(base.get("protocolo_averbacao")):
        for r in group:
            if _fluxo_step_done(r.get("protocolo_averbacao")):
                base["protocolo_averbacao"] = r.get("protocolo_averbacao")
                break
    if any_nfe:
        base["nfe_emitida"] = "S"
    return base


def _agrupar_fluxo_por_viagem(
    records: list[dict],
    *,
    somente_com_mdfe_emitido: bool = False,
) -> list[dict]:
    """Agrupa linhas do SATI: uma linha do painel por MDF-e (manif)."""
    from collections import defaultdict

    buckets: dict[tuple, list[dict]] = defaultdict(list)
    for rec in records:
        buckets[_fluxo_group_key(rec)].append(rec)
    merged = [_merge_raw_fluxo_viagem(g) for g in buckets.values()]
    if somente_com_mdfe_emitido:
        merged = [m for m in merged if _raw_tem_mdfe_emitido(m)]
    merged.sort(key=lambda r: str(r.get("emissao") or ""), reverse=True)
    return merged


def _build_fluxo_row(raw: dict) -> dict:
    ordens_list = list(raw.get("ordens_list") or [])
    ctes_list = list(raw.get("ctes_list") or [])
    numeros_list = list(raw.get("numeros_list") or [])
    num_ordem = _fluxo_int_or_none(raw.get("num_ordem"))
    cod_ordem = _fluxo_int_or_none(raw.get("codordemcar"))
    num_cte = _fluxo_int_or_none(raw.get("num_cte"))
    if num_ordem is not None and num_ordem not in ordens_list:
        ordens_list.append(num_ordem)
    if num_cte is not None and num_cte not in ctes_list:
        ctes_list.append(num_cte)
    n_raw = _fluxo_int_or_none(raw.get("numero"))
    if n_raw is not None and n_raw not in numeros_list:
        numeros_list.append(n_raw)
    ordens_list = sorted(set(ordens_list))
    ctes_list = sorted(set(ctes_list))
    ctestatus_raw = str(raw.get("ctestatus") or "").strip()
    protocolo_cte = str(raw.get("protocolo_cte") or "").strip()
    cte_autorizado = (
        _ctestatus_autorizado(ctestatus_raw)
        or _fluxo_step_done(raw.get("ctechave"))
        or bool(protocolo_cte)
    )

    ciot_valor = _fluxo_resolve_ciot(raw)
    codordens_list = list(raw.get("codordens_list") or [])
    if cod_ordem is not None and cod_ordem not in codordens_list:
        codordens_list.append(cod_ordem)
    tem_ordem_viagem = bool(ordens_list) or bool(codordens_list) or cod_ordem is not None
    cod_manif = raw.get("codmanif")
    if cod_manif is not None and isinstance(cod_manif, float) and pd.isna(cod_manif):
        cod_manif = None
    elif cod_manif is not None:
        try:
            cod_manif = int(cod_manif)
        except (TypeError, ValueError):
            cod_manif = None

    comprovantes_cache = list(raw.get("comprovantes_cache") or [])
    tem_doc_banco = _fluxo_tem_documento_descarga(raw)
    nome_documento = _fluxo_nome_documento_descarga(comprovantes_cache, raw)

    steps = {
        "ordem_carregamento": tem_ordem_viagem,
        "nfe_emitida": _fluxo_flag_sim(raw.get("nfe_emitida")),
        "cte_autorizado": cte_autorizado,
        "carga_averbada": _fluxo_step_done(raw.get("protocolo_averbacao")) or bool(protocolo_cte),
        "mdfe_autorizado": _mdfestatus_autorizado(raw.get("mdfestatus")) or _fluxo_step_done(raw.get("mdfeprot")),
        "documento_descarga": False,
        "mdfe_encerrado": (
            _fluxo_step_done(raw.get("mdfe_prot_encerramento"))
            or _fluxo_step_done(raw.get("mdfe_data_finalizacao"))
        ),
    }
    steps["ciot_emitido"] = _fluxo_ciot_emitido(raw, steps)
    steps["pedagio_emitido"] = _fluxo_pedagio_emitido(raw, steps)
    pedagio_valor = _fluxo_format_pedagio_label(raw, steps)

    status_comprovante = _fluxo_status_comprovante_descarga(
        steps, tem_doc_banco, comprovantes_cache, nome_documento
    )
    steps["documento_descarga"] = status_comprovante == "arquivo_ok"
    tem_doc = status_comprovante == "arquivo_ok" or tem_doc_banco

    mdfe_numero = _fluxo_format_mdfe_numero(raw)

    ordem_txt = _fluxo_format_lista_numeros(ordens_list)
    if not ordem_txt and codordens_list:
        ordem_txt = ", ".join(str(c) for c in codordens_list)
    elif not ordem_txt and cod_ordem is not None:
        ordem_txt = str(cod_ordem)
    cte_txt = _fluxo_format_cte_com_interno(
        ctes_list,
        numeros_list,
        num_cte=num_cte,
        numero=n_raw,
        pares=raw.get("ctes_pares_list"),
    )

    detalhe_descarga = {
        "arquivo_ok": "Arquivo OK",
        "identificado_banco": "No banco · buscar PDF",
        "identificado_painel": "Listado · buscar PDF",
        "pendente_coleta": "—",
        "aguardando_mdfe": "—",
    }.get(status_comprovante, "—")
    nome_trilha = _fluxo_format_nome_documento_trilha(nome_documento)
    if status_comprovante == "arquivo_ok" and comprovantes_cache:
        for c in comprovantes_cache:
            nt = _fluxo_format_nome_documento_trilha(c.get("nomearq"))
            if nt:
                detalhe_descarga = nt
                break
        if detalhe_descarga == "Arquivo OK" and nome_trilha:
            detalhe_descarga = nome_trilha
    elif nome_trilha and status_comprovante in (
        "identificado_banco",
        "identificado_painel",
    ):
        detalhe_descarga = nome_trilha

    emissao = raw.get("emissao")
    emissao_fmt = pd.NaT
    if emissao is not None and not (isinstance(emissao, float) and pd.isna(emissao)):
        emissao_fmt = pd.to_datetime(emissao, errors="coerce")
        emissao_str = emissao_fmt.strftime("%d/%m/%Y %H:%M") if pd.notna(emissao_fmt) else "—"
        data_dia = emissao_fmt.strftime("%d/%m/%Y") if pd.notna(emissao_fmt) else "—"
        data_dia_iso = emissao_fmt.strftime("%Y-%m-%d") if pd.notna(emissao_fmt) else ""
    else:
        emissao_str = "—"
        data_dia = "—"
        data_dia_iso = ""

    data_viagem_motorista_fmt = ""
    data_viagem_motorista_trilha = ""
    dv_fmt = pd.NaT
    tem_cte = bool(cte_autorizado or ctes_list or num_cte is not None)
    if tem_cte:
        dv_raw = raw.get("data_viagem_motorista")
        if dv_raw is not None and not (isinstance(dv_raw, float) and pd.isna(dv_raw)):
            dv_fmt = pd.to_datetime(dv_raw, errors="coerce")
            if pd.notna(dv_fmt):
                data_viagem_motorista_fmt = dv_fmt.strftime("%d/%m/%Y %H:%M")
                data_viagem_motorista_trilha = dv_fmt.strftime("%d/%m/%Y")
                data_dia = dv_fmt.strftime("%d/%m/%Y")
                data_dia_iso = dv_fmt.strftime("%Y-%m-%d")

    # Preenchido depois por placa: data motorista do CT-e emitido anterior
    ultima_movimentacao_fmt = ""
    ultima_movimentacao_ts = pd.NaT

    labels = {
        "ordem": ordem_txt,
        "cte": cte_txt,
        "cte_status": ctestatus_raw or "—",
        "ctes_nested": list(raw.get("ctes_detalhe_list") or []),
        "protocolo_cte": protocolo_cte,
        "averbacao": str(raw.get("protocolo_averbacao") or "").strip(),
        "ciot": ciot_valor or (
            "Encerrado (sem nº CIOT no SATI)" if steps.get("ciot_emitido") and not ciot_valor else ""
        ),
        "pedagio": pedagio_valor,
        "mdfe_status": mdfe_numero or str(raw.get("mdfestatus") or "").strip() or "—",
        "mdfe_numero": mdfe_numero,
        "mdfe_enc": str(raw.get("mdfe_prot_encerramento") or "").strip(),
        "documento_descarga": detalhe_descarga,
        "data_viagem_motorista": data_viagem_motorista_trilha,
    }

    if not labels["ctes_nested"] and (num_cte is not None or n_raw is not None):
        labels["ctes_nested"] = [_fluxo_build_cte_detalhe(raw)]

    ctes_trilhas = [_fluxo_build_cte_subtrack(r) for r in (raw.get("ctes_raw_list") or [])]
    if not ctes_trilhas:
        ctes_trilhas = [_fluxo_build_cte_subtrack(raw)]

    progresso_total = len(steps)
    concluidos = sum(1 for v in steps.values() if v)

    flux_anim = _build_flux_mdfe_track_anim(steps, labels)

    mdfe_lbl = labels.get("mdfe_numero") or labels.get("mdfe_status") or ""
    if ordem_txt and not mdfe_lbl and not cte_txt:
        numero_exibicao = ordem_txt.split(",")[0].strip()
    elif mdfe_lbl and mdfe_lbl != "—":
        numero_exibicao = mdfe_lbl
    elif cte_txt:
        numero_exibicao = cte_txt.split(",")[0].strip()
    elif ordem_txt:
        numero_exibicao = ordem_txt.split(",")[0].strip()
    elif cod_manif:
        numero_exibicao = str(cod_manif)
    else:
        numero_exibicao = "—"

    numeros_internos_fluxo = sorted(
        set(numeros_list)
        | {n for n in [_fluxo_int_or_none(raw.get("numero"))] if n is not None}
    )
    numeros_coleta = _fluxo_numeros_coletar_comprovante(
        steps, comprovantes_cache, raw, numeros_internos_fluxo
    )
    precisa_coletar = bool(numeros_coleta)
    linha_descarga = _fluxo_linha_status_viagem(
        numero_exibicao, steps, status_comprovante
    )

    _, _, km_carregado, km_vazio = _fluxo_km_manifesto(raw)
    km_carregado_fmt = _fluxo_fmt_km(km_carregado) if km_carregado is not None else ""
    if not km_carregado_fmt:
        kp = _fluxo_parse_km(raw.get("km_previsto"))
        if kp is not None and kp > 0:
            km_carregado_fmt = f"{_fluxo_fmt_km(kp)} (prev.)"
    km_vazio_fmt = _fluxo_fmt_km(km_vazio) if km_vazio is not None and km_vazio > 0 else ""

    return {
        "placa": str(raw.get("placa") or "—").strip().upper() or "—",
        "motorista": str(raw.get("motorista") or "—").strip() or "—",
        "emissao": emissao_str,
        "ultima_movimentacao_fmt": ultima_movimentacao_fmt,
        "data_viagem_motorista_fmt": data_viagem_motorista_fmt,
        "data_viagem_motorista_ts": dv_fmt.isoformat() if pd.notna(dv_fmt) else "",
        "data_dia": data_dia,
        "data_dia_iso": data_dia_iso,
        "emissao_ts": emissao_fmt.isoformat() if pd.notna(emissao_fmt) else "",
        "ultima_movimentacao_ts": (
            ultima_movimentacao_ts.isoformat() if pd.notna(ultima_movimentacao_ts) else ""
        ),
        "num_ordem": ordens_list[0] if ordens_list else num_ordem,
        "num_cte": ctes_list[0] if ctes_list else num_cte,
        "numero": numeros_list[0] if numeros_list else raw.get("numero"),
        "codmanif": cod_manif,
        "qtd_ctes": len(ctes_list),
        "lista_ordens": ordens_list,
        "lista_ctes": ctes_list,
        "lista_ctes_detalhe": labels["ctes_nested"],
        "ctes_trilhas": ctes_trilhas,
        "lista_numeros": numeros_list,
        "numero_exibicao": numero_exibicao,
        "linha_descarga": linha_descarga,
        "km_carregado_fmt": km_carregado_fmt,
        "km_vazio_fmt": km_vazio_fmt,
        "tem_documento_descarga": steps["documento_descarga"],
        "precisa_coletar_comprovante": precisa_coletar,
        "status_comprovante_descarga": status_comprovante,
        "nome_documento_descarga": nome_documento,
        "comprovantes_descarga": comprovantes_cache,
        "numeros_internos_fluxo": numeros_internos_fluxo,
        "numeros_coleta_comprovante": numeros_coleta,
        "steps": steps,
        "labels": labels,
        "flux_anim": flux_anim,
        "progresso": concluidos,
        "progresso_total": progresso_total,
    }


_FLUX_STAGE_KEYS = (
    "ordem_carregamento",
    "nfe_emitida",
    "cte_autorizado",
    "carga_averbada",
    "ciot_emitido",
    "pedagio_emitido",
    "mdfe_autorizado",
    "documento_descarga",
    "mdfe_encerrado",
)


def _flux_truck_index(steps: dict, n: int) -> int:
    """Posição do caminhão = maior etapa concluída; ordem sem nº no SATI não trava se CT-e já existe."""
    keys = _FLUX_STAGE_KEYS
    furthest_done = -1
    first_pending = n
    for i, key in enumerate(keys):
        if steps.get(key):
            furthest_done = i
        elif first_pending == n:
            first_pending = i

    if furthest_done < 0:
        return 0

    if steps.get("mdfe_encerrado"):
        return keys.index("mdfe_encerrado")

    if steps.get("mdfe_autorizado"):
        doc_idx = keys.index("documento_descarga")
        enc_idx = keys.index("mdfe_encerrado")
        if not steps.get("documento_descarga"):
            return doc_idx
        if not steps.get("mdfe_encerrado"):
            return enc_idx
        return enc_idx

    # CT-e emitido: avança até a última etapa concluída (ex.: ordem só com codordemcar, sem oc.numero)
    if steps.get("cte_autorizado") and furthest_done > 0:
        return furthest_done

    return first_pending if first_pending < n else furthest_done


def _build_flux_anim(steps: dict, labels: dict) -> dict:
    """Trilha L→R: 1ª etapa com Sem ordem/Ordem emitida; NFE; caminhão em cima se MDF-e encerrado."""
    tem_ordem = bool(steps.get("ordem_carregamento"))
    tem_nfe = bool(steps.get("nfe_emitida"))
    tem_cte = bool(steps.get("cte_autorizado"))
    mdfe_encerrado = bool(steps.get("mdfe_encerrado"))

    def node_state(key: str) -> str:
        return "done" if steps.get(key) else "pending"

    pipeline = [
        {
            "id": "ordem_carregamento",
            "label": "Ordem de carregamento",
            "short": "Ordem carg.",
            "state": "done" if tem_ordem else "alert",
            "dual_status": True,
            "sem_ordem": not tem_ordem,
            "ordem_emitida": tem_ordem,
            "detail": labels.get("ordem") or "",
        },
        {
            "id": "nfe_emitida",
            "label": "NFE emitida",
            "short": "NFE emitida",
            "state": node_state("nfe_emitida"),
            "detail": "Emitida" if tem_nfe else "Pendente",
        },
        {
            "id": "cte_autorizado",
            "label": "CT-es do MDF-e",
            "short": "CT-es",
            "state": node_state("cte_autorizado"),
            "detail": labels.get("cte") or "—",
            "detail_sub": (
                f"{len(labels.get('ctes_nested') or [])} CT-e(s) no manifesto"
                if len(labels.get("ctes_nested") or []) > 1
                else (labels.get("cte_status") or "")
            ),
            "detail_data_motorista": labels.get("data_viagem_motorista") or "",
            "ctes_nested": labels.get("ctes_nested") or [],
        },
        {
            "id": "carga_averbada",
            "label": "Carga averbada",
            "short": "Averb.",
            "state": node_state("carga_averbada"),
            "detail": labels.get("protocolo_cte") or labels.get("averbacao") or "",
        },
        {
            "id": "ciot_emitido",
            "label": "CIOT emitido",
            "short": "CIOT",
            "state": node_state("ciot_emitido"),
            "detail": labels.get("ciot") or "",
        },
        {
            "id": "pedagio_emitido",
            "label": "Pedágio emitido",
            "short": "Pedágio",
            "state": node_state("pedagio_emitido"),
            "detail": labels.get("pedagio") or "",
        },
        {
            "id": "mdfe_autorizado",
            "label": "MDF-e autorizado",
            "short": "MDF-e",
            "state": node_state("mdfe_autorizado"),
            "detail": labels.get("mdfe_numero") or labels.get("mdfe_status") or "",
        },
        {
            "id": "documento_descarga",
            "label": "Comprovante de descarga",
            "short": "Descarga",
            "state": node_state("documento_descarga"),
            "detail": labels.get("documento_descarga") or "",
            "clickable": True,
            "icon": "📄",
        },
        {
            "id": "mdfe_encerrado",
            "label": "MDF-e encerrado",
            "short": "Encerr.",
            "state": node_state("mdfe_encerrado"),
            "detail": labels.get("mdfe_enc") or "",
        },
    ]

    n = len(pipeline)
    truck_index = _flux_truck_index(steps, n)
    truck_percent = (truck_index / max(n - 1, 1)) * 100

    return {
        "stages": pipeline,
        "truck_index": truck_index,
        "truck_percent": round(truck_percent, 2),
        "tem_ordem": tem_ordem,
        "tem_nfe": tem_nfe,
        "tem_cte": tem_cte,
        "mdfe_encerrado": mdfe_encerrado,
        "mdfe_autorizado": bool(steps.get("mdfe_autorizado")),
        "truck_on_top": bool(steps.get("mdfe_autorizado")),
        "pula_nfe": tem_ordem and tem_cte,
    }


_fluxo_sati_cache: dict[tuple, tuple] = {}
_FLUXO_CACHE_TTL_SEC = 90


def _fluxo_cache_key(apartamento_id: int, start_date, end_date, cod_filial) -> tuple:
    def _fmt(d):
        if d is None:
            return ""
        return d.strftime("%Y-%m-%d %H:%M:%S") if hasattr(d, "strftime") else str(d)

    return (apartamento_id, _fmt(start_date), _fmt(end_date), cod_filial, 5)


def _fluxo_sql_coluna_ausente(exc: Exception, coluna: str) -> bool:
    err = str(exc).lower()
    col = coluna.lower()
    return col in err and (
        "does not exist" in err or "não existe" in err or "nao existe" in err
    )


def _fetch_fluxo_viagem_sati(apartamento_id: int, start_date, end_date) -> pd.DataFrame:
    cod_filial = resolve_cod_filial(db.engine, apartamento_id)
    key = _fluxo_cache_key(apartamento_id, start_date, end_date, cod_filial)
    now = time.time()
    cached = _fluxo_sati_cache.get(key)
    if cached and (now - cached[0]) < _FLUXO_CACHE_TTL_SEC:
        return cached[1].copy()

    schema = get_sati_schema()
    params = {
        "start_date": start_date,
        "end_date": end_date,
        "cod_filial": cod_filial,
    }

    def _run(incluir_km_vazio: bool = True) -> pd.DataFrame:
        sql = query_fluxo_viagem(schema, incluir_km_vazio=incluir_km_vazio)
        with get_sati_engine().connect() as conn:
            return pd.read_sql_query(text(sql), conn, params=params)

    try:
        df = _run(True)
    except Exception as exc:
        if _fluxo_sql_coluna_ausente(exc, "kmvazio"):
            df = _run(False)
        else:
            raise

    df.columns = [str(c).strip() for c in df.columns]
    _fluxo_sati_cache[key] = (now, df)
    return df


def _placas_fluxo_proprietario(apartamento_id: int) -> set[str] | None:
    """Placas permitidas no fluxo quando BI_COD_PROPRIETARIO está no painel."""
    cod_prop = obter_cod_proprietario_filtro(apartamento_id)
    if cod_prop is None:
        return None
    return set(_mapa_veiculos_sati(apartamento_id, cod_prop).keys())


def _filtrar_fluxo_placas_proprietario(apartamento_id: int, rows: list[dict]) -> list[dict]:
    placas_ok = _placas_fluxo_proprietario(apartamento_id)
    if placas_ok is None:
        return rows
    if not placas_ok:
        return []
    return [
        r
        for r in rows
        if str(r.get("placa") or "").strip().upper() in placas_ok
    ]


def _filtrar_df_fluxo_placas_proprietario(apartamento_id: int, df: pd.DataFrame) -> pd.DataFrame:
    placas_ok = _placas_fluxo_proprietario(apartamento_id)
    if placas_ok is None or df is None or df.empty:
        return df
    if not placas_ok:
        return df.iloc[0:0].copy()
    if "placa" not in df.columns:
        return df
    return df[df["placa"].isin(placas_ok)].copy()


def _get_fluxo_viagem_fallback(
    apartamento_id: int, start_date, end_date, placa_filter, filial_filter
) -> list:
    """Monta fluxo parcial a partir de relFilViagensCliente quando SATI direto não está ativo."""
    df = get_data_as_dataframe("relFilViagensCliente", apartamento_id)
    if df.empty:
        return []
    df = apply_filters_to_df(df, start_date, end_date, placa_filter, filial_filter)
    placas_ok = _placas_fluxo_proprietario(apartamento_id)
    if placas_ok is not None:
        if not placas_ok:
            return []
        cm0 = _get_case_insensitive_column_map(df.columns)
        col_placa0 = cm0.get("placaveiculo")
        if col_placa0:
            df = df[
                df[col_placa0].astype(str).str.strip().str.upper().isin(placas_ok)
            ]
    cm = _get_case_insensitive_column_map(df.columns)
    rows = []
    for _, r in df.iterrows():
        raw = {
            "placa": r.get(cm.get("placaveiculo", "placaveiculo")),
            "motorista": r.get(cm.get("nomemotorista", "nomemotorista")),
            "emissao": r.get(cm.get("dataemissao", "dataemissao")),
            "num_ordem": r.get(cm.get("codordemcar", "codordemcar")),
            "nfe_emitida": None,
            "num_cte": r.get(cm.get("numconhec", "numconhec")),
            "numero": r.get(cm.get("numero", "numero")),
            "ctechave": r.get(cm.get("ctechave", "ctechave")),
            "ctestatus": r.get(cm.get("ctestatus", "ctestatus")),
            "ciot": r.get(cm.get("ciot", "ciot")),
            "protocolo_averbacao": r.get(cm.get("numautgerrisco", "numautgerrisco")),
            "numeropedagio": r.get(cm.get("numeropedagio", "numeropedagio")),
            "mdfestatus": None,
            "mdfeprot": None,
            "mdfe_data_finalizacao": None,
            "mdfe_prot_encerramento": None,
        }
        rows.append(_build_fluxo_row(raw))
    rows.sort(key=lambda x: x.get("emissao") or "", reverse=True)
    return rows


def _fluxo_ordem_emissao_cte_row(row: dict) -> tuple:
    """Ordena CT-es da placa pela data de emissão (e número interno)."""
    ts = pd.to_datetime(row.get("emissao_ts") or "", errors="coerce")
    if pd.isna(ts):
        ts = pd.to_datetime(row.get("data_viagem_motorista_ts") or "", errors="coerce")
    if pd.isna(ts):
        ts = pd.Timestamp.min
    numero = _fluxo_int_or_none(row.get("numero")) or 0
    return (ts, numero)


def _aplicar_ultima_movimentacao_cte_anterior(rows: list[dict]) -> None:
    """
    Por placa: última movimentação = data viagem motorista do CT-e emitido anterior.
    Ex.: CT-e 1 (10/06) → sem última; CT-e 4 (20/06) → última 10/06; CT-e 6 (30/06) → última 20/06.
    """
    from collections import defaultdict

    por_placa: dict[str, list[dict]] = defaultdict(list)
    for row in rows or []:
        placa = str(row.get("placa") or "").strip().upper()
        if not placa or placa in ("—", "NAN"):
            continue
        if not (row.get("data_viagem_motorista_fmt") or row.get("emissao_ts")):
            continue
        por_placa[placa].append(row)

    for grupo in por_placa.values():
        grupo.sort(key=_fluxo_ordem_emissao_cte_row)
        prev_fmt = ""
        prev_ts = ""
        for row in grupo:
            if prev_fmt:
                row["ultima_movimentacao_fmt"] = prev_fmt
                row["ultima_movimentacao_ts"] = prev_ts
            else:
                row["ultima_movimentacao_fmt"] = ""
                row["ultima_movimentacao_ts"] = ""

            dv = (row.get("data_viagem_motorista_fmt") or "").strip()
            if dv:
                prev_fmt = dv
                prev_ts = row.get("data_viagem_motorista_ts") or ""


def _fluxo_ultima_por_placa_rows(rows: list[dict]) -> list[dict]:
    """Mantém só a viagem MDF-e mais recente de cada placa."""
    ordenado = sorted(
        rows,
        key=lambda r: pd.to_datetime(
            r.get("data_viagem_motorista_ts") or r.get("emissao_ts") or "",
            errors="coerce",
        ),
        reverse=True,
    )
    por_placa: dict[str, dict] = {}
    for row in ordenado:
        if not (row.get("steps") or {}).get("mdfe_autorizado"):
            continue
        placa = str(row.get("placa") or "").strip().upper()
        if not placa or placa in ("—", "NAN"):
            continue
        if placa not in por_placa:
            por_placa[placa] = row
    return list(por_placa.values())


def _fluxo_ts_movimentacao_raw(rec: dict) -> pd.Timestamp:
    """Prioriza data viagem motorista do CT-e para ordenar última movimentação."""
    for key in ("data_viagem_motorista", "emissao"):
        val = rec.get(key)
        if val is None or (isinstance(val, float) and pd.isna(val)):
            continue
        ts = pd.to_datetime(val, errors="coerce")
        if pd.notna(ts):
            return ts
    return pd.NaT


def _fluxo_ultima_por_placa(merged: list[dict]) -> list[dict]:
    """Mantém a viagem mais recente de cada placa; prioriza viagem com MDF-e emitido."""
    ordenado = sorted(
        merged,
        key=lambda r: _fluxo_ts_movimentacao_raw(r),
        reverse=True,
    )
    por_placa_mdfe: dict[str, dict] = {}
    por_placa_any: dict[str, dict] = {}
    for rec in ordenado:
        placa = str(rec.get("placa") or "").strip().upper()
        if not placa or placa in ("—", "NAN"):
            continue
        if placa not in por_placa_any:
            por_placa_any[placa] = rec
        if _raw_tem_mdfe_emitido(rec) and placa not in por_placa_mdfe:
            por_placa_mdfe[placa] = rec
    return [
        por_placa_mdfe.get(placa) or por_placa_any[placa]
        for placa in sorted(por_placa_any.keys())
    ]


def _load_fluxo_viagem_rows(
    apartamento_id: int,
    start_date=None,
    end_date=None,
    placa_filter: str = "Todos",
    filial_filter: list = None,
    apenas_ultima_por_placa: bool = False,
    somente_com_mdfe_emitido: bool = False,
) -> list:
    filial_filter = filial_filter or []
    rows = []

    if sati_enabled_for_apartment(db.engine, apartamento_id):
        try:
            df = _fetch_fluxo_viagem_sati(apartamento_id, start_date, end_date)
            if not df.empty:
                df["placa"] = df["placa"].astype(str).str.strip().str.upper()
                df = df[(df["placa"] != "") & (df["placa"] != "—") & (df["placa"].str.lower() != "nan")]
                df = _filtrar_df_fluxo_placas_proprietario(apartamento_id, df)
                if placa_filter and placa_filter != "Todos":
                    df = df[df["placa"] == str(placa_filter).strip().upper()]
                raw_rows = _agrupar_fluxo_por_viagem(
                    df.to_dict(orient="records"),
                    somente_com_mdfe_emitido=somente_com_mdfe_emitido,
                )
                _aplicar_cache_comprovantes_painel(apartamento_id, raw_rows)
                rows = [_build_fluxo_row(rec) for rec in raw_rows]
                _aplicar_ultima_movimentacao_cte_anterior(rows)
                if apenas_ultima_por_placa:
                    rows = _fluxo_ultima_por_placa_rows(rows)
        except Exception as e:
            print(f"ERRO fluxo viagem SATI: {e}")

    if not rows:
        rows = _get_fluxo_viagem_fallback(
            apartamento_id, start_date, end_date, placa_filter, filial_filter
        )
        _aplicar_ultima_movimentacao_cte_anterior(rows)
        if apenas_ultima_por_placa and rows:
            rows = _fluxo_ultima_por_placa_rows(rows)

    rows = _filtrar_fluxo_placas_proprietario(apartamento_id, rows)
    rows.sort(
        key=lambda r: r.get("data_viagem_motorista_ts") or r.get("emissao_ts") or "",
        reverse=True,
    )
    return rows


def _empty_fluxo_resumo(placa: str, motorista: str = "—") -> dict:
    steps = {k: False for k in (
        "ordem_carregamento", "nfe_emitida", "cte_autorizado", "carga_averbada", "ciot_emitido",
        "pedagio_emitido", "mdfe_autorizado", "documento_descarga", "mdfe_encerrado",
    )}
    labels = {k: "" for k in (
        "ordem", "cte", "cte_status", "averbacao", "ciot", "pedagio", "mdfe_status", "mdfe_enc",
    )}
    flux_anim = _build_flux_anim(steps, labels)
    return {
        "placa": placa,
        "motorista": motorista,
        "emissao": "—",
        "data_dia": "—",
        "data_dia_iso": "",
        "emissao_ts": "",
        "num_ordem": None,
        "num_cte": None,
        "numero": None,
        "steps": steps,
        "labels": labels,
        "flux_anim": flux_anim,
        "progresso": 0,
        "progresso_total": len(steps),
        "sem_viagem_periodo": True,
        "numeros_internos_fluxo": [],
        "comprovantes_descarga": [],
        "tem_documento_descarga": False,
        "linha_descarga": "— · Sem documento de descarga",
    }


def get_fluxo_veiculos_resumo(
    apartamento_id: int,
    start_date=None,
    end_date=None,
    filial_filter: list = None,
    limite: int = 120,
) -> list:
    """MDF-es do período (mais recentes primeiro), até ``limite`` linhas."""
    rows = _load_fluxo_viagem_rows(
        apartamento_id,
        start_date,
        end_date,
        "Todos",
        filial_filter,
        apenas_ultima_por_placa=False,
        somente_com_mdfe_emitido=True,
    )
    rows = [r for r in rows if (r.get("steps") or {}).get("mdfe_autorizado")]
    for row in rows:
        row["sem_viagem_periodo"] = False
    if limite and len(rows) > limite:
        rows = rows[:limite]
    return rows


def get_fluxo_viagem_historico(
    apartamento_id: int,
    start_date=None,
    end_date=None,
    placa: str = "",
    filial_filter: list = None,
    limite: int = 40,
) -> list:
    """Análise diária: uma linha por viagem (manifesto) da placa no período."""
    placa = str(placa or "").strip().upper()
    if not placa or placa == "TODOS":
        return []
    rows = _load_fluxo_viagem_rows(
        apartamento_id, start_date, end_date, placa, filial_filter,
        somente_com_mdfe_emitido=True,
    )
    return rows[:limite] if limite else rows


def get_fluxo_viagem_data(
    apartamento_id: int,
    start_date=None,
    end_date=None,
    placa_filter: str = "Todos",
    filial_filter: list = None,
) -> list:
    """Compatível com API: resumo ou histórico conforme filtro de placa."""
    if placa_filter and placa_filter != "Todos":
        return get_fluxo_viagem_historico(
            apartamento_id, start_date, end_date, placa_filter, filial_filter
        )
    return get_fluxo_veiculos_resumo(apartamento_id, start_date, end_date, filial_filter)


def get_nfe_pendentes_cte(
    apartamento_id: int,
    start_date=None,
    end_date=None,
    filial_filter: list | None = None,
    placa_filter: str | None = None,
    numero_nfe: str | None = None,
    data_nfe: str | None = None,
) -> dict:
    """
    NFe transporte (notaxml tipoes=T) sem CT-e: chavenfe não ligada a conhecimento.
    Retorno agrupado por placa do veículo.
    """
    vazio = {"total": 0, "por_placa": [], "mensagem": ""}
    if not sati_enabled_for_apartment(db.engine, apartamento_id):
        vazio["mensagem"] = "SATI não configurado para esta transportadora."
        return vazio

    cod_filial = resolve_cod_filial(db.engine, apartamento_id)
    if filial_filter:
        try:
            cod_filial = int(filial_filter[0])
        except (TypeError, ValueError, IndexError):
            pass

    sql = query_nfe_pendentes_cte(get_sati_schema())
    params = {
        "start_date": start_date,
        "end_date": end_date,
        "cod_filial": cod_filial,
    }
    try:
        with get_sati_engine().connect() as conn:
            df = pd.read_sql_query(text(sql), conn, params=params)
    except Exception as e:
        print(f"ERRO NFe pendentes CT-e: {e}")
        vazio["mensagem"] = f"Erro ao consultar SATI: {e}"
        return vazio

    if df.empty:
        vazio["mensagem"] = "Nenhuma NFe pendente de CT-e no período."
        return vazio

    df.columns = [str(c).strip() for c in df.columns]
    from collections import defaultdict

    placa_f = str(placa_filter or "").strip().upper()
    numero_f = str(numero_nfe or "").strip()
    data_f = str(data_nfe or "").strip()

    buckets: dict[str, list[dict]] = defaultdict(list)
    for _, row in df.iterrows():
        placa = str(row.get("placa") or "SEM PLACA").strip().upper() or "SEM PLACA"
        if placa_f and placa_f not in ("TODOS", "—") and placa != placa_f:
            continue
        numeronota = str(row.get("numeronota") or "").strip()
        serie = str(row.get("serie") or "").strip()
        nota_ref = f"{serie}/{numeronota}" if serie else numeronota
        if numero_f and numero_f not in numeronota and numero_f not in nota_ref:
            continue
        data_raw = row.get("data_nfe")
        data_fmt = "—"
        data_iso = ""
        if data_raw is not None and not (isinstance(data_raw, float) and pd.isna(data_raw)):
            dt = pd.to_datetime(data_raw, errors="coerce")
            if pd.notna(dt):
                data_fmt = dt.strftime("%d/%m/%Y")
                data_iso = dt.strftime("%Y-%m-%d")
        if data_f and data_iso != data_f:
            continue
        valor = row.get("valor")
        try:
            valor_fmt = f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except (TypeError, ValueError):
            valor_fmt = "—"
        chave = str(row.get("chavenfe") or "").strip()
        emitente = str(row.get("emitente_nome") or row.get("nome") or "").strip() or "—"
        remetente = str(row.get("remetente_nome") or row.get("clientenome") or "").strip() or "—"
        destino = str(row.get("destino_nome") or row.get("destnome") or "").strip() or "—"
        mercadoria = str(row.get("mercadoria_nome") or "").strip() or "—"
        buckets[placa].append({
            "chavenfe": chave,
            "chavenfe_curta": chave[-8:] if len(chave) > 8 else chave,
            "numeronota": numeronota,
            "serie": serie,
            "nota_ref": nota_ref or "—",
            "data_nfe": data_fmt,
            "data_nfe_iso": data_iso,
            "placa": placa,
            "destino": destino,
            "mercadoria": mercadoria,
            "remetente": remetente,
            "emitiu_nota": emitente,
            "valor": valor_fmt,
            "status": str(row.get("status") or "").strip(),
            "sitnfe": str(row.get("sitnfe") or "").strip(),
        })

    por_placa = []
    total_filtrado = 0
    for placa in sorted(buckets.keys(), key=lambda p: (-len(buckets[p]), p)):
        notas = buckets[placa]
        total_filtrado += len(notas)
        por_placa.append({
            "placa": placa,
            "qtd": len(notas),
            "notas": notas,
        })

    if not por_placa:
        vazio["mensagem"] = "Nenhuma NFe pendente com os filtros informados."
        return vazio

    return {
        "total": total_filtrado,
        "por_placa": por_placa,
        "mensagem": "",
    }


def get_expense_audit_data(
    apartamento_id: int,
    start_date,
    end_date,
    placa_filter,
    filial_filter,
    tipo_negocio_filter,
    unidade_embarque_filter: list | None = None,
    embarcador_filter: str = "Todos",
):
    """
    Prepara os dados para a auditoria de despesas, agrupando itens por categoria e grupo.
    """
    # 1. Reutiliza a função mestre para buscar todos os dados já filtrados
    filtered_data = _obter_dados_filtrados_mestre(
        apartamento_id,
        start_date,
        end_date,
        placa_filter,
        filial_filter,
        tipo_negocio_filter,
        unidade_embarque_filter,
        embarcador_filter,
    )
    df_viagens_cliente = filtered_data["df_viagens_cliente"]
    df_despesas_filtrado = filtered_data["df_despesas_filtrado"]
    df_flags = filtered_data["df_flags"]
    df_acerto_motorista_raw = filtered_data["df_acerto_motorista_raw"]

    # 2. Reutiliza a função que classifica as despesas
    expense_data = _get_final_expense_dataframes(df_viagens_cliente, df_despesas_filtrado, df_flags, df_acerto_motorista_raw)
    df_custos = expense_data.get('custos', pd.DataFrame())
    df_despesas_gerais = expense_data.get('despesas', pd.DataFrame())
    df_tipo_d = expense_data.get('tipo_d', pd.DataFrame())

    # 3. Função auxiliar para agrupar os dados para o formato do modal
    def _group_for_audit(df: pd.DataFrame):
        col_map = _get_case_insensitive_column_map(df.columns)
        group_col = col_map.get('descgrupod')
        item_col = col_map.get('descitemd')
        
        if df.empty or not group_col or not item_col:
            return {}
        
        # Agrupa pelo nome do grupo de despesa e cria uma lista com as descrições dos itens
        return df.groupby(group_col)[item_col].apply(lambda x: x.dropna().unique().tolist()).to_dict()

    # 4. Monta o resultado final
    audit_result = {
        "custos": _group_for_audit(df_custos),
        "despesas": _group_for_audit(df_despesas_gerais),
        "tipo_d": _group_for_audit(df_tipo_d)
    }

    return audit_result

def get_relatorio_viagem_data(apartamento_id: int, numero: int, dias_janela: int = 10):
    """
    VERSÃO FINAL 9: Usa 'numero' de forma consistente em todo o fluxo.
    """
    df_viagens = get_data_as_dataframe("relFilViagensCliente", apartamento_id)
    df_fat = get_data_as_dataframe("relFilViagensFatCliente", apartamento_id)
    df_despesas_raw = get_data_as_dataframe("relFilDespesasGerais", apartamento_id)
    df_acerto_motorista = get_data_as_dataframe("relFilAcertoMot", apartamento_id)
    df_flags = get_all_group_flags(apartamento_id)

    viagem = df_viagens[df_viagens['numero'] == numero].copy()
    faturamento = df_fat[df_fat['numero'] == numero]
    acerto = df_acerto_motorista[df_acerto_motorista['numero'] == numero]

    if viagem.empty:
        return {"error": "Viagem não encontrada."}

    viagem_data = viagem.iloc[0].to_dict()
    fat_data = faturamento.iloc[0].to_dict() if not faturamento.empty else {}
    acerto_data = _agregar_acerto_motorista(acerto)
    km_comissao = _km_comissao_relatorio(viagem_data, acerto_data)

    placa_viagem = _dict_get_ci(viagem_data, "placaVeiculo", "placaveiculo")
    data_viagem_obj = pd.to_datetime(
        _dict_get_ci(viagem_data, "dataViagemMotorista", "dataviagemmotorista"), errors="coerce"
    )

    col_map_desp_raw = _get_case_insensitive_column_map(df_despesas_raw.columns)
    cod_item_col = col_map_desp_raw.get("coditemnota", "codItemNota")

    ids_associados_nesta_viagem = []
    ids_associados_em_qualquer_viagem = []
    ids_excluidos = []

    with engine.connect() as conn:
        query_associadas_nesta_viagem = text('SELECT "coditemnota" FROM despesas_viagem_associadas WHERE apartamento_id = :apt_id AND numero = :numero')
        result_nesta_viagem = conn.execute(query_associadas_nesta_viagem, {"apt_id": apartamento_id, "numero": numero})
        ids_associados_nesta_viagem = [row[0] for row in result_nesta_viagem]

        query_todos_associados = text('SELECT "coditemnota" FROM despesas_viagem_associadas WHERE apartamento_id = :apt_id')
        result_todos = conn.execute(query_todos_associados, {"apt_id": apartamento_id})
        ids_associados_em_qualquer_viagem = [row[0] for row in result_todos]
        
        query_excluidas = text('SELECT "coditemnota" FROM despesas_viagem_excluidas WHERE apartamento_id = :apt_id AND numero = :numero')
        result_excluidas = conn.execute(query_excluidas, {"apt_id": apartamento_id, "numero": numero})
        ids_excluidos = [row[0] for row in result_excluidas]

    despesas_associadas_manual = df_despesas_raw[
        df_despesas_raw[cod_item_col].isin(ids_associados_nesta_viagem)
    ].copy() if cod_item_col in df_despesas_raw.columns else pd.DataFrame()
    todas_despesas_associadas = despesas_associadas_manual

    expense_data = _get_final_expense_dataframes(viagem, todas_despesas_associadas, df_flags, acerto)
    df_custos_nota = expense_data.get("custo_nota", pd.DataFrame())
    df_despesas_gerais = expense_data.get("despesas", pd.DataFrame())
    
    col_map_fat = _get_case_insensitive_column_map(faturamento.columns)
    frete_empresa_col = col_map_fat.get('freteempresa')

    comissao_map = dre.comissao_acerto_por_numero(acerto)
    dre_opts = obter_dre_opts(apartamento_id)
    modo_proprietario = dre_opts.get("campo_receita") == "fretemotorista"
    dre_previa = dre.calcular_dre_viagem(
        viagem_data,
        comissao_map.get(int(numero) if numero else numero, 0.0),
        campo_receita=dre_opts.get("campo_receita", "freteempresa"),
        incluir_icms_custo=dre_opts.get("incluir_icms_custo", True),
    )

    frete_bruto = dre_previa["receita"] if modo_proprietario else dre_previa["frete_empresa"]
    frete_empresa_bruto = dre_previa.get("frete_empresa_bruto", frete_bruto)
    valor_pedagio = dre_previa["valor_pedagio"]
    pedagio_embutido = dre_previa["pedagio_embutido"]
    total_receitas = dre_previa["receita"]

    valor_quebra = dre_previa.get("valor_quebra_bruto", dre_previa["custo_quebra_potencial"])
    comissao_motorista = dre_previa["comissao_motorista"]
    custo_motorista = dre_previa["custo_motorista"]
    custo_icms = dre_previa["custo_icms"]
    custo_seguro = dre_previa["custo_seguro"]

    total_outros_custos = dre.soma_itemnota_sem_grupos_conhecimento(df_custos_nota)
    total_despesas = dre.soma_itemnota_sem_grupos_conhecimento(df_despesas_gerais)

    outros_descontos = _dict_get_ci(viagem_data, "outrosDescontos", "outrosdescontos", default=0)
    resultado = dre.calcular_lucro_viagem(
        dre_previa,
        custos_itemnota=total_outros_custos,
        despesas_itemnota=total_despesas,
        outros_descontos=outros_descontos,
    )
    lucro = resultado["lucro"]
    margem = resultado["margem_pct"]
    custo_previa_conhecimento = dre_previa["custo_previa_conhecimento"]
    total_custos_final = custo_previa_conhecimento + total_outros_custos

    def formatar_df_para_relatorio(df):
        if df.empty:
            return []
        df_copy = df.copy()
        cm = _get_case_insensitive_column_map(df_copy.columns)
        data_col = cm.get("datacontrole", "dataControle")
        if data_col in df_copy.columns:
            df_copy["dataControle_fmt"] = pd.to_datetime(df_copy[data_col], errors="coerce").dt.strftime("%d/%m/%Y")
        else:
            df_copy["dataControle_fmt"] = ""
        aliases = {
            "descGrupoD": ["descgrupod", "descGrupoD"],
            "codNota": ["codnota", "codNota"],
            "serie": ["serie"],
            "nomeForn": ["nomeforn", "nomeForn"],
            "codItemNota": ["coditemnota", "codItemNota"],
            "descItemD": ["descitemd", "descItemD"],
        }
        colunas_para_manter = {"dataControle_fmt": "dataControle", "valor_calculado": "valor_calculado"}
        for out_name, keys in aliases.items():
            for k in keys:
                if k in cm:
                    colunas_para_manter[cm[k]] = out_name
                    break
        colunas_existentes = {k: v for k, v in colunas_para_manter.items() if k in df_copy.columns}
        df_formatado = df_copy[list(colunas_existentes.keys())].rename(columns=colunas_existentes)
        if "valor_calculado" in df_formatado.columns:
            df_formatado["valor_calculado"] = pd.to_numeric(
                df_formatado["valor_calculado"], errors="coerce"
            ).fillna(0.0)
        return df_formatado.fillna("").to_dict("records")

    custos_detalhados_formatado = formatar_df_para_relatorio(df_custos_nota)
    despesas_detalhadas_formatado = formatar_df_para_relatorio(df_despesas_gerais)
    
    despesas_sugeridas = []
    periodo_sugestao = {"inicio": None, "fim": None, "proxima_viagem": None}
    data_col = col_map_desp_raw.get("datacontrole", "dataControle")
    data_ini_janela, data_fim_janela, proxima_viagem_fmt = _janela_sugestao_despesas(
        df_viagens, placa_viagem, data_viagem_obj, numero
    )
    if data_ini_janela is not None and data_fim_janela is not None:
        periodo_sugestao = {
            "inicio": data_ini_janela.strftime("%d/%m/%Y"),
            "fim": data_fim_janela.strftime("%d/%m/%Y"),
            "proxima_viagem": proxima_viagem_fmt,
        }
    if (
        placa_viagem
        and pd.notna(data_viagem_obj)
        and data_ini_janela is not None
        and data_fim_janela is not None
        and not df_despesas_raw.empty
        and data_col in df_despesas_raw.columns
    ):
        df_despesas_raw = df_despesas_raw.copy()
        df_despesas_raw[data_col] = pd.to_datetime(df_despesas_raw[data_col], errors="coerce")
        data_ini_cmp = data_ini_janela.normalize()
        data_fim_cmp = data_fim_janela.normalize() + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

        candidatas = df_despesas_raw[
            (df_despesas_raw.get(col_map_desp_raw.get("despesa"), pd.Series(dtype=str)) == "S")
            & (df_despesas_raw.get(col_map_desp_raw.get("placaveiculo")) == placa_viagem)
            & (df_despesas_raw[data_col] >= data_ini_cmp)
            & (df_despesas_raw[data_col] <= data_fim_cmp)
            & (~df_despesas_raw.get(cod_item_col, pd.Series(dtype=int)).isin(ids_excluidos))
            & (~df_despesas_raw.get(cod_item_col, pd.Series(dtype=int)).isin(ids_associados_em_qualquer_viagem))
        ].copy().sort_values(by=data_col)
        
        if not candidatas.empty:
            if all(c in col_map_desp_raw for c in ["serie", "liquido", "vlcontabil"]):
                candidatas["Valor"] = np.where(
                    candidatas[col_map_desp_raw["serie"]] == "RQ",
                    candidatas[col_map_desp_raw["liquido"]],
                    candidatas[col_map_desp_raw["vlcontabil"]],
                )
            else:
                candidatas["Valor"] = candidatas.get(col_map_desp_raw.get("vlcontabil"), 0)
            candidatas["dataControle_fmt"] = candidatas[data_col].dt.strftime("%d/%m/%Y")
            colunas_desejadas_raw = ["descGrupoD", "codNota", "serie", "nomeForn", "codItemNota", "descItemD"]
            colunas_existentes_map = {
                orig: col_map_desp_raw.get(orig.lower())
                for orig in colunas_desejadas_raw
                if col_map_desp_raw.get(orig.lower())
            }
            colunas_unicas_para_selecionar = list(set(colunas_existentes_map.values()))
            colunas_finais_para_selecionar = [col for col in colunas_unicas_para_selecionar + ['dataControle_fmt', 'Valor'] if col in candidatas.columns]
            df_sugestoes = candidatas[colunas_finais_para_selecionar]
            df_sugestoes = df_sugestoes.rename(columns={col: orig for orig, col in colunas_existentes_map.items()})
            df_sugestoes = df_sugestoes.rename(columns={'dataControle_fmt': 'dataControle'})
            despesas_sugeridas = df_sugestoes.fillna('').to_dict('records')
    # Cria a string de exibição para a viagem (CT-e)
    numero_display = str(_dict_get_ci(viagem_data, "numero", default=""))
    num_conhec = _dict_get_ci(fat_data, "numConhec", "numconhec")
    if num_conhec and num_conhec != 0:
        numero_display = f"{numero_display} ({int(num_conhec)})"
    relatorio = {
    "numero": numero,
    "viagem_display": numero_display,
    "data_viagem": _dict_get_ci(viagem_data, "dataViagemMotorista", "dataviagemmotorista"),
    "placa_veiculo": placa_viagem,
    "motorista": _dict_get_ci(viagem_data, "nomeMotorista", "nomemotorista"),
    "numero_nota": (
        _dict_get_ci(viagem_data, "numNotaNF", "numnotanf", "nfe_numero_notaxml")
        or _dict_get_ci(fat_data, "numNotaNF", "numnotanf")
        or "—"
    ),
    "filial": _dict_get_ci(viagem_data, "nomeFilial", "nomefilial")
        or _dict_get_ci(fat_data, "nomeFilial", "nomefilial", default="N/A"),
    "unidade_embarque": _dict_get_ci(viagem_data, "nomeUnidEmb", "nomeunidembarque", default="N/A"),
    "origem": _dict_get_ci(viagem_data, "cidOrigemFormat", "cidorigemformat"),
    "destino": _dict_get_ci(viagem_data, "cidDestinoFormat", "ciddestinoformat"),
    "cliente": _dict_get_ci(viagem_data, "nomeCliente", "nomecliente")
        or _dict_get_ci(fat_data, "nomeCliente", "nomecliente", default="N/A"),
    "peso_saida": _dict_get_ci(viagem_data, "pesoSaida", "pesosaida"),
    "peso_chegada": _dict_get_ci(viagem_data, "pesoChegada", "pesochegada"),
    "valor_seguro": dre_previa["custo_seguro"] if dre_previa["custo_seguro"] > 0 else _dict_get_ci(viagem_data, "valorSeguro", "valorseguro", "premioSeguro", "premioseguro", default=0),
    "km_inicial": km_comissao["km_inicial"],
    "km_final": km_comissao["km_final"],
    "km_rodado": km_comissao["km_rodado"],
    "comissao_perc": km_comissao["comissao_perc"],
    "valor_base_comissao": km_comissao["valor_base_comissao"],
    "valor_comissao_calculada": km_comissao.get("valor_comissao_calculada", comissao_motorista),
    "fretemotorista_bruto": dre_previa.get("fretemotorista_bruto", 0),
    "composicao_motorista": [] if modo_proprietario else dre_previa.get("composicao_motorista", []),
    "modo_proprietario": modo_proprietario,
    "valor_quebra_bruto": dre_previa.get("valor_quebra_bruto", valor_quebra),
    "pedagio_embutido_motorista": dre_previa.get("pedagio_embutido_motorista", "N"),
    "frete_bruto": frete_bruto,
    "frete_empresa_bruto": frete_empresa_bruto,
    "permite_faturar": dre_previa.get("permite_faturar", True),
    "pagar_conhecimento": dre_previa.get("pagar_conhecimento", True),
    "permite_faturar_flag": dre_previa.get("permite_faturar_flag", "S"),
    "pagar_flag": dre_previa.get("pagar_flag", "S"),
    "custo_previa_potencial": dre_previa.get("custo_previa_potencial", 0),
    "custo_motorista_potencial": dre_previa.get("custo_motorista_potencial", 0),
    "comissao_motorista_potencial": dre_previa.get("comissao_motorista_potencial", 0),
    "custo_icms_potencial": dre_previa.get("custo_icms_potencial", 0),
    "custo_seguro_potencial": dre_previa.get("custo_seguro_potencial", 0),
    "custo_quebra_potencial": dre_previa.get("custo_quebra_potencial", 0),
    "valor_pedagio": valor_pedagio,
    "pedagio_embutido_frete": pedagio_embutido,
    "pedagio_reembolso": dre_previa.get("pedagio_reembolso", dre_previa.get("pedagio_fatura_cliente", 0)),
    "pedagio_fatura_cliente": dre_previa.get("pedagio_reembolso", dre_previa.get("pedagio_fatura_cliente", 0)),
    "total_receitas": total_receitas,
    "custo_motorista": custo_motorista,
    "custo_icms": custo_icms,
    "custo_seguro": custo_seguro,
    "custo_previa_conhecimento": custo_previa_conhecimento,
    "valor_quebra": valor_quebra,
    "comissao_motorista": comissao_motorista,
    "total_outros_custos": total_outros_custos,
    "outros_descontos": outros_descontos,
    "custos_detalhados": custos_detalhados_formatado,
    "despesas_detalhadas": despesas_detalhadas_formatado,
    "total_custos": total_custos_final, "total_despesas": total_despesas,
    "lucro_prejuizo_valor": lucro, "margem_valor": margem,
    "tipo_frete": dre_previa.get("tipo_frete")
        or str(_dict_get_ci(viagem_data, "tipoFrete", "tipofrete", default="") or "").strip().upper(),
    "tipo_frete_label": dre.label_tipofrete_relatorio(
        dre_previa.get("tipo_frete")
        or _dict_get_ci(viagem_data, "tipoFrete", "tipofrete", default="")
    ),
    "despesas_sugeridas": despesas_sugeridas,
    "periodo_sugestao_despesas": periodo_sugestao,
}
    return _sanitize_for_json(relatorio)