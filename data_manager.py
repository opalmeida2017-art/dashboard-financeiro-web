# Forçando a atualização para o deploy

import pandas as pd
from sqlalchemy import text
from datetime import datetime
from slugify import slugify
import database as db
from database import engine 
import config
import numpy as np
import re

# Substitua esta função em data_manager.py

def get_data_as_dataframe(table_name: str, apartamento_id: int) -> pd.DataFrame:
    """
    Busca todos os dados de uma tabela para um apartamento específico e padroniza os nomes das colunas,
    removendo espaços no início e no fim.
    """
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
            
            return df
    except Exception as e:
        print(f"ERRO CRÍTICO ao carregar dados da tabela '{table_name}': {e}")
        return pd.DataFrame()

def _get_case_insensitive_column_map(df_columns):
    """Cria um dicionário para mapear nomes de colunas em minúsculas para seus nomes originais."""
    return {col.lower(): col for col in df_columns}

def apply_filters_to_df(df: pd.DataFrame, start_date: datetime, end_date: datetime, placa_filter: str, filial_filter: list) -> pd.DataFrame:
    """
    Aplica filtros de data, placa e uma LISTA de filiais a um DataFrame de forma case-insensitive e inteligente.
    """
    if df.empty:
        return df
    
    df_filtrado = df.copy()
    col_map = _get_case_insensitive_column_map(df_filtrado.columns)
    
    # Filtragem por Data (lógica existente mantida)
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

    # Filtragem por Placa (lógica existente mantida)
    if placa_filter and placa_filter != "Todos":
        placa_cols_lower = [c.lower() for c in config.FILTER_COLUMN_MAPS.get("placa", [])]
        placa_col_found_lower = next((col for col in placa_cols_lower if col in col_map), None)
        if placa_col_found_lower:
            original_placa_col = col_map[placa_col_found_lower]
            placa_filter_limpa = placa_filter.strip().upper()
            df_filtrado = df_filtrado[df_filtrado[original_placa_col].astype(str).str.strip().str.upper() == placa_filter_limpa]

    # CORREÇÃO: Lógica de Filtragem de Filial Inteligente
    if filial_filter:
        filial_cols_possiveis = config.FILTER_COLUMN_MAPS.get("filial", [])
        coluna_para_usar = None
        
        # Procura a melhor coluna de filial: uma que exista e que contenha dados
        for col_lower in [c.lower() for c in filial_cols_possiveis]:
            if col_lower in col_map:
                col_original = col_map[col_lower]
                if not df_filtrado[col_original].dropna().empty:
                    coluna_para_usar = col_original
                    break # Usa a primeira coluna que encontrar que não esteja vazia
        
        if coluna_para_usar:
            filial_filter_upper = [f.upper() for f in filial_filter]
            # Limpa os espaços e compara em maiúsculas
            df_filtrado = df_filtrado[df_filtrado[coluna_para_usar].astype(str).str.strip().str.upper().isin(filial_filter_upper)]
            
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

    # Converte todas as colunas de data de uma vez
    for col in date_cols_in_df:
        df[col] = pd.to_datetime(df[col], errors='coerce')

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
        filtro_comissao = (df_viagens_cliente_copy[col_map_viagens_cli['tipofrete']].astype(str) == 'P') & (pd.to_numeric(df_viagens_cliente_copy[col_map_viagens_cli['fretemotorista']], errors='coerce') > 0)
        df_comissao_base = df_viagens_cliente_copy[filtro_comissao].copy()
        if not df_comissao_base.empty:
            frete_motorista = pd.to_numeric(df_comissao_base[col_map_viagens_cli['fretemotorista']], errors='coerce').fillna(0)
            percentual_comissao = pd.to_numeric(df_comissao_base[col_map_viagens_cli['comissao']], errors='coerce').fillna(0)
            df_comissao_base.loc[:, 'valor_calculado'] = frete_motorista * (percentual_comissao / 100)
            
            comissao_df_data = df_comissao_base[[col_map_viagens_cli['dataviagemmotorista'], 'valor_calculado', filial_col_to_use]].rename(columns={col_map_viagens_cli['dataviagemmotorista']: 'datacontrole', filial_col_to_use: 'nomefil'})

            if flags_dict.get('COMISSÃO DE MOTORISTA', {}).get('is_custo_viagem') == 'S':
                df_custos = pd.concat([df_custos, comissao_df_data], ignore_index=True)
            elif flags_dict.get('COMISSÃO DE MOTORISTA', {}).get('is_despesa') == 'S':
                df_despesas_gerais = pd.concat([df_despesas_gerais, comissao_df_data], ignore_index=True)

    if not df_viagens_cliente_copy.empty and 'valorquebra' in col_map_viagens_cli:
        quebra_df_data = df_viagens_cliente_copy[[col_map_viagens_cli['dataviagemmotorista'], col_map_viagens_cli['valorquebra'], filial_col_to_use]].rename(columns={col_map_viagens_cli['dataviagemmotorista']: 'datacontrole', col_map_viagens_cli['valorquebra']: 'valor_calculado', filial_col_to_use: 'nomefil'})
        
        if flags_dict.get('VALOR QUEBRA', {}).get('is_custo_viagem') == 'S':
            df_custos = pd.concat([df_custos, quebra_df_data], ignore_index=True)
        elif flags_dict.get('VALOR QUEBRA', {}).get('is_despesa') == 'S':
            df_despesas_gerais = pd.concat([df_despesas_gerais, quebra_df_data], ignore_index=True)

    return df_custos, df_despesas_gerais


def _get_final_expense_dataframes(df_viagens_cliente, df_despesas_filtrado, df_flags):
    """
    Função auxiliar mestra que serve como FONTE ÚNICA DA VERDADADE para todos os cálculos de despesas.
    VERSÃO DE DEPURAÇÃO: Imprime a lógica de classificação de custos.
    """
    flags_dict = df_flags.set_index('group_name').to_dict('index') if not df_flags.empty else {}
    col_map_despesas = _get_case_insensitive_column_map(df_despesas_filtrado.columns)
    
    if not df_despesas_filtrado.empty and 'despesa' in col_map_despesas:
        df_despesas_filtrado = df_despesas_filtrado[df_despesas_filtrado[col_map_despesas['despesa']] == 'S'].copy()

    if not df_despesas_filtrado.empty:
        if all(c in col_map_despesas for c in ['serie', 'liquido', 'vlcontabil']):
            df_despesas_filtrado.loc[:, 'valor_calculado'] = np.where(df_despesas_filtrado[col_map_despesas['serie']] == 'RQ', df_despesas_filtrado[col_map_despesas['liquido']], df_despesas_filtrado[col_map_despesas['vlcontabil']])
        elif 'vlcontabil' in col_map_despesas:
            df_despesas_filtrado.loc[:, 'valor_calculado'] = df_despesas_filtrado[col_map_despesas['vlcontabil']]
        else:
            df_despesas_filtrado.loc[:, 'valor_calculado'] = 0

    outros_gastos = []
    if not df_viagens_cliente.empty:
        col_map_viagens_cli = _get_case_insensitive_column_map(df_viagens_cliente.columns)
        
        if 'dataviagemmotorista' in col_map_viagens_cli and 'dataemissao' in col_map_viagens_cli:
            df_viagens_cliente['data_custo_fallback'] = df_viagens_cliente[col_map_viagens_cli['dataviagemmotorista']].fillna(df_viagens_cliente[col_map_viagens_cli['dataemissao']])
        elif 'dataviagemmotorista' in col_map_viagens_cli:
            df_viagens_cliente['data_custo_fallback'] = df_viagens_cliente[col_map_viagens_cli['dataviagemmotorista']]
        else:
            df_viagens_cliente['data_custo_fallback'] = pd.NaT

        if 'valorquebra' in col_map_viagens_cli:
            df_quebra = df_viagens_cliente[df_viagens_cliente[col_map_viagens_cli['valorquebra']] > 0].copy()
            if not df_quebra.empty:
                df_quebra['valor_calculado'] = df_quebra[col_map_viagens_cli['valorquebra']]
                df_quebra['descGrupoD'] = 'VALOR QUEBRA'
                df_quebra.rename(columns={'data_custo_fallback': 'dataControle'}, inplace=True)
                outros_gastos.append(df_quebra)
        
        if all(c in col_map_viagens_cli for c in ['tipofrete', 'fretemotorista', 'comissao']):
            filtro_comissao = (df_viagens_cliente[col_map_viagens_cli['tipofrete']].astype(str) == 'P') & (pd.to_numeric(df_viagens_cliente[col_map_viagens_cli['fretemotorista']], errors='coerce') > 0)
            df_comissao = df_viagens_cliente[filtro_comissao].copy()
            if not df_comissao.empty:
                frete = pd.to_numeric(df_comissao[col_map_viagens_cli['fretemotorista']], errors='coerce').fillna(0)
                perc = pd.to_numeric(df_comissao[col_map_viagens_cli['comissao']], errors='coerce').fillna(0)
                df_comissao['valor_calculado'] = frete * (perc / 100)
                df_comissao['descGrupoD'] = 'COMISSÃO DE MOTORISTA'
                df_comissao.rename(columns={'data_custo_fallback': 'dataControle'}, inplace=True)
                outros_gastos.append(df_comissao)

    df_despesas_unificado = pd.concat([df_despesas_filtrado] + outros_gastos, ignore_index=True)
    
    df_tipo_d = pd.DataFrame()
    col_map_unificado_final = _get_case_insensitive_column_map(df_despesas_unificado.columns)
    if not df_despesas_unificado.empty and 'ved' in col_map_unificado_final:
        df_tipo_d = df_despesas_unificado[df_despesas_unificado[col_map_unificado_final['ved']] == 'D'].copy()
        df_despesas_unificado = df_despesas_unificado[df_despesas_unificado[col_map_unificado_final['ved']] != 'D']

    if df_despesas_unificado.empty:
        return {'custos': pd.DataFrame(), 'despesas': pd.DataFrame(), 'tipo_d': df_tipo_d}

    df_com_flags = pd.merge(df_despesas_unificado, df_flags, left_on=col_map_unificado_final.get('descgrupod'), right_on='group_name', how='left')
    df_com_flags['is_custo_viagem'] = df_com_flags['is_custo_viagem'].fillna('N')
    df_com_flags['is_despesa'] = df_com_flags['is_despesa'].fillna('N')
    
    # --- INÍCIO DO CÓDIGO DE DEPURAÇÃO ---
    print("\n" + "="*50)
    print("--- DEPURAÇÃO: VERIFICANDO CLASSIFICAÇÃO DE CUSTOS ---")
    
    # Mostra os grupos que o sistema considera como CUSTO a partir da sua configuração
    grupos_configurados_como_custo = df_flags[df_flags['is_custo_viagem'] == 'S']['group_name'].tolist()
    print(f"\nGrupos configurados como CUSTO no Gerenciador: {grupos_configurados_como_custo}")

    # Verifica os grupos que existem nos dados de despesa e como foram classificados
    if col_map_unificado_final.get('descgrupod') in df_com_flags.columns:
        grupos_nos_dados = df_com_flags[[col_map_unificado_final.get('descgrupod'), 'is_custo_viagem']].drop_duplicates()
        print("\nClassificação aplicada aos grupos encontrados nos dados:")
        print(grupos_nos_dados.to_string())
        
        # Encontra grupos que deveriam ser 'S' mas foram classificados como 'N'
        grupos_problematicos = df_com_flags[
            (df_com_flags[col_map_unificado_final.get('descgrupod')].isin(grupos_configurados_como_custo)) &
            (df_com_flags['is_custo_viagem'] == 'N')
        ][col_map_unificado_final.get('descgrupod')].unique().tolist()
        
        if grupos_problematicos:
            print("\n!!! ALERTA: Os seguintes grupos foram configurados como CUSTO, mas não foram encontrados nos dados (verifique espaços/nomes):")
            print(grupos_problematicos)
        else:
            print("\nNenhuma divergência de classificação encontrada.")
    
    print("="*50 + "\n")
    # --- FIM DO CÓDIGO DE DEPURAÇÃO ---

    df_custos_final = df_com_flags[df_com_flags['is_custo_viagem'] == 'S'].copy()
    df_despesas_final = df_com_flags[df_com_flags['is_despesa'] == 'S'].copy()
    
    return {'custos': df_custos_final, 'despesas': df_despesas_final, 'tipo_d': df_tipo_d}

def _obter_dados_filtrados_mestre(apartamento_id: int, start_date: datetime, end_date: datetime, placa_filter: str, filial_filter: list, tipo_negocio_filter: str):
    """
    Função mestre e consolidada que carrega todos os dados brutos necessários e aplica
    a lógica de filtragem completa, servindo como fonte única para os cálculos do dashboard.
    """
    # 1. Carrega todos os DataFrames brutos
    df_viagens_raw = get_data_as_dataframe("relFilViagensCliente", apartamento_id)
    df_fat_raw = get_data_as_dataframe("relFilViagensFatCliente", apartamento_id)
    df_despesas_raw = get_data_as_dataframe("relFilDespesasGerais", apartamento_id)
    df_contas_pagar_raw = get_data_as_dataframe("relFilContasPagarDet", apartamento_id)
    df_contas_receber_raw = get_data_as_dataframe("relFilContasReceber", apartamento_id)
    df_flags = get_all_group_flags(apartamento_id)

    # 2. Pré-filtra por Tipo de Negócio (se aplicável)
    df_despesas_pre_filtrado = df_despesas_raw
    df_viagens_pre_filtrado = df_viagens_raw
    
    col_map_desp_raw = _get_case_insensitive_column_map(df_despesas_raw.columns)
    col_map_viag_raw = _get_case_insensitive_column_map(df_viagens_raw.columns)

    if tipo_negocio_filter and tipo_negocio_filter != "Todos":
        if 'descnegocio' in col_map_desp_raw and not df_despesas_raw.empty:
            df_despesas_pre_filtrado = df_despesas_raw[df_despesas_raw[col_map_desp_raw['descnegocio']] == tipo_negocio_filter].copy()

        if 'tipofrete' in col_map_viag_raw and not df_viagens_raw.empty:
            tipo_negocio_upper = tipo_negocio_filter.upper().strip()
            if tipo_negocio_upper == 'FROTA':
                placas_de_apoio = []
                if 'veiculoproprio' in col_map_desp_raw and 'placaveiculo' in col_map_desp_raw:
                    placas_de_apoio = df_despesas_raw[df_despesas_raw[col_map_desp_raw['veiculoproprio']] == 'F'][col_map_desp_raw['placaveiculo']].unique().tolist()
                df_viagens_pre_filtrado = df_viagens_raw[(df_viagens_raw[col_map_viag_raw['tipofrete']] == 'P') | (df_viagens_raw[col_map_viag_raw['placaveiculo']].isin(placas_de_apoio))].copy()
            elif 'AGENCIAMENTO' in tipo_negocio_upper:
                df_viagens_pre_filtrado = df_viagens_raw[df_viagens_raw[col_map_viag_raw['tipofrete']].isin(['A', 'T'])].copy()
            else:
                df_viagens_pre_filtrado = pd.DataFrame(columns=df_viagens_raw.columns)

    # 3. Aplica os filtros principais (data, placa, filial) sobre os dados pré-filtrados
    df_viagens_cliente = apply_filters_to_df(df_viagens_pre_filtrado, start_date, end_date, placa_filter, filial_filter)
    df_despesas_filtrado = apply_filters_to_df(df_despesas_pre_filtrado, start_date, end_date, placa_filter, filial_filter)

    # 4. Filtra o faturamento com base nas viagens já filtradas
    viagens_filtradas_ids = df_viagens_cliente['numConhec'].unique() if not df_viagens_cliente.empty else []
    col_map_fat_temp = _get_case_insensitive_column_map(df_fat_raw.columns)
    if 'permitefaturar' in col_map_fat_temp:
        df_fat_raw = df_fat_raw[df_fat_raw[col_map_fat_temp['permitefaturar']] == 'S']
    df_fat_filtrado = df_fat_raw[df_fat_raw['numConhec'].isin(viagens_filtradas_ids)]

    # 5. Retorna o dicionário completo com todos os DataFrames necessários
    return {
        "df_viagens_cliente": df_viagens_cliente,
        "df_despesas_filtrado": df_despesas_filtrado,
        "df_fat_filtrado": df_fat_filtrado,
        "df_contas_pagar_raw": df_contas_pagar_raw,
        "df_contas_receber_raw": df_contas_receber_raw,
        "df_flags": df_flags,
        "df_despesas_raw": df_despesas_raw  # Inclui o DF de despesas raw para cálculos de Tipo D
    }
   
def get_dashboard_summary(apartamento_id: int, start_date: datetime = None, end_date: datetime = None, placa_filter: str = "Todos", filial_filter: list = None, tipo_negocio_filter: str = "Todos") -> dict:
    """
    Calcula os KPIs para o dashboard principal usando a nova função mestre de filtragem.
    """
    # Passo 1: Sincroniza os grupos de despesa antes de qualquer cálculo.
    sync_expense_groups(apartamento_id)
    
    # Passo 2: Busca todos os dados já filtrados da função mestre.
    filtered_data = _obter_dados_filtrados_mestre(apartamento_id, start_date, end_date, placa_filter, filial_filter, tipo_negocio_filter)
    df_viagens_cliente = filtered_data["df_viagens_cliente"]
    df_despesas_filtrado = filtered_data["df_despesas_filtrado"]
    df_fat_filtrado = filtered_data["df_fat_filtrado"]
    df_contas_pagar_raw = filtered_data["df_contas_pagar_raw"]
    df_contas_receber_raw = filtered_data["df_contas_receber_raw"]
    df_flags = filtered_data["df_flags"]
    df_despesas_raw = filtered_data["df_despesas_raw"]

    # Passo 3: O restante dos cálculos permanece o mesmo, pois já operam sobre dados filtrados.
    summary = {}
    col_map_fat = _get_case_insensitive_column_map(df_fat_filtrado.columns)
    
    if not df_fat_filtrado.empty and 'freteempresa' in col_map_fat:
        summary['faturamento_total_viagens'] = df_fat_filtrado[col_map_fat['freteempresa']].sum()
        summary['faturamento_conhecimentos'] = df_fat_filtrado['numConhec'].unique().tolist()
    else:
        summary['faturamento_total_viagens'] = 0
        summary['faturamento_conhecimentos'] = []

    expense_data = _get_final_expense_dataframes(df_viagens_cliente, df_despesas_filtrado, df_flags)
    df_custos = expense_data['custos']
    df_despesas_gerais = expense_data['despesas']
    summary['custo_total_viagem'] = df_custos['valor_calculado'].sum() if not df_custos.empty else 0
    summary['total_despesas_gerais'] = df_despesas_gerais['valor_calculado'].sum() if not df_despesas_gerais.empty else 0
    
    df_despesas_sem_placa = apply_filters_to_df(df_despesas_raw, start_date, end_date, "Todos", filial_filter)
    col_map_despesas_geral = _get_case_insensitive_column_map(df_despesas_sem_placa.columns)
    df_tipo_d_bruto = pd.DataFrame()
    if 'ved' in col_map_despesas_geral:
        df_tipo_d_bruto = df_despesas_sem_placa[df_despesas_sem_placa[col_map_despesas_geral['ved']] == 'D'].copy()
    
    soma_bruta_tipo_d = 0
    if not df_tipo_d_bruto.empty:
        df_tipo_d_com_flags = pd.merge(df_tipo_d_bruto, df_flags, left_on=col_map_despesas_geral.get('descgrupod'), right_on='group_name', how='left')
        df_tipo_d_final_para_soma = df_tipo_d_com_flags[df_tipo_d_com_flags['incluir_em_tipo_d'] == True].copy()
        if not df_tipo_d_final_para_soma.empty:
            if all(c in col_map_despesas_geral for c in ['serie', 'liquido', 'vlcontabil']):
                 df_tipo_d_final_para_soma.loc[:, 'valor_calculado'] = np.where(df_tipo_d_final_para_soma[col_map_despesas_geral.get('serie')] == 'RQ', df_tipo_d_final_para_soma[col_map_despesas_geral.get('liquido')], df_tipo_d_final_para_soma[col_map_despesas_geral.get('vlcontabil')])
                 soma_bruta_tipo_d = df_tipo_d_final_para_soma['valor_calculado'].sum()

    valor_final_tipo_d = soma_bruta_tipo_d
    if placa_filter and placa_filter != 'Todos':
        placas_com_tipos = get_unique_plates_with_types(apartamento_id)
        lista_placas_proprias = [item['placa'] for item in placas_com_tipos if item['tipo'] == 'Próprio']
        if placa_filter in lista_placas_proprias:
            contagem_veiculos_proprios = len(lista_placas_proprias)
            valor_final_tipo_d = (soma_bruta_tipo_d / contagem_veiculos_proprios) if contagem_veiculos_proprios > 0 else 0
        else:
            valor_final_tipo_d = 0
    summary['total_despesas_tipo_d'] = valor_final_tipo_d

    if not df_contas_pagar_raw.empty:
        col_map_cp = _get_case_insensitive_column_map(df_contas_pagar_raw.columns)
        df_cp_pendentes = df_contas_pagar_raw[pd.to_numeric(df_contas_pagar_raw.get(col_map_cp.get('codtransacao')), errors='coerce').fillna(0) == 0]
        summary['saldo_contas_a_pagar_pendentes'] = df_cp_pendentes[col_map_cp.get('liquidoitemnota')].sum() if 'liquidoitemnota' in col_map_cp else 0
    else:
        summary['saldo_contas_a_pagar_pendentes'] = 0
        
    if not df_contas_receber_raw.empty:
        col_map_cr = _get_case_insensitive_column_map(df_contas_receber_raw.columns)
        df_cr_pendentes = df_contas_receber_raw[pd.to_numeric(df_contas_receber_raw.get(col_map_cr.get('codtransacao')), errors='coerce').fillna(0) == 0]
        summary['saldo_contas_a_receber_pendentes'] = df_cr_pendentes[col_map_cr.get('valorvenc')].sum() if 'valorvenc' in col_map_cr else 0
    else:
        summary['saldo_contas_a_receber_pendentes'] = 0
        
    custo_operacional_total = summary['custo_total_viagem'] + summary['total_despesas_gerais'] + summary['total_despesas_tipo_d']
    summary['saldo_geral'] = summary['faturamento_total_viagens'] - custo_operacional_total
    summary['margem_frete'] = (summary['saldo_geral'] / summary['faturamento_total_viagens'] * 100) if summary.get('faturamento_total_viagens', 0) > 0 else 0
    
    return summary

# Substitua esta função em data_manager.py

def get_monthly_summary(apartamento_id: int, start_date, end_date, placa_filter, filial_filter, tipo_negocio_filter) -> pd.DataFrame:
    """
    Calcula os dados para o gráfico mensal/diário usando a nova função mestre de filtragem.
    """
    periodo_format = 'M'
    if start_date and end_date and (end_date - start_date).days <= 62:
        periodo_format = 'D'

    # Busca os dados já filtrados da função mestre.
    filtered_data = _obter_dados_filtrados_mestre(apartamento_id, start_date, end_date, placa_filter, filial_filter, tipo_negocio_filter)
    df_viagens_cliente = filtered_data["df_viagens_cliente"]
    df_despesas_filtrado = filtered_data["df_despesas_filtrado"]
    df_fat_filtrado = filtered_data["df_fat_filtrado"]
    df_flags = filtered_data["df_flags"]
    
    # O restante dos cálculos para agrupar por período permanece o mesmo.
    col_map_viagens_cli = _get_case_insensitive_column_map(df_viagens_cliente.columns)
    col_map_fat = _get_case_insensitive_column_map(df_fat_filtrado.columns)
    
    faturamento = pd.Series(dtype=float)
    if not df_viagens_cliente.empty and not df_fat_filtrado.empty and 'dataviagemmotorista' in col_map_viagens_cli and 'freteempresa' in col_map_fat:
        df_viagens_essencial = df_viagens_cliente[[col_map_viagens_cli['numconhec'], col_map_viagens_cli['dataviagemmotorista']]]
        df_fat_essencial = df_fat_filtrado[['numConhec', col_map_fat['freteempresa']]]
        df_faturamento_para_grafico = pd.merge(df_viagens_essencial, df_fat_essencial, on='numConhec', how='inner')
        df_faturamento_para_grafico['Periodo'] = pd.to_datetime(df_faturamento_para_grafico[col_map_viagens_cli['dataviagemmotorista']], errors='coerce').dt.to_period(periodo_format)
        df_faturamento_para_grafico.dropna(subset=['Periodo'], inplace=True)
        faturamento = df_faturamento_para_grafico.groupby('Periodo')[col_map_fat['freteempresa']].sum()
    faturamento.name = 'Faturamento'

    expense_data = _get_final_expense_dataframes(df_viagens_cliente, df_despesas_filtrado, df_flags)
    df_custos = expense_data['custos']
    df_despesas_gerais = expense_data['despesas']
    
    custos_agrupados = pd.Series(dtype=float)
    if not df_custos.empty:
        mapa_colunas_custo = _get_case_insensitive_column_map(df_custos.columns)
        if 'datacontrole' in mapa_colunas_custo and 'valor_calculado' in mapa_colunas_custo:
            nome_coluna_data = mapa_colunas_custo['datacontrole']
            df_custos.loc[:, nome_coluna_data] = pd.to_datetime(df_custos[nome_coluna_data], errors='coerce')
            df_custos.dropna(subset=[nome_coluna_data], inplace=True)
            if not df_custos.empty:
                custos_agrupados = df_custos.groupby(df_custos[nome_coluna_data].dt.to_period(periodo_format))[mapa_colunas_custo['valor_calculado']].sum()
    custos_agrupados.name = 'Custo'
    
    despesas_agrupadas = pd.Series(dtype=float)
    if not df_despesas_gerais.empty:
        mapa_colunas_despesa = _get_case_insensitive_column_map(df_despesas_gerais.columns)
        if 'datacontrole' in mapa_colunas_despesa and 'valor_calculado' in mapa_colunas_despesa:
            nome_coluna_data = mapa_colunas_despesa['datacontrole']
            df_despesas_gerais.loc[:, nome_coluna_data] = pd.to_datetime(df_despesas_gerais[nome_coluna_data], errors='coerce')
            df_despesas_gerais.dropna(subset=[nome_coluna_data], inplace=True)
            if not df_despesas_gerais.empty:
                despesas_agrupadas = df_despesas_gerais.groupby(df_despesas_gerais[nome_coluna_data].dt.to_period(periodo_format))[mapa_colunas_despesa['valor_calculado']].sum()
    despesas_agrupadas.name = 'DespesasGerais'
        
    monthly_df = pd.concat([faturamento, custos_agrupados, despesas_agrupadas], axis=1).fillna(0)
    
    if not monthly_df.empty:
        monthly_df = monthly_df.reset_index()
        monthly_df.rename(columns={'index': 'Periodo'}, inplace=True)
        monthly_df['Periodo'] = monthly_df['Periodo'].dt.to_timestamp()
        date_format_str = '%d/%m/%Y' if periodo_format == 'D' else '%b/%Y'
        monthly_df['PeriodoLabel'] = monthly_df['Periodo'].dt.strftime(date_format_str)
        monthly_df = monthly_df.sort_values(by='Periodo', ascending=True)
            
    return monthly_df

def sync_expense_groups(apartamento_id: int):
    """
    Sincroniza os grupos de despesa, adicionando novos grupos encontrados nos dados,
    mas NUNCA removendo os existentes.
    """
    print(f"Sincronizando grupos de despesa para o apartamento {apartamento_id}...")
    
    df_despesas = get_data_as_dataframe("relFilDespesasGerais", apartamento_id)
    col_map = _get_case_insensitive_column_map(df_despesas.columns)
    
    grupos_dinamicos = set()
    if not df_despesas.empty and 'descgrupod' in col_map:
        for grupo in df_despesas[col_map['descgrupod']].dropna().unique():
            grupos_dinamicos.add(grupo)
            
    grupos_especiais = {'VALOR QUEBRA', 'COMISSÃO DE MOTORISTA'}
    todos_os_grupos_encontrados = grupos_dinamicos.union(grupos_especiais)
    
    if not todos_os_grupos_encontrados:
        print("Nenhum grupo de despesa para sincronizar.")
        return

    try:
        with engine.connect() as conn:
            with conn.begin() as trans:
                sql_insert = text("""
                    INSERT INTO "static_expense_groups" (apartamento_id, group_name, is_despesa)
                    VALUES (:apt_id, :group_name, 'S')
                    ON CONFLICT (apartamento_id, group_name) DO NOTHING
                """)
                for group_name in todos_os_grupos_encontrados:
                    if group_name:
                        conn.execute(sql_insert, {"apt_id": apartamento_id, "group_name": group_name})

        print("Sincronização de grupos concluída: Novos grupos foram adicionados, existentes foram preservados.")
    except Exception as e:
        print(f"ERRO CRÍTICO durante a sincronização de grupos: {e}")

def get_all_group_flags(apartamento_id: int):

    try:
        with db.engine.connect() as conn:
            query = text('SELECT "group_name", "is_despesa", "is_custo_viagem", "incluir_em_tipo_d" FROM "static_expense_groups" WHERE "apartamento_id" = :apt_id')
            df = pd.read_sql(query, conn, params={"apt_id": apartamento_id})
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
    table_names = [
        "relFilViagensFatCliente", 
        "relFilDespesasGerais", 
        "relFilContasPagarDet", 
        "relFilContasReceber",
        "relFilViagensCliente"
    ]

    all_dfs = [get_data_as_dataframe(name, apartamento_id) for name in table_names]
    filiais = pd.Series(dtype=str)
    
    for df in all_dfs:
        col_map = _get_case_insensitive_column_map(df.columns)
        for col_lower in ['nomefilial', 'nomefil']:
            if col_lower in col_map:
                filiais_validas = df[col_map[col_lower]].dropna().astype(str)
                filiais = pd.concat([filiais, filiais_validas])

    if filiais.empty:
        return ["Todos"]
    
    unique_filiais = sorted(list(set(f for f in filiais.unique() if f and f.strip())))

    return ["Todos"] + unique_filiais



def get_faturamento_details_dashboard_data(apartamento_id: int, start_date, end_date, placa_filter, filial_filter):
    """
    Prepara e calcula todos os dados para a página de Análise Detalhada de Faturamento.
    VERSÃO CORRIGIDA: Garante que o filtro de data seja aplicado corretamente no gráfico de evolução e que os dados sejam ordenados.
    """
    dashboard_data = {}
    
    # --- Passo 1: Carregar todos os dados brutos necessários ---
    df_fat_raw = get_data_as_dataframe("relFilViagensFatCliente", apartamento_id)
    df_viagens_raw = get_data_as_dataframe("relFilViagensCliente", apartamento_id)
    df_despesas_raw = get_data_as_dataframe("relFilDespesasGerais", apartamento_id)
    df_flags = get_all_group_flags(apartamento_id)
    flags_dict = df_flags.set_index('group_name').to_dict('index') if not df_flags.empty else {}

    # --- Passo 2: Aplicar os filtros de interface UMA VEZ ---
    df_viagens_cliente = apply_filters_to_df(df_viagens_raw, start_date, end_date, placa_filter, filial_filter)
    df_despesas_filtrado = apply_filters_to_df(df_despesas_raw, start_date, end_date, placa_filter, filial_filter)

    if df_viagens_cliente.empty:
        return {} # Se não há viagens no período, não há nada para mostrar

    # --- Passo 3: Calcular dados para o Gráfico de Evolução ---
    periodo = 'D' if start_date and end_date and (end_date - start_date).days <= 62 else 'M'
    
    # Prepara Faturamento
    viagens_ids = df_viagens_cliente['numConhec'].unique()
    df_fat_filtrado = df_fat_raw[df_fat_raw['numConhec'].isin(viagens_ids)]
    col_map_viagens_cli = _get_case_insensitive_column_map(df_viagens_cliente.columns)
    col_map_fat = _get_case_insensitive_column_map(df_fat_filtrado.columns)
    
    fat_evolucao = pd.Series(dtype=float)
    if not df_fat_filtrado.empty and 'dataviagemmotorista' in col_map_viagens_cli:
        df_viagens_essencial = df_viagens_cliente[[col_map_viagens_cli['numconhec'], col_map_viagens_cli['dataviagemmotorista']]]
        df_fat_essencial = df_fat_filtrado[['numConhec', col_map_fat['freteempresa']]]
        df_faturamento_para_grafico = pd.merge(df_viagens_essencial, df_fat_essencial, on='numConhec', how='inner')
        df_faturamento_para_grafico['Periodo'] = pd.to_datetime(df_faturamento_para_grafico[col_map_viagens_cli['dataviagemmotorista']]).dt.to_period(periodo)
        fat_evolucao = df_faturamento_para_grafico.groupby('Periodo')[col_map_fat['freteempresa']].sum()

    # Prepara Custo
    expense_data = _get_final_expense_dataframes(df_viagens_cliente, df_despesas_filtrado, df_flags)
    df_custos = expense_data['custos']
    custo_evolucao = pd.Series(dtype=float)
    if not df_custos.empty:
        mapa_colunas_custo = _get_case_insensitive_column_map(df_custos.columns)
        if 'datacontrole' in mapa_colunas_custo and 'valor_calculado' in mapa_colunas_custo:
            df_custos['Periodo'] = pd.to_datetime(df_custos[mapa_colunas_custo['datacontrole']]).dt.to_period(periodo)
            custo_evolucao = df_custos.groupby('Periodo')[mapa_colunas_custo['valor_calculado']].sum()

    # Combina e formata os dados para o gráfico
    evolucao_df = pd.DataFrame({'Faturamento': fat_evolucao, 'Custo': custo_evolucao}).fillna(0).reset_index()
    evolucao_df.rename(columns={'index': 'Periodo'}, inplace=True)
    evolucao_df = evolucao_df.sort_values(by='Periodo') # GARANTE A ORDEM CRONOLÓGICA
    evolucao_df['Periodo'] = evolucao_df['Periodo'].astype(str)
    dashboard_data['evolucao_faturamento_custo'] = evolucao_df.to_dict('records')

    # --- Passo 4: Calcular dados para os outros gráficos (usando os mesmos dados já filtrados) ---
    
    if not df_fat_filtrado.empty and 'nomecliente' in col_map_fat and 'freteempresa' in col_map_fat:
        top_clientes = df_fat_filtrado.groupby(col_map_fat['nomecliente'])[col_map_fat['freteempresa']].sum().sort_values(ascending=False).reset_index()
        dashboard_data['top_clientes'] = top_clientes.to_dict(orient='records')

    if not df_fat_filtrado.empty and 'nomefilial' in col_map_fat and 'freteempresa' in col_map_fat:
        fat_filial = df_fat_filtrado.groupby(col_map_fat['nomefilial'])[col_map_fat['freteempresa']].sum().reset_index()
        dashboard_data['faturamento_filial'] = fat_filial.to_dict(orient='records')

    if 'cidorigemformat' in col_map_viagens_cli and 'ciddestinoformat' in col_map_viagens_cli:
        df_viagens_cliente['rota'] = df_viagens_cliente[col_map_viagens_cli['cidorigemformat']] + ' -> ' + df_viagens_cliente[col_map_viagens_cli['ciddestinoformat']]
        top_rotas = df_viagens_cliente['rota'].value_counts().reset_index()
        top_rotas.columns = ['rota', 'contagem']
        dashboard_data['top_rotas'] = top_rotas.head(10).to_dict(orient='records')
        
        if 'pesosaida' in col_map_viagens_cli:
            volume_rota = df_viagens_cliente.groupby('rota')[col_map_viagens_cli['pesosaida']].sum().sort_values(ascending=False).reset_index()
            dashboard_data['volume_por_rota'] = volume_rota.head(10).to_dict(orient='records')
    
    if 'placaveiculo' in col_map_viagens_cli:
        viagens_veiculo = df_viagens_cliente[col_map_viagens_cli['placaveiculo']].value_counts().reset_index()
        viagens_veiculo.columns = ['placa', 'contagem']
        dashboard_data['viagens_por_veiculo'] = viagens_veiculo.head(10).to_dict(orient='records')
        
    if 'nomemotorista' in col_map_viagens_cli and 'freteempresa' in col_map_viagens_cli:
        fat_motorista = df_viagens_cliente.groupby(col_map_viagens_cli['nomemotorista'])[col_map_viagens_cli['freteempresa']].sum().sort_values(ascending=False).reset_index()
        fat_motorista.rename(columns={col_map_viagens_cli['nomemotorista']: 'nomeMotorista', col_map_viagens_cli['freteempresa']: 'faturamento'}, inplace=True)
        dashboard_data['faturamento_motorista'] = fat_motorista.head(10).to_dict(orient='records')

    if 'descricaomercadoria' in col_map_viagens_cli and 'freteempresa' in col_map_viagens_cli:
        fat_por_mercadoria = df_viagens_cliente.groupby(col_map_viagens_cli['descricaomercadoria'])[col_map_viagens_cli['freteempresa']].sum().sort_values(ascending=False)
        if len(fat_por_mercadoria) > 7:
            top_7 = fat_por_mercadoria.nlargest(7)
            outros = pd.Series([fat_por_mercadoria.nsmallest(len(fat_por_mercadoria) - 7).sum()], index=['Outros'])
            fat_final = pd.concat([top_7, outros])
        else:
            fat_final = fat_por_mercadoria
        df_resultado = fat_final.reset_index()
        df_resultado.columns = ['mercadoria', 'faturamento']
        dashboard_data['faturamento_por_mercadoria'] = df_resultado.to_dict('records')

    return dashboard_data
def ler_configuracoes_robo(apartamento_id: int):
    df = get_data_as_dataframe("configuracoes_robo", apartamento_id)
    if df.empty:
        return {}
    # Esta tabela tem nomes de coluna fixos, então a conversão original é segura
    df.columns = [col.lower() for col in df.columns]
    return pd.Series(df.valor.values, index=df.chave).to_dict()

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
                        conn.execute(sql, {
                            "apt_id": apartamento_id,
                            "chave": chave,
                            "valor": str(valor)
                        })
        print(f"Configurações salvas com sucesso para o apartamento {apartamento_id}.")
    except Exception as e:
        print(f"ERRO CRÍTICO ao salvar configurações para o apartamento {apartamento_id}: {e}")

def get_users_for_apartment(apartamento_id: int):
    from app import app 
    super_admin_email = app.config.get('SUPER_ADMIN_EMAIL')
    with engine.connect() as conn:
        sql = text("""
            SELECT id, nome, email, role 
            FROM usuarios 
            WHERE apartamento_id = :apt_id AND email != :super_admin_email
        """)
        df = pd.read_sql(sql, conn, params={"apt_id": apartamento_id, "super_admin_email": super_admin_email})
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
            df_apartamentos = pd.read_sql('SELECT id, nome_empresa, status, data_criacao, slug FROM apartamentos', conn)
            if df_apartamentos.empty:
                return []
            apartamentos_list = df_apartamentos.to_dict(orient='records')
            for apt in apartamentos_list:
                total_registos = 0
                apt_id = apt['id']
                for table in data_tables:
                    if db.table_exists(table):
                        query = text(f'SELECT COUNT(*) FROM "{table}" WHERE "apartamento_id" = :apt_id')
                        result = conn.execute(query, {"apt_id": apt_id})
                        count = result.scalar_one_or_none()
                        if count:
                            total_registos += count
                apt['total_registos'] = total_registos
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
    Busca as flags de classificação e adiciona colunas booleanas que indicam
    se o grupo contém despesas com VED = 'D' ou VED = 'V'.
    VERSÃO CORRIGIDA: Garante que 'Comissão' e 'Quebra' sempre mostrem as flags de Custo/Despesa.
    """
    df_flags = get_all_group_flags(apartamento_id)
    df_despesas_raw = get_data_as_dataframe("relFilDespesasGerais", apartamento_id)

    if df_flags.empty:
        return pd.DataFrame()

    # Define as colunas padrão como False
    df_flags['has_tipo_d'] = False
    df_flags['has_tipo_v'] = False

    if not df_despesas_raw.empty:
        col_map_desp = _get_case_insensitive_column_map(df_despesas_raw.columns)
        
        if 'ved' in col_map_desp and 'descgrupod' in col_map_desp:
            grupos_com_tipo_d = df_despesas_raw[df_despesas_raw[col_map_desp['ved']] == 'D'][col_map_desp['descgrupod']].unique()
            grupos_com_tipo_v = df_despesas_raw[df_despesas_raw[col_map_desp['ved']] == 'V'][col_map_desp['descgrupod']].unique()

            df_flags['has_tipo_d'] = df_flags['group_name'].isin(grupos_com_tipo_d)
            df_flags['has_tipo_v'] = df_flags['group_name'].isin(grupos_com_tipo_v)

    # --- INÍCIO DA CORREÇÃO ---
    # Força a flag 'has_tipo_v' a ser True para os grupos especiais,
    # garantindo que os checkboxes de Custo/Despesa sempre apareçam para eles.
    grupos_especiais = ['COMISSÃO DE MOTORISTA', 'VALOR QUEBRA']
    df_flags.loc[df_flags['group_name'].isin(grupos_especiais), 'has_tipo_v'] = True
    # --- FIM DA CORREÇÃO ---
    
    return df_flags

def get_unique_plates_with_types(apartamento_id: int) -> list:
    """
    Busca todas as placas únicas e as classifica em 'Próprio', 'Terceiro', 
    'Agregado', ou 'Apoio', retornando uma lista de dicionários.
    """
    placas_classificadas = {}

    # 1. Classifica veículos de 'relFilViagensCliente' (Próprio, Terceiro, Agregado)
    df_viagens = get_data_as_dataframe("relFilViagensCliente", apartamento_id)
    if not df_viagens.empty:
        col_map_viagens = _get_case_insensitive_column_map(df_viagens.columns)
        if all(c in col_map_viagens for c in ['placaveiculo', 'tipofrete']):
            for index, row in df_viagens.iterrows():
                placa = row[col_map_viagens['placaveiculo']]
                tipo_frete = row[col_map_viagens['tipofrete']]
                if placa and pd.notna(placa):
                    placa_limpa = placa.strip()
                    if tipo_frete == 'P':
                        placas_classificadas[placa_limpa] = 'Próprio'
                    elif tipo_frete == 'T':
                        placas_classificadas[placa_limpa] = 'Terceiro'
                    elif tipo_frete == 'A':
                        placas_classificadas[placa_limpa] = 'Agregado'

    # 2. Classifica veículos de 'relFilDespesasGerais' (Apoio)
    df_despesas = get_data_as_dataframe("relFilDespesasGerais", apartamento_id)
    if not df_despesas.empty:
        col_map_despesas = _get_case_insensitive_column_map(df_despesas.columns)
        if all(c in col_map_despesas for c in ['placaveiculo', 'veiculoproprio']):
            df_apoio = df_despesas[df_despesas[col_map_despesas['veiculoproprio']] == 'F']
            for placa in df_apoio[col_map_despesas['placaveiculo']].dropna().unique():
                placa_limpa = placa.strip()
                # Só adiciona se já não tiver uma classificação mais forte (ex: Próprio)
                if placa_limpa not in placas_classificadas:
                    placas_classificadas[placa_limpa] = 'Apoio'

    # 3. Formata a saída para o frontend
    lista_final = [{'placa': placa, 'tipo': tipo} for placa, tipo in placas_classificadas.items()]

    # Ordena por tipo e depois por placa
    lista_final.sort(key=lambda x: (x['tipo'], x['placa']))

    return lista_final



# SUBSTITUA ESTA FUNÇÃO EM data_manager.py

def get_despesas_details_dashboard_data(apartamento_id: int, start_date, end_date, placa_filter, filial_filter):
    """
    Prepara e calcula todos os dados para a página de Análise Detalhada de Despesas.
    VERSÃO CORRIGIDA: Corrige o NameError para df_tipo_d.
    """
    dashboard_data = {}
    
    # 1. Carrega e filtra os dados de base
    df_viagens_raw = get_data_as_dataframe("relFilViagensCliente", apartamento_id)
    df_despesas_raw = get_data_as_dataframe("relFilDespesasGerais", apartamento_id)
    df_flags = get_all_group_flags(apartamento_id)

    df_viagens_cliente = apply_filters_to_df(df_viagens_raw, start_date, end_date, placa_filter, filial_filter)
    df_despesas_filtrado = apply_filters_to_df(df_despesas_raw, start_date, end_date, placa_filter, filial_filter)

    # --- INÍCIO DA CORREÇÃO ---
    # 2. Chama a função auxiliar e extrai TODOS os DataFrames necessários
    expense_data = _get_final_expense_dataframes(df_viagens_cliente, df_despesas_filtrado, df_flags)
    df_custos = expense_data['custos']
    df_despesas_gerais = expense_data['despesas']
    df_tipo_d = expense_data['tipo_d'] # ESTA LINHA ESTAVA FALTANDO
    # --- FIM DA CORREÇÃO ---
    
    col_map = _get_case_insensitive_column_map(df_despesas_filtrado.columns) if not df_despesas_filtrado.empty else {}

    # 3. Gráfico de Composição: Junta os 3 DataFrames
    df_composicao_total = pd.concat([
        df_custos.assign(categoria='Custo de Viagem'),
        df_despesas_gerais.assign(categoria='Despesa Geral'),
        df_tipo_d.assign(categoria='Despesa Tipo D')
    ], ignore_index=True)
    
    if not df_composicao_total.empty and 'nomefil' in col_map:
        df_grouped = df_composicao_total.groupby([col_map['nomefil'], 'categoria'])['valor_calculado'].sum().unstack(fill_value=0)
        
        # Lógica de Rateio (para sobrescrever o valor de Tipo D se necessário)
        if placa_filter and placa_filter != 'Todos':
            placas_com_tipos = get_unique_plates_with_types(apartamento_id)
            lista_placas_proprias = [item['placa'] for item in placas_com_tipos if item['tipo'] == 'Próprio']
            
            if placa_filter in lista_placas_proprias:
                df_despesas_sem_placa = apply_filters_to_df(df_despesas_raw, start_date, end_date, "Todos", filial_filter)
                soma_bruta_tipo_d = _get_final_expense_dataframes(pd.DataFrame(), df_despesas_sem_placa, df_flags)['tipo_d']['valor_calculado'].sum()
                contagem_veiculos_proprios = len(lista_placas_proprias)
                valor_rateado_tipo_d = (soma_bruta_tipo_d / contagem_veiculos_proprios) if contagem_veiculos_proprios > 0 else 0
                
                filial_do_veiculo = None
                if not df_despesas_filtrado.empty and 'nomefil' in col_map:
                    filiais_no_filtro = df_despesas_filtrado[col_map['nomefil']].unique()
                    if len(filiais_no_filtro) > 0:
                        filial_do_veiculo = filiais_no_filtro[0]
                
                if filial_do_veiculo:
                    if filial_do_veiculo not in df_grouped.index: df_grouped.loc[filial_do_veiculo] = 0
                    if 'Despesa Tipo D' not in df_grouped.columns: df_grouped['Despesa Tipo D'] = 0
                    df_grouped.loc[filial_do_veiculo, 'Despesa Tipo D'] = valor_rateado_tipo_d
                    

        if not df_grouped.empty:
            colors = {'Custo de Viagem': 'rgba(230, 126, 34, 0.7)', 'Despesa Geral': 'rgba(231, 76, 60, 0.7)', 'Despesa Tipo D': 'rgba(142, 68, 173, 0.7)'}
            datasets = []
            for categoria in ['Custo de Viagem', 'Despesa Geral', 'Despesa Tipo D']:
                if categoria in df_grouped.columns:
                    datasets.append({'label': categoria, 'data': df_grouped[categoria].tolist(), 'backgroundColor': colors.get(categoria)})
            dashboard_data['despesas_por_filial_e_grupo'] = {'labels': df_grouped.index.tolist(), 'datasets': datasets}

    # 4. Outros gráficos
    if 'descgrupod' in col_map and not df_despesas_gerais.empty:
        grupo_df = df_despesas_gerais.groupby(col_map['descgrupod'])['valor_calculado'].sum().nlargest(10).reset_index()
        grupo_df.rename(columns={col_map['descgrupod']: 'descSuperGrupoD', 'valor_calculado': 'vlcontabil'}, inplace=True)
        dashboard_data['despesa_super_grupo'] = grupo_df.to_dict(orient='records')
        
    if 'nomefil' in col_map and not df_despesas_gerais.empty:
        filial_df = df_despesas_gerais.groupby(col_map['nomefil'])['valor_calculado'].sum().reset_index()
        filial_df.rename(columns={col_map['nomefil']: 'nomeFil', 'valor_calculado': 'vlcontabil'}, inplace=True)
        dashboard_data['despesa_filial'] = filial_df.to_dict(orient='records')

    df_despesas_completo = pd.concat([df_custos, df_despesas_gerais, df_tipo_d], ignore_index=True)
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
    
    if 'descgrupod' in col_map and 'placaveiculo' in col_map and 'quantidade' in col_map:
        df_combustivel_veiculo = df_despesas_completo[normalize_text(df_despesas_completo[col_map['descgrupod']]).str.contains("COMBUSTIVEL")].copy()
        if not df_combustivel_veiculo.empty:
            combustivel_agg = df_combustivel_veiculo.groupby(col_map['placaveiculo']).agg(
                valor_total=('valor_calculado', 'sum'),
                litros_total=(col_map['quantidade'], 'sum')
            ).sort_values(by='valor_total', ascending=False).reset_index()
            
            combustivel_agg.rename(columns={col_map['placaveiculo']: 'placaVeiculo'}, inplace=True)
            dashboard_data['combustivel_por_veiculo'] = combustivel_agg.to_dict(orient='records')

    return dashboard_data

def get_expense_audit_data(apartamento_id: int, start_date: datetime, end_date: datetime, placa_filter: str, filial_filter: list):
    """
    Coleta e organiza os dados de despesas em categorias para auditoria detalhada,
    com os números das notas/CT-es agrupados por nome de grupo. VERSÃO CORRIGIDA.
    """
    # 1. Carrega e filtra os dados de base
    df_viagens_raw = get_data_as_dataframe("relFilViagensCliente", apartamento_id)
    df_despesas_raw = get_data_as_dataframe("relFilDespesasGerais", apartamento_id)
    df_flags = get_all_group_flags(apartamento_id)

    df_viagens_cliente = apply_filters_to_df(df_viagens_raw, start_date, end_date, placa_filter, filial_filter)
    df_despesas_filtrado = apply_filters_to_df(df_despesas_raw, start_date, end_date, placa_filter, filial_filter)

    if df_despesas_filtrado.empty and df_viagens_cliente.empty:
        return {'custos': {}, 'despesas': {}, 'tipo_d': {}}

    # 2. Obtém os DataFrames finais de despesas já classificados
    expense_data = _get_final_expense_dataframes(df_viagens_cliente, df_despesas_filtrado, df_flags)
    df_custos = expense_data['custos']
    df_despesas_gerais = expense_data['despesas']
    df_tipo_d = expense_data['tipo_d']

    col_map = _get_case_insensitive_column_map(pd.concat([df_custos, df_despesas_gerais, df_tipo_d]))
    
    audit_data = {
        'custos': {},
        'despesas': {},
        'tipo_d': {}
    }

    def process_category(df_category: pd.DataFrame):
        """Função interna para processar e agrupar os dados de uma categoria."""
        if df_category.empty:
            return {}

        grouped_data = {}
        
        # Separa os grupos normais dos especiais (Quebra/Comissão)
        df_normal = df_category[~df_category[col_map['descgrupod']].isin(['VALOR QUEBRA', 'COMISSÃO DE MOTORISTA'])]
        df_special = df_category[df_category[col_map['descgrupod']].isin(['VALOR QUEBRA', 'COMISSÃO DE MOTORISTA'])]

        # Processa grupos normais (usando 'numnota')
        if not df_normal.empty and col_map.get('numnota') in df_normal.columns:
            normal_groups = df_normal.groupby(col_map['descgrupod'])[col_map['numnota']].unique().apply(list).to_dict()
            grouped_data.update(normal_groups)

        # Processa grupos especiais (usando 'numconhec')
        if not df_special.empty and col_map.get('numconhec') in df_special.columns:
            special_groups = df_special.groupby(col_map['descgrupod'])[col_map['numconhec']].unique().apply(list).to_dict()
            grouped_data.update(special_groups)
            
        return grouped_data

    # 3. Processa cada categoria
    audit_data['custos'] = process_category(df_custos)
    audit_data['despesas'] = process_category(df_despesas_gerais)
    
    # Tipo D nunca terá Quebra/Comissão, então o agrupamento é simples
    if not df_tipo_d.empty and col_map.get('numnota') in df_tipo_d.columns:
        audit_data['tipo_d'] = df_tipo_d.groupby(col_map['descgrupod'])[col_map['numnota']].unique().apply(list).to_dict()

    return audit_data
    def group_data(df, group_col, key_col):
        """Função auxiliar para agrupar e formatar os dados."""
        if df.empty or group_col not in df.columns or key_col not in df.columns:
            return {}
        
        # Agrupa pelo nome do grupo, coleta chaves únicas e converte para dicionário
        return df.groupby(group_col)[key_col].unique().apply(list).to_dict()

    # 3. Processa cada categoria
    # Para Custos e Despesas, a chave pode ser 'numnota' ou 'numconhec' (para Quebra/Comissão)
    key_col_custos_despesas = col_map.get('numnota', col_map.get('numconhec'))
    
    audit_data['custos'] = group_data(df_custos, col_map.get('descgrupod'), key_col_custos_despesas)
    audit_data['despesas'] = group_data(df_despesas_gerais, col_map.get('descgrupod'), key_col_custos_despesas)
    audit_data['tipo_d'] = group_data(df_tipo_d, col_map.get('descgrupod'), col_map.get('numnota'))

    return audit_data

# Em data_manager.py

def get_relatorio_viagem_data(apartamento_id: int, num_conhec: int):
    """
    Busca e consolida todos os dados para o Relatório de Viagem de um único CT-e.
    """
    # 1. Buscar dados principais da viagem e do faturamento
    df_viagens = get_data_as_dataframe("relFilViagensCliente", apartamento_id)
    df_fat = get_data_as_dataframe("relFilViagensFatCliente", apartamento_id)

    viagem = df_viagens[df_viagens['numConhec'] == num_conhec]
    faturamento = df_fat[df_fat['numConhec'] == num_conhec]

    if viagem.empty or faturamento.empty:
        return {"error": "Viagem não encontrada."}

    viagem_data = viagem.iloc[0].to_dict()
    fat_data = faturamento.iloc[0].to_dict()

    # 2. Buscar custos e despesas associados a esta viagem
    # ASSUNÇÃO IMPORTANTE: Como não há um link direto entre despesa e CT-e,
    # vamos associar as despesas pela placa do veículo na mesma data da viagem.
    df_despesas = get_data_as_dataframe("relFilDespesasGerais", apartamento_id)
    placa_viagem = viagem_data.get('placaVeiculo')
    data_viagem = pd.to_datetime(viagem_data.get('dataViagemMotorista')).date() if pd.notna(viagem_data.get('dataViagemMotorista')) else None
    
    custos_viagem = pd.DataFrame()
    if placa_viagem and data_viagem and not df_despesas.empty:
        df_despesas['dataControle'] = pd.to_datetime(df_despesas['dataControle'], errors='coerce').dt.date
        custos_viagem = df_despesas[
            (df_despesas['placaVeiculo'] == placa_viagem) &
            (df_despesas['dataControle'] == data_viagem)
        ].copy()

    # 3. Classificar custos e despesas usando a lógica que já temos
    df_flags = get_all_group_flags(apartamento_id)
    expense_data = _get_final_expense_dataframes(viagem, custos_viagem, df_flags)
    df_custos = expense_data.get('custos', pd.DataFrame())
    
    custos_por_grupo = {}
    if not df_custos.empty:
        custos_por_grupo = df_custos.groupby('descGrupoD')['valor_calculado'].sum().to_dict()

    # 4. Montar o dicionário final com todos os dados para o relatório
    total_receitas = fat_data.get('freteEmpresa', 0)
    total_custos = sum(custos_por_grupo.values())
    lucro = total_receitas - total_custos
    margem = (lucro / total_receitas * 100) if total_receitas > 0 else 0

    relatorio = {
        # Dados Principais
        "num_conhec": num_conhec,
        "data_viagem": viagem_data.get('dataViagemMotorista'),
        "placa_veiculo": placa_viagem,
        "motorista": viagem_data.get('nomeMotorista'),
        # Dados da Viagem
        "origem": viagem_data.get('cidOrigemFormat'),
        "destino": viagem_data.get('cidDestinoFormat'),
        "distancia": viagem_data.get('kmRodado'),
        "cliente": fat_data.get('nomeCliente'),
        "mercadoria": viagem_data.get('descricaoMercadoria'),
        "peso_saida": viagem_data.get('pesoSaida'),
        "peso_chegada": viagem_data.get('pesoChegada'),
        "quebra_kg": viagem_data.get('quantidadeQuebra'),
        # Receitas
        "frete_bruto": fat_data.get('freteEmpresa'),
        "adiantamentos": viagem_data.get('adiantamentoMotorista'),
        "taxas": fat_data.get('despesasadicionais'), # Exemplo, pode ser outra coluna
        "descontos": fat_data.get('outrosDescontos'),
        "total_receitas": total_receitas,
        # Custos
        "custos_detalhados": custos_por_grupo,
        "total_custos": total_custos,
        # Resultado
        "lucro_prejuizo": lucro,
        "margem": margem,
    }
    return relatorio