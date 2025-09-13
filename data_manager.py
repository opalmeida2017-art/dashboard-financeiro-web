# Forçando a atualização para o deploy

import pandas as pd
from sqlalchemy import text
from datetime import datetime
from slugify import slugify
import database as db
from database import engine 
import config
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
                    df_filtrado = df_filtrado[df_filtrado[original_date_col_name] >= start_date]
                if end_date:
                    df_filtrado = df_filtrado[df_filtrado[original_date_col_name] <= end_date]

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

def get_dashboard_summary(apartamento_id: int, start_date: datetime = None, end_date: datetime = None, placa_filter: str = "Todos", filial_filter: list = None) -> dict:
    summary = {}
    
    # --- Passo 1: Carregar todos os dados brutos necessários ---
    df_contas_pagar_raw = get_data_as_dataframe("relFilContasPagarDet", apartamento_id)
    df_contas_receber_raw = get_data_as_dataframe("relFilContasReceber", apartamento_id)
    df_viagens_raw = get_data_as_dataframe("relFilViagensCliente", apartamento_id)
    df_despesas_raw = get_data_as_dataframe("relFilDespesasGerais", apartamento_id)
    df_fat_raw = get_data_as_dataframe("relFilViagensFatCliente", apartamento_id)
    df_flags = get_all_group_flags(apartamento_id)
    flags_dict = df_flags.set_index('group_name').to_dict('index') if not df_flags.empty else {}

    # --- Passo 2: Lógica de Filtragem ---
    col_map_fat_temp = _get_case_insensitive_column_map(df_fat_raw.columns)
    if 'permitefaturar' in col_map_fat_temp:
        df_fat_raw = df_fat_raw[df_fat_raw[col_map_fat_temp['permitefaturar']] == 'S']

    df_viagens_cliente = apply_filters_to_df(df_viagens_raw, start_date, end_date, placa_filter, filial_filter)
    df_despesas_filtrado = apply_filters_to_df(df_despesas_raw, start_date, end_date, placa_filter, filial_filter)
    
    viagens_filtradas_ids = df_viagens_cliente['numConhec'].unique() if not df_viagens_cliente.empty else []
    df_fat_filtrado = df_fat_raw[df_fat_raw['numConhec'].isin(viagens_filtradas_ids)]
    
    # --- Passo 3: Cálculos dos KPIs ---
    col_map_viagens_cli = _get_case_insensitive_column_map(df_viagens_cliente.columns)
    col_map_despesas = _get_case_insensitive_column_map(df_despesas_filtrado.columns)
    col_map_fat = _get_case_insensitive_column_map(df_fat_filtrado.columns)

    summary['faturamento_total_viagens'] = df_fat_filtrado[col_map_fat['freteempresa']].sum() if not df_fat_filtrado.empty and 'freteempresa' in col_map_fat else 0

    # --- INÍCIO DA CORREÇÃO DEFINITIVA DO CÁLCULO DE CUSTO ---
    # Substituímos a lógica antiga e frágil por esta, que é robusta e idêntica à do gráfico.
    df_com_flags = pd.DataFrame()
    if not df_despesas_filtrado.empty and not df_flags.empty and 'descgrupod' in col_map_despesas:
        df_com_flags = pd.merge(df_despesas_filtrado, df_flags, left_on=col_map_despesas['descgrupod'], right_on='group_name', how='left')
    else:
        df_com_flags = df_despesas_filtrado.copy()
    
    if not df_com_flags.empty:
        df_com_flags['is_custo_viagem'] = df_com_flags['is_custo_viagem'].fillna('N')
        df_com_flags['is_despesa'] = df_com_flags['is_despesa'].fillna('S')

    df_custos = df_com_flags[df_com_flags['is_custo_viagem'] == 'S'].copy() if not df_com_flags.empty else pd.DataFrame()
    df_despesas_gerais = df_com_flags[df_com_flags['is_despesa'] == 'S'].copy() if not df_com_flags.empty else pd.DataFrame()
    # --- FIM DA CORREÇÃO ---
    
    # --- INÍCIO DA CORREÇÃO ISOLADA DA COMISSÃO ---
    # 1. Criamos uma cópia temporária do DataFrame de viagens para não afetar outros cálculos (como Valor Quebra).
    df_viagens_para_comissao = df_viagens_cliente.copy()

    # 2. Replicamos a operação de MERGE que existe na função do gráfico.
    #    Esta operação causa a duplicação de linhas que leva ao valor de comissão esperado.
    if not df_fat_filtrado.empty:
        df_faturamento_correto = df_fat_filtrado[['numConhec', 'freteEmpresa']]
        if 'freteEmpresa' in df_viagens_para_comissao.columns:
            df_viagens_para_comissao = df_viagens_para_comissao.drop(columns=['freteEmpresa'])
        df_viagens_para_comissao = pd.merge(df_viagens_para_comissao, df_faturamento_correto, on='numConhec', how='left')

    # 3. Agora, calculamos a comissão usando esta tabela temporária, corrigida e isolada.
    #    A fórmula (fretemotorista * comissao) não muda.
    total_comissao_motorista = 0
    col_map_comissao = _get_case_insensitive_column_map(df_viagens_para_comissao.columns)
    if not df_viagens_para_comissao.empty and all(c in col_map_comissao for c in ['tipofrete', 'fretemotorista', 'comissao']):
        df_comissao_base = df_viagens_para_comissao[(df_viagens_para_comissao[col_map_comissao['tipofrete']].astype(str) == 'P') & (pd.to_numeric(df_viagens_para_comissao[col_map_comissao['fretemotorista']], errors='coerce') > 0)].copy()
        if not df_comissao_base.empty:
            frete_motorista = pd.to_numeric(df_comissao_base[col_map_comissao['fretemotorista']], errors='coerce').fillna(0)
            percentual_comissao = pd.to_numeric(df_comissao_base[col_map_comissao['comissao']], errors='coerce').fillna(0)
            total_comissao_motorista = (frete_motorista * (percentual_comissao / 100)).sum()
    # --- FIM DA CORREÇÃO ISOLADA DA COMISSÃO ---

    valor_quebra_sum = df_viagens_cliente[col_map_viagens_cli['valorquebra']].sum() if not df_viagens_cliente.empty and 'valorquebra' in col_map_viagens_cli else 0
  
    col_map_custos = _get_case_insensitive_column_map(df_custos.columns)
    col_map_despesas_gerais = _get_case_insensitive_column_map(df_despesas_gerais.columns)
    
    custo_base = df_custos[col_map_custos['liquido']].sum() if not df_custos.empty and 'liquido' in col_map_custos else 0
    despesa_base = df_despesas_gerais[col_map_despesas_gerais['liquido']].sum() if not df_despesas_gerais.empty and 'liquido' in col_map_despesas_gerais else 0
    
    if flags_dict.get('VALOR QUEBRA', {}).get('is_custo_viagem') == 'S':
        custo_base += valor_quebra_sum
    elif flags_dict.get('VALOR QUEBRA', {}).get('is_despesa') == 'S':
        despesa_base += valor_quebra_sum
        
    comissao_flags = flags_dict.get('COMISSÃO DE MOTORISTA', {})
    if comissao_flags.get('is_custo_viagem') == 'S':
        custo_base += total_comissao_motorista
    elif comissao_flags.get('is_despesa') == 'S':
        despesa_base += total_comissao_motorista
    
    summary['custo_total_viagem'] = custo_base
    summary['total_despesas_gerais'] = despesa_base

    # O restante da função permanece inalterado...
    if not df_contas_pagar_raw.empty:
        col_map_cp = _get_case_insensitive_column_map(df_contas_pagar_raw.columns)
        df_cp_pendentes = df_contas_pagar_raw.copy()
        if 'codtransacao' in col_map_cp:
            df_cp_pendentes['codtransacao_numeric'] = pd.to_numeric(df_cp_pendentes[col_map_cp['codtransacao']], errors='coerce')
            df_cp_pendentes = df_cp_pendentes[df_cp_pendentes['codtransacao_numeric'].isnull() | (df_cp_pendentes['codtransacao_numeric'] == 0)]
        summary['saldo_contas_a_pagar_pendentes'] = df_cp_pendentes[col_map_cp['liquidoitemnota']].sum() if 'liquidoitemnota' in col_map_cp else 0
    else:
        summary['saldo_contas_a_pagar_pendentes'] = 0
        
    if not df_contas_receber_raw.empty:
        col_map_cr = _get_case_insensitive_column_map(df_contas_receber_raw.columns)
        df_cr_pendentes = df_contas_receber_raw.copy()
        if 'codtransacao' in col_map_cr:
            df_cr_pendentes['codtransacao_numeric'] = pd.to_numeric(df_cr_pendentes[col_map_cr['codtransacao']], errors='coerce')
            df_cr_pendentes = df_cr_pendentes[df_cr_pendentes['codtransacao_numeric'].isnull() | (df_cr_pendentes['codtransacao_numeric'] == 0)]
        summary['saldo_contas_a_receber_pendentes'] = df_cr_pendentes[col_map_cr['valorvenc']].sum() if 'valorvenc' in col_map_cr else 0
    else:
        summary['saldo_contas_a_receber_pendentes'] = 0

    custo_operacional_total = summary['custo_total_viagem'] + summary['total_despesas_gerais']
    summary['saldo_geral'] = summary['faturamento_total_viagens'] - custo_operacional_total
    summary['margem_frete'] = (summary['saldo_geral'] / summary['faturamento_total_viagens'] * 100) if summary.get('faturamento_total_viagens', 0) > 0 else 0
    
    return summary

# Em data_manager.py, substitua a função get_monthly_summary inteira por esta:

def get_monthly_summary(apartamento_id: int, start_date, end_date, placa_filter, filial_filter) -> pd.DataFrame:
    periodo_format = 'M'
    if start_date and end_date:
        duracao_dias = (end_date - start_date).days
        if duracao_dias <= 62:
            periodo_format = 'D'

    # Carrega os dados brutos
    df_viagens_raw = get_data_as_dataframe("relFilViagensCliente", apartamento_id)
    df_despesas_raw = get_data_as_dataframe("relFilDespesasGerais", apartamento_id)
    df_flags = get_all_group_flags(apartamento_id)
    flags_dict = df_flags.set_index('group_name').to_dict('index') if not df_flags.empty else {}
    
    # Aplica os filtros da tela
    df_viagens_cliente = apply_filters_to_df(df_viagens_raw, start_date, end_date, placa_filter, filial_filter)
    df_despesas_filtrado = apply_filters_to_df(df_despesas_raw, start_date, end_date, placa_filter, filial_filter)
    
    # Adiciona a lógica de faturamento corrigida que já implementamos
    df_fat_raw = get_data_as_dataframe("relFilViagensFatCliente", apartamento_id)
    col_map_fat_temp = _get_case_insensitive_column_map(df_fat_raw.columns)
    if 'permitefaturar' in col_map_fat_temp:
        df_fat_raw = df_fat_raw[df_fat_raw[col_map_fat_temp['permitefaturar']] == 'S']
    viagens_filtradas_ids = df_viagens_cliente['numConhec'].unique() if not df_viagens_cliente.empty else []
    df_fat_filtrado = df_fat_raw[df_fat_raw['numConhec'].isin(viagens_filtradas_ids)]
    if not df_fat_filtrado.empty:
        df_faturamento_correto = df_fat_filtrado[['numConhec', 'freteEmpresa']]
        if 'freteEmpresa' in df_viagens_cliente.columns:
            df_viagens_cliente = df_viagens_cliente.drop(columns=['freteEmpresa'])
        df_viagens_cliente = pd.merge(df_viagens_cliente, df_faturamento_correto, on='numConhec', how='left')

    # Lógica de classificação de custos e despesas
    col_map_despesas = _get_case_insensitive_column_map(df_despesas_filtrado.columns)
    df_com_flags = pd.DataFrame()
    if not df_despesas_filtrado.empty and not df_flags.empty and 'descgrupod' in col_map_despesas:
        df_com_flags = pd.merge(df_despesas_filtrado, df_flags, left_on=col_map_despesas['descgrupod'], right_on='group_name', how='left').copy()
    else:
        df_com_flags = df_despesas_filtrado.copy()
    
    if not df_com_flags.empty:
        df_com_flags['is_custo_viagem'] = df_com_flags['is_custo_viagem'].fillna('N')
        df_com_flags['is_despesa'] = df_com_flags['is_despesa'].fillna('S')
    
    df_custos = df_com_flags[df_com_flags['is_custo_viagem'] == 'S'].copy() if not df_com_flags.empty else pd.DataFrame()
    df_despesas_gerais = df_com_flags[df_com_flags['is_despesa'] == 'S'].copy() if not df_com_flags.empty else pd.DataFrame()

    col_map_viagens_cli = _get_case_insensitive_column_map(df_viagens_cliente.columns)
    comissao_df_data = pd.DataFrame()
    if not df_viagens_cliente.empty and all(c in col_map_viagens_cli for c in ['tipofrete', 'fretemotorista', 'comissao', 'dataviagemmotorista']):
        df_comissao_base = df_viagens_cliente[(df_viagens_cliente[col_map_viagens_cli['tipofrete']].astype(str) == 'P') & (pd.to_numeric(df_viagens_cliente[col_map_viagens_cli['fretemotorista']], errors='coerce') > 0)].copy()
        if not df_comissao_base.empty:
            df_comissao_base['liquido'] = pd.to_numeric(df_comissao_base[col_map_viagens_cli['fretemotorista']], errors='coerce').fillna(0) * (pd.to_numeric(df_comissao_base[col_map_viagens_cli['comissao']], errors='coerce').fillna(0) / 100)
            comissao_df_data = df_comissao_base[[col_map_viagens_cli['dataviagemmotorista'], 'liquido']].rename(columns={col_map_viagens_cli['dataviagemmotorista']: 'datacontrole'})
    
    col_map_viagens_fat = _get_case_insensitive_column_map(df_viagens_cliente.columns)
    quebra_df_data = pd.DataFrame()
    if not df_viagens_cliente.empty and 'valorquebra' in col_map_viagens_fat:
        df_quebra_base = df_viagens_cliente[[col_map_viagens_fat['dataviagemmotorista'], col_map_viagens_fat['valorquebra']]].copy()
        quebra_df_data = df_quebra_base.rename(columns={col_map_viagens_fat['valorquebra']: 'liquido', col_map_viagens_fat['dataviagemmotorista']: 'datacontrole'})
        
    if not quebra_df_data.empty:
        if flags_dict.get('VALOR QUEBRA', {}).get('is_custo_viagem') == 'S':
            df_custos = pd.concat([df_custos, quebra_df_data], ignore_index=True)
        elif flags_dict.get('VALOR QUEBRA', {}).get('is_despesa') == 'S':
            df_despesas_gerais = pd.concat([df_despesas_gerais, quebra_df_data], ignore_index=True)
    
    if not comissao_df_data.empty:
        comissao_flags = flags_dict.get('COMISSÃO DE MOTORISTA', {})
        if comissao_flags.get('is_custo_viagem') == 'S':
            df_custos = pd.concat([df_custos, comissao_df_data], ignore_index=True)
        elif comissao_flags.get('is_despesa') == 'S':
            df_despesas_gerais = pd.concat([df_despesas_gerais, comissao_df_data], ignore_index=True)

    faturamento = pd.Series(dtype=float)
    if not df_viagens_cliente.empty and 'dataviagemmotorista' in col_map_viagens_fat and 'freteempresa' in col_map_viagens_fat:
        df_viagens_cliente['Periodo'] = pd.to_datetime(df_viagens_cliente[col_map_viagens_fat['dataviagemmotorista']], errors='coerce', dayfirst=True).dt.to_period(periodo_format)
        faturamento = df_viagens_cliente.groupby('Periodo')[col_map_viagens_fat['freteempresa']].sum()
    faturamento.name = 'Faturamento'
    
    # --- INÍCIO DA CORREÇÃO FINAL (Tratamento de Datas com Formato Inválido) ---
    col_map_despesas_gerais = _get_case_insensitive_column_map(df_despesas_gerais.columns)
    despesas_agrupadas = pd.Series(dtype=float)
    if not df_despesas_gerais.empty and 'datacontrole' in col_map_despesas_gerais and 'liquido' in col_map_despesas_gerais:
        
        data_col_name = col_map_despesas_gerais['datacontrole']
        
        # 1. Converte a coluna de data, forçando erros de formato a virarem NaT (Data Inválida)
        df_despesas_gerais[data_col_name] = pd.to_datetime(df_despesas_gerais[data_col_name], errors='coerce')
        
        # 2. Se houver uma data de início no filtro, usa essa data para PREENCHER
        #    qualquer despesa que tenha ficado com a data inválida (NaT).
        if start_date:
            df_despesas_gerais[data_col_name].fillna(start_date, inplace=True)

        # 3. Agrupa os dados agora que a despesa de R$ 35,00 tem uma data válida para a soma.
        df_despesas_gerais.dropna(subset=[data_col_name], inplace=True)
        if not df_despesas_gerais.empty:
            df_despesas_gerais['Periodo'] = df_despesas_gerais[data_col_name].dt.to_period(periodo_format)
            despesas_agrupadas = df_despesas_gerais.groupby('Periodo')[col_map_despesas_gerais['liquido']].sum()

    despesas_agrupadas.name = 'DespesasGerais'
    # --- FIM DA CORREÇÃO ---

    col_map_custos = _get_case_insensitive_column_map(df_custos.columns)
    custos_agrupados = pd.Series(dtype=float)
    if not df_custos.empty and 'datacontrole' in col_map_custos and 'liquido' in col_map_custos:
        df_custos['Periodo'] = pd.to_datetime(df_custos[col_map_custos['datacontrole']], errors='coerce', dayfirst=True).dt.to_period(periodo_format)
        custos_agrupados = df_custos.groupby('Periodo')[col_map_custos['liquido']].sum()
    custos_agrupados.name = 'Custo'
        
    monthly_df = pd.concat([faturamento, custos_agrupados, despesas_agrupadas], axis=1).fillna(0)
    
    if monthly_df.empty:
        return monthly_df

    monthly_df = monthly_df.reset_index()
    monthly_df.rename(columns={'index': 'Periodo'}, inplace=True)
    
    monthly_df['Periodo'] = monthly_df['Periodo'].dt.to_timestamp()

    date_format_str = '%d/%m/%Y' if periodo_format == 'D' else '%Y-%m'
    monthly_df['PeriodoLabel'] = monthly_df['Periodo'].dt.strftime(date_format_str)
    
    monthly_df['Periodo'] = monthly_df['Periodo'].astype(str)
    monthly_df = monthly_df.sort_values(by='Periodo', ascending=True)
            
    return monthly_df

def get_despesas_details_dashboard_data(apartamento_id: int, start_date, end_date, placa_filter, filial_filter):
    """
    Prepara todos os dados necessários para os gráficos da página de detalhes de despesas.
    """
    dashboard_data = {}
    
    df_despesas_raw = get_data_as_dataframe("relFilDespesasGerais", apartamento_id)
    df = apply_filters_to_df(df_despesas_raw, start_date, end_date, placa_filter, filial_filter)

    if df.empty:
        return dashboard_data

    col_map = _get_case_insensitive_column_map(df.columns)

    # Gráfico 1: Despesas por Super Grupo
    if 'descsupergrupod' in col_map and 'liquido' in col_map:
        despesa_super_grupo = df.groupby(col_map['descsupergrupod'])[col_map['liquido']].sum().reset_index()
        dashboard_data['despesa_super_grupo'] = despesa_super_grupo.to_dict('records')

    # Gráfico 2: Despesas por Filial
    if 'nomefil' in col_map and 'liquido' in col_map:
        despesa_filial = df.groupby(col_map['nomefil'])[col_map['liquido']].sum().reset_index()
        dashboard_data['despesa_filial'] = despesa_filial.to_dict('records')

    # Gráfico 3: Custo de Manutenção por Veículo
    if 'descgrupod' in col_map and 'placaveiculo' in col_map and 'liquido' in col_map:
        df_manutencao = df[df[col_map['descgrupod']] == 'MANUTENCAO'].copy() # Comparação case-insensitive
        if not df_manutencao.empty:
            custo_manutencao_veiculo = df_manutencao.groupby(col_map['placaveiculo'])[col_map['liquido']].sum().nlargest(10).reset_index()
            dashboard_data['custo_manutencao_veiculo'] = custo_manutencao_veiculo.to_dict('records')

    # Gráfico 4: Custo Médio por KM Rodado
    if 'kmrodado' in col_map and 'liquido' in col_map and 'placaveiculo' in col_map:
        df_km = df[df[col_map['kmrodado']] > 0].copy()
        if not df_km.empty:
            custo_por_veiculo = df_km.groupby(col_map['placaveiculo']).agg(
                total_liquido=(col_map['liquido'], 'sum'),
                total_km=(col_map['kmrodado'], 'sum')
            ).reset_index()
            
            custo_por_veiculo = custo_por_veiculo[custo_por_veiculo['total_km'] > 0]
            if not custo_por_veiculo.empty:
                custo_por_veiculo['custo_por_km'] = custo_por_veiculo['total_liquido'] / custo_por_veiculo['total_km']
                dashboard_data['custo_km_veiculo'] = custo_por_veiculo.sort_values(by='custo_por_km', ascending=False).to_dict('records')

    # Gráfico 5: Despesas com Combustível (DIESEL) por Mês
    if 'descgrupod' in col_map and 'datacontrole' in col_map and 'liquido' in col_map:
        df_diesel = df[df[col_map['descgrupod']] == 'DIESEL'].copy() # Comparação case-insensitive
        if not df_diesel.empty:
            df_diesel['mes'] = pd.to_datetime(df_diesel[col_map['datacontrole']], errors='coerce').dt.to_period('M').astype(str)
            diesel_mensal = df_diesel.groupby('mes')[col_map['liquido']].sum().reset_index()
            dashboard_data['diesel_mensal'] = diesel_mensal.sort_values(by='mes').to_dict('records')
            
    return dashboard_data

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
            query = text('SELECT "group_name", "is_despesa", "is_custo_viagem" FROM "static_expense_groups" WHERE "apartamento_id" = :apt_id')
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
        with engine.connect() as conn:
            with conn.begin():
                sql_update_flags = text("""
                    UPDATE "static_expense_groups" 
                    SET "is_despesa" = :is_despesa, "is_custo_viagem" = :is_custo 
                    WHERE "group_name" = :group_name AND "apartamento_id" = :apt_id
                """)
                for group_name, classification in update_data.items():
                    is_despesa = 'S' if classification == 'despesa' else 'N'
                    is_custo = 'S' if classification == 'custo_viagem' else 'N'
                    conn.execute(sql_update_flags, {
                        "is_despesa": is_despesa, "is_custo": is_custo,
                        "group_name": group_name, "apt_id": apartamento_id
                    })
        sync_expense_groups(apartamento_id)
        print(f"Flags de grupo atualizadas com sucesso para o apartamento {apartamento_id}.")
    except Exception as e:
        print(f"Erro ao atualizar flags de grupo de despesa: {e}")
        raise e

def get_unique_plates(apartamento_id: int) -> list[str]:
    df_viagens = get_data_as_dataframe("relFilViagensFatCliente", apartamento_id)
    df_despesas = get_data_as_dataframe("relFilDespesasGerais", apartamento_id)
    
    col_map_viagens = _get_case_insensitive_column_map(df_viagens.columns)
    col_map_despesas = _get_case_insensitive_column_map(df_despesas.columns)
    
    plates = pd.Series(dtype=str)
    if 'placaveiculo' in col_map_viagens:
        plates = pd.concat([plates, df_viagens[col_map_viagens['placaveiculo']].dropna().astype(str)])
    if 'placaveiculo' in col_map_despesas:
        plates = pd.concat([plates, df_despesas[col_map_despesas['placaveiculo']].dropna().astype(str)])
        
    if plates.empty:
        return ["Todos"]
    return ["Todos"] + sorted(plates.unique().tolist())

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

# Substitua a função inteira em data_manager.py

# Substitua a função inteira em data_manager.py

# Em data_manager.py, substitua a função existente por esta versão corrigida:

def get_faturamento_details_dashboard_data(apartamento_id: int, start_date, end_date, placa_filter, filial_filter):
    dashboard_data = {}
    
    # --- Passo 1: Carregar dados brutos (Sem alterações) ---
    df_fat_raw = get_data_as_dataframe("relFilViagensFatCliente", apartamento_id)
    df_viagens_cliente_raw = get_data_as_dataframe("relFilViagensCliente", apartamento_id)
    df_despesas_raw = get_data_as_dataframe("relFilDespesasGerais", apartamento_id)
    df_flags = get_all_group_flags(apartamento_id)
    flags_dict = df_flags.set_index('group_name').to_dict('index') if not df_flags.empty else {}

    # --- Passo 2: Lógica de Filtragem Corrigida ---
    # A linha que filtrava df_fat_raw foi removida.
    # A "fonte da verdade" para os filtros é sempre a tabela de viagens.
    df_viagens_cliente = apply_filters_to_df(df_viagens_cliente_raw, start_date, end_date, placa_filter, filial_filter)
    df_despesas_filtrado = apply_filters_to_df(df_despesas_raw, start_date, end_date, placa_filter, filial_filter)

    # --- Passo 3: Cálculos ---
    periodo = 'D' if start_date and end_date and (end_date - start_date).days <= 62 else 'M'

    # --- ALTERAÇÃO CIRÚRGICA 1: Centraliza a criação do DataFrame de faturamento correto ---
    # Este bloco agora define a fonte de dados correta para TODOS os gráficos de faturamento.
    df_fat_filtrado_final = pd.DataFrame()
    col_map_fat_final = {}
    if not df_viagens_cliente.empty and not df_fat_raw.empty:
        # Aplica o filtro 'permitefaturar' para consistência com os KPIs
        col_map_fat_temp = _get_case_insensitive_column_map(df_fat_raw.columns)
        if 'permitefaturar' in col_map_fat_temp:
            df_fat_raw = df_fat_raw[df_fat_raw[col_map_fat_temp['permitefaturar']] == 'S']

        viagens_filtradas_ids = df_viagens_cliente['numConhec'].unique()
        df_fat_filtrado_final = df_fat_raw[df_fat_raw['numConhec'].isin(viagens_filtradas_ids)]
        col_map_fat_final = _get_case_insensitive_column_map(df_fat_filtrado_final.columns)

        # Calcula os gráficos que já usavam esta lógica
        if not df_fat_filtrado_final.empty and 'nomecliente' in col_map_fat_final and 'freteempresa' in col_map_fat_final:
            top_clientes = df_fat_filtrado_final.groupby(col_map_fat_final['nomecliente'])[col_map_fat_final['freteempresa']].sum().reset_index()
            top_clientes.sort_values(by=col_map_fat_final['freteempresa'], ascending=False, inplace=True)
            dashboard_data['top_clientes'] = top_clientes.to_dict(orient='records')

        if not df_fat_filtrado_final.empty and 'nomefilial' in col_map_fat_final and 'freteempresa' in col_map_fat_final:
            fat_filial = df_fat_filtrado_final.groupby(col_map_fat_final['nomefilial'])[col_map_fat_final['freteempresa']].sum().reset_index()
            dashboard_data['faturamento_filial'] = fat_filial.to_dict(orient='records')
    
    # --- ALTERAÇÃO CIRÚRGICA 2: Injeta os dados corretos no df_viagens_cliente ---
    # Isso conserta automaticamente todos os gráficos que dependem da coluna 'freteempresa' de df_viagens_cliente.
    if not df_fat_filtrado_final.empty:
        df_faturamento_correto = df_fat_filtrado_final[['numConhec', 'freteEmpresa']]
        if 'freteEmpresa' in df_viagens_cliente.columns:
            df_viagens_cliente = df_viagens_cliente.drop(columns=['freteEmpresa'])
        df_viagens_cliente = pd.merge(df_viagens_cliente, df_faturamento_correto, on='numConhec', how='left')

    # A partir daqui, o resto da função pode continuar como era, pois os dados já foram corrigidos na origem.
    col_map_viagens_cli = _get_case_insensitive_column_map(df_viagens_cliente.columns)
    col_map_despesas = _get_case_insensitive_column_map(df_despesas_filtrado.columns)

    # Gráfico de Evolução (agora usa o 'freteempresa' correto injetado acima)
    fat_evolucao = pd.Series(dtype=float)
    if not df_viagens_cliente.empty and 'dataviagemmotorista' in col_map_viagens_cli and 'freteempresa' in col_map_viagens_cli:
        df_fat_copy = df_viagens_cliente.copy()
        df_fat_copy['Periodo'] = pd.to_datetime(df_fat_copy[col_map_viagens_cli['dataviagemmotorista']], errors='coerce', dayfirst=True).dt.to_period(periodo)
        fat_evolucao = df_fat_copy.groupby('Periodo')[col_map_viagens_cli['freteempresa']].sum()
    
    df_com_flags = pd.DataFrame()
    if not df_despesas_filtrado.empty and not df_flags.empty and 'descgrupod' in col_map_despesas:
        df_com_flags = pd.merge(df_despesas_filtrado, df_flags, left_on=col_map_despesas['descgrupod'], right_on='group_name', how='left')
    else:
        df_com_flags = df_despesas_filtrado.copy()
    if not df_com_flags.empty:
        df_com_flags['is_custo_viagem'] = df_com_flags['is_custo_viagem'].fillna('N')
        df_com_flags['is_despesa'] = df_com_flags['is_despesa'].fillna('S')
    df_custos_final = df_com_flags[df_com_flags['is_custo_viagem'] == 'S'].copy() if not df_com_flags.empty else pd.DataFrame()
    comissao_df_data = pd.DataFrame()
    if not df_viagens_cliente.empty and all(c in col_map_viagens_cli for c in ['tipofrete', 'fretemotorista', 'comissao', 'dataviagemmotorista']):
        df_comissao_base = df_viagens_cliente[(df_viagens_cliente[col_map_viagens_cli['tipofrete']].astype(str) == 'P') & (pd.to_numeric(df_viagens_cliente[col_map_viagens_cli['fretemotorista']], errors='coerce') > 0)].copy()
        if not df_comissao_base.empty:
            df_comissao_base['valorNota'] = pd.to_numeric(df_comissao_base[col_map_viagens_cli['fretemotorista']], errors='coerce').fillna(0) * (pd.to_numeric(df_comissao_base[col_map_viagens_cli['comissao']], errors='coerce').fillna(0) / 100)
            comissao_df_data = df_comissao_base[[col_map_viagens_cli['dataviagemmotorista'], 'valorNota']].rename(columns={col_map_viagens_cli['dataviagemmotorista']: 'dataControle'})
    
    # O cálculo de 'quebra' agora usa o df_fat_filtrado_final que é a fonte correta
    quebra_df_data = pd.DataFrame()
    if not df_fat_filtrado_final.empty and all(c in col_map_fat_final for c in ['dataviagemmotorista', 'valorquebra']):
        df_quebra_base = df_fat_filtrado_final[[col_map_fat_final['dataviagemmotorista'], col_map_fat_final['valorquebra']]].copy()
        quebra_df_data = df_quebra_base.rename(columns={col_map_fat_final['valorquebra']: 'valorNota', col_map_fat_final['dataviagemmotorista']: 'dataControle'})

    if not quebra_df_data.empty and flags_dict.get('VALOR QUEBRA', {}).get('is_custo_viagem') == 'S':
        df_custos_final = pd.concat([df_custos_final, quebra_df_data], ignore_index=True)
    if not comissao_df_data.empty and flags_dict.get('COMISSÃO DE MOTORISTA', {}).get('is_custo_viagem') == 'S':
        df_custos_final = pd.concat([df_custos_final, comissao_df_data], ignore_index=True)
    
    custo_evolucao = pd.Series(dtype=float)
    col_map_custos = _get_case_insensitive_column_map(df_custos_final.columns)
    if not df_custos_final.empty and 'datacontrole' in col_map_custos and 'valornota' in col_map_custos:
        df_custos_copy = df_custos_final.copy()
        df_custos_copy['Periodo'] = pd.to_datetime(df_custos_copy[col_map_custos['datacontrole']], errors='coerce', dayfirst=True).dt.to_period(periodo)
        custo_evolucao = df_custos_copy.groupby('Periodo')[col_map_custos['valornota']].sum()

    evolucao_df = pd.DataFrame({'Faturamento': fat_evolucao, 'Custo': custo_evolucao}).fillna(0).reset_index()
    evolucao_df.rename(columns={'index': 'Periodo'}, inplace=True)
    evolucao_df['Periodo'] = evolucao_df['Periodo'].astype(str)
    dashboard_data['evolucao_faturamento_custo'] = evolucao_df.to_dict('records')
    
    # O bloco de "Lógica de cruzamento..." foi movido para o topo, então não existe mais aqui.
    # Os cálculos abaixo agora usam o df_viagens_cliente já corrigido.
    if not df_viagens_cliente.empty:
        if 'cidorigemformat' in col_map_viagens_cli and 'ciddestinoformat' in col_map_viagens_cli:
            df_viagens_cliente['rota'] = df_viagens_cliente[col_map_viagens_cli['cidorigemformat']] + ' -> ' + df_viagens_cliente[col_map_viagens_cli['ciddestinoformat']]
            top_rotas = df_viagens_cliente['rota'].value_counts().reset_index()
            top_rotas.columns = ['rota', 'contagem']
            dashboard_data['top_rotas'] = top_rotas.to_dict(orient='records')
            if 'pesosaida' in col_map_viagens_cli:
                volume_rota = df_viagens_cliente.groupby('rota')[col_map_viagens_cli['pesosaida']].sum().reset_index()
                volume_rota.sort_values(by=col_map_viagens_cli['pesosaida'], ascending=False, inplace=True)
                dashboard_data['volume_por_rota'] = volume_rota.to_dict(orient='records')
        
        if 'placaveiculo' in col_map_viagens_cli:
            viagens_veiculo = df_viagens_cliente[col_map_viagens_cli['placaveiculo']].value_counts().reset_index()
            viagens_veiculo.columns = ['placa', 'contagem']
            viagens_veiculo.sort_values(by='contagem', ascending=False, inplace=True)
            dashboard_data['viagens_por_veiculo'] = viagens_veiculo.to_dict(orient='records')
            
        if 'nomemotorista' in col_map_viagens_cli and 'freteempresa' in col_map_viagens_cli:
            fat_motorista = df_viagens_cliente.groupby(col_map_viagens_cli['nomemotorista'])[col_map_viagens_cli['freteempresa']].sum().reset_index()
            fat_motorista = fat_motorista[fat_motorista[col_map_viagens_cli['freteempresa']] > 0]
            fat_motorista.sort_values(by=col_map_viagens_cli['freteempresa'], ascending=False, inplace=True)
            fat_motorista.rename(columns={col_map_viagens_cli['nomemotorista']: 'nomeMotorista', col_map_viagens_cli['freteempresa']: 'faturamento'}, inplace=True)
            dashboard_data['faturamento_motorista'] = fat_motorista.to_dict(orient='records')

        if 'descricaomercadoria' in col_map_viagens_cli and 'freteempresa' in col_map_viagens_cli:
            fat_por_mercadoria = df_viagens_cliente.groupby(col_map_viagens_cli['descricaomercadoria'])[col_map_viagens_cli['freteempresa']].sum().sort_values(ascending=False)
            if len(fat_por_mercadoria) > 7:
                top_7 = fat_por_mercadoria.nlargest(7)
                outros = pd.Series([fat_por_mercadoria.nsmallest(len(fat_por_mercadoria) - 7).sum()], index=['Outros'])
                fat_final = pd.concat([top_7, outros])
            else:
                fat_final = fat_por_mercadoria
            fat_final.name = col_map_viagens_cli['freteempresa']
            df_resultado = fat_final.reset_index().rename(columns={col_map_viagens_cli['descricaomercadoria']: 'mercadoria', col_map_viagens_cli['freteempresa']: 'faturamento'})
            df_resultado['faturamento'] = df_resultado['faturamento'].astype(float)
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