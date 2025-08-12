# data_manager.py (versão final com todas as regras implementadas)

import pandas as pd
from datetime import datetime
import database as db 
import config
import sqlite3
import os

def get_data_as_dataframe(table_name: str, apartamento_id: int) -> pd.DataFrame:
    db_url = os.getenv('DATABASE_URL')
    if not db_url and not os.path.exists(db.DATABASE_NAME):
        return pd.DataFrame()
    try:
        with db.get_db_connection() as conn:
            if conn is None:
                return pd.DataFrame()
            query_check_table = f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"
            cursor = conn.cursor()
            cursor.execute(query_check_table)
            result = cursor.fetchone()
            if result is None or result[0] is None:
                return pd.DataFrame()
            df = pd.read_sql_query(
                f'SELECT * FROM "{table_name}" WHERE "apartamento_id" = ?',
                conn,
                params=(apartamento_id,)
            )
            df.columns = [str(col).strip() for col in df.columns]
            return df
    except Exception as e:
        print(f"ERRO CRÍTICO ao carregar dados da tabela '{table_name}': {e}")
        return pd.DataFrame()

def apply_filters_to_df(df: pd.DataFrame, start_date: datetime, end_date: datetime, placa_filter: str, filial_filter: str) -> pd.DataFrame:
    if df.empty: return df
    df = df.copy()
    
    date_column_found = None
    possible_date_cols = ['dataControle', 'dataViagemMotorista', 'dataVenc']
    for col in possible_date_cols:
        if col in df.columns:
            date_column_found = col
            break

    if date_column_found and (start_date or end_date):
        df[date_column_found] = pd.to_datetime(df[date_column_found], errors='coerce', dayfirst=True)
        df.dropna(subset=[date_column_found], inplace=True)
        if not df.empty:
            if start_date: df = df[df[date_column_found] >= start_date]
            if end_date: df = df[df[date_column_found] <= end_date]

    if placa_filter and placa_filter != "Todos" and "placa" in config.FILTER_COLUMN_MAPS:
        for col in config.FILTER_COLUMN_MAPS["placa"]:
            if col in df.columns:
                df = df[df[col].astype(str).str.strip().str.upper() == placa_filter.strip().upper()]
                break

    if filial_filter and filial_filter != "Todos" and "filial" in config.FILTER_COLUMN_MAPS:
        for col in config.FILTER_COLUMN_MAPS["filial"]:
            if col in df.columns:
                df = df[df[col].astype(str).str.strip().str.upper() == filial_filter.strip().upper()]
                break
    return df

# --- FUNÇÃO MESTRA QUE CENTRALIZA TODA A LÓGICA ---
def _get_final_dataframes(apartamento_id: int, start_date, end_date, placa_filter, filial_filter):
    # 1. Pega os dados brutos e aplica os filtros globais, passando o apartamento_id
    df_viagens_faturamento_raw = get_data_as_dataframe("relFilViagensFatCliente", apartamento_id)
    df_viagens_faturamento = apply_filters_to_df(df_viagens_faturamento_raw, start_date, end_date, placa_filter, filial_filter)
    
    df_viagens_cliente_raw = get_data_as_dataframe("relFilViagensCliente", apartamento_id)
    df_viagens_cliente = apply_filters_to_df(df_viagens_cliente_raw, start_date, end_date, placa_filter, filial_filter)

    df_despesas_raw = get_data_as_dataframe("relFilDespesasGerais", apartamento_id)
    df_despesas_filtrado = apply_filters_to_df(df_despesas_raw, start_date, end_date, placa_filter, filial_filter)
    
    df_flags = get_all_group_flags(apartamento_id)
    flags_dict = df_flags.set_index('group_name').to_dict('index') if not df_flags.empty else {}

    # 2. Processa os dados base de custo e despesa
    df_despesas_processed = pd.DataFrame()
    if not df_despesas_filtrado.empty:
        df_despesas_processed = df_despesas_filtrado.drop_duplicates(subset=['dataControle', 'numNota', 'valorVenc'])
    
    df_custos = pd.DataFrame(columns=['dataControle', 'valorNota'])
    df_despesas_gerais = pd.DataFrame(columns=['dataControle', 'valorNota'])

    if not df_despesas_processed.empty and not df_flags.empty:
        df_com_flags = pd.merge(df_despesas_processed, df_flags, left_on='descGrupoD', right_on='group_name', how='left')
        df_com_flags['is_custo_viagem'] = df_com_flags['is_custo_viagem'].fillna('N')
        df_com_flags['is_despesa'] = df_com_flags['is_despesa'].fillna('S')
        
        df_custos = df_com_flags[df_com_flags['is_custo_viagem'] == 'S'].copy()
        df_despesas_gerais = df_com_flags[df_com_flags['is_despesa'] == 'S'].copy()

    # 3. Calcula comissão e quebra e os transforma em DataFrames para serem adicionados
    comissao_df = pd.DataFrame(columns=['dataControle', 'valorNota'])
    if not df_viagens_cliente.empty and all(c in df_viagens_cliente.columns for c in ['tipoFrete', 'freteMotorista', 'comissao', 'dataViagemMotorista']):
        df_comissao_base = df_viagens_cliente[(df_viagens_cliente['tipoFrete'].astype(str).str.strip().str.upper() == 'P') & (pd.to_numeric(df_viagens_cliente['freteMotorista'], errors='coerce') > 0)].copy()
        if not df_comissao_base.empty:
            frete_motorista = pd.to_numeric(df_comissao_base['freteMotorista'], errors='coerce').fillna(0)
            percentual_comissao = pd.to_numeric(df_comissao_base['comissao'], errors='coerce').fillna(0)
            df_comissao_base['valorNota'] = frete_motorista * (percentual_comissao / 100)
            df_comissao_base.rename(columns={'dataViagemMotorista': 'dataControle'}, inplace=True)
            comissao_df = df_comissao_base[['dataControle', 'valorNota']]
    
    quebra_df = pd.DataFrame(columns=['dataControle', 'valorNota'])
    if not df_viagens_faturamento.empty and all(c in df_viagens_faturamento.columns for c in ['valorQuebra', 'dataViagemMotorista']):
        df_quebra_base = df_viagens_faturamento[['dataViagemMotorista', 'valorQuebra']].copy()
        df_quebra_base.rename(columns={'valorQuebra': 'valorNota', 'dataViagemMotorista': 'dataControle'}, inplace=True)
        quebra_df = df_quebra_base
        
    # 4. Adiciona comissão e quebra aos DataFrames corretos
    if not quebra_df.empty:
        if flags_dict.get('VALOR QUEBRA', {}).get('is_custo_viagem') == 'S':
            df_custos = pd.concat([df_custos, quebra_df], ignore_index=True)
        elif flags_dict.get('VALOR QUEBRA', {}).get('is_despesa') == 'S':
            df_despesas_gerais = pd.concat([df_despesas_gerais, quebra_df], ignore_index=True)
    
    if not comissao_df.empty:
        comissao_flags = flags_dict.get('COMISSÃO DE MOTORISTA', {})
        if comissao_flags.get('is_custo_viagem') == 'S':
            df_custos = pd.concat([df_custos, comissao_df], ignore_index=True)
        elif comissao_flags.get('is_despesa') == 'S':
            df_despesas_gerais = pd.concat([df_despesas_gerais, comissao_df], ignore_index=True)

    return df_viagens_faturamento, df_custos, df_despesas_gerais

def get_dashboard_summary(apartamento_id: int, start_date: datetime = None, end_date: datetime = None, placa_filter: str = "Todos", filial_filter: str = "Todos") -> dict:
    summary = {}
    
    df_contas_pagar_raw = get_data_as_dataframe("relFilContasPagarDet", apartamento_id)
    pending_pagar = 0
    if not df_contas_pagar_raw.empty and 'codTransacao' in df_contas_pagar_raw.columns:
        pendentes_df = df_contas_pagar_raw[df_contas_pagar_raw['codTransacao'].fillna('').str.strip() == '']
        unicas_df = pendentes_df.drop_duplicates(subset=['dataVenc', 'numNota', 'nomeForn'])
        pending_pagar = unicas_df['valorVenc'].sum() if 'valorVenc' in unicas_df.columns else 0
    summary['saldo_contas_a_pagar_pendentes'] = pending_pagar
    
    df_contas_receber_raw = get_data_as_dataframe("relFilContasReceber", apartamento_id)
    summary['saldo_contas_a_receber_pendentes'] = df_contas_receber_raw[df_contas_receber_raw['codTransacao'].fillna('').str.strip() == '']['valorVenc'].sum() if not df_contas_receber_raw.empty and 'codTransacao' in df_contas_receber_raw.columns else 0
    
    df_viagens_faturamento_raw = get_data_as_dataframe("relFilViagensFatCliente", apartamento_id)
    df_viagens_faturamento = apply_filters_to_df(df_viagens_faturamento_raw, start_date, end_date, placa_filter, filial_filter)
    
    df_viagens_cliente_raw = get_data_as_dataframe("relFilViagensCliente", apartamento_id)
    df_viagens_cliente = apply_filters_to_df(df_viagens_cliente_raw, start_date, end_date, placa_filter, filial_filter)

    df_despesas_raw = get_data_as_dataframe("relFilDespesasGerais", apartamento_id)
    df_despesas_filtrado = apply_filters_to_df(df_despesas_raw, start_date, end_date, placa_filter, filial_filter)
    
    df_flags = get_all_group_flags(apartamento_id)
    flags_dict = df_flags.set_index('group_name').to_dict('index') if not df_flags.empty else {}
    
    df_despesas_processed = df_despesas_filtrado.drop_duplicates(subset=['dataControle', 'numNota', 'valorVenc']) if not df_despesas_filtrado.empty else pd.DataFrame()
    df_com_flags = pd.merge(df_despesas_processed, df_flags, left_on='descGrupoD', right_on='group_name', how='left') if not df_despesas_processed.empty and not df_flags.empty else df_despesas_processed
    
    # --- INÍCIO DA CORREÇÃO CIRÚRGICA ---
    # Se o merge não adicionou as colunas (porque df_flags estava vazio),
    # nós as adicionamos manualmente com valores padrão para evitar o KeyError.
    if 'is_custo_viagem' not in df_com_flags.columns:
        df_com_flags['is_custo_viagem'] = 'N'
    if 'is_despesa' not in df_com_flags.columns:
        df_com_flags['is_despesa'] = 'S' # 'S' (Sim) é o valor padrão para uma despesa não classificada
    # --- FIM DA CORREÇÃO CIRÚRGICA ---

    if not df_com_flags.empty:
        df_com_flags['is_custo_viagem'] = df_com_flags['is_custo_viagem'].fillna('N')
        df_com_flags['is_despesa'] = df_com_flags['is_despesa'].fillna('S')
    
    df_custos = df_com_flags[df_com_flags['is_custo_viagem'] == 'S'].copy() if not df_com_flags.empty else pd.DataFrame()
    df_despesas_gerais = df_com_flags[df_com_flags['is_despesa'] == 'S'].copy() if not df_com_flags.empty else pd.DataFrame()

    total_comissao_motorista = 0
    if not df_viagens_cliente.empty and all(c in df_viagens_cliente.columns for c in ['tipoFrete', 'freteMotorista', 'comissao']):
        df_comissao_base = df_viagens_cliente[(df_viagens_cliente['tipoFrete'].astype(str).str.strip().str.upper() == 'P') & (pd.to_numeric(df_viagens_cliente['freteMotorista'], errors='coerce') > 0)].copy()
        if not df_comissao_base.empty:
            frete_motorista = pd.to_numeric(df_comissao_base['freteMotorista'], errors='coerce').fillna(0)
            percentual_comissao = pd.to_numeric(df_comissao_base['comissao'], errors='coerce').fillna(0)
            total_comissao_motorista = (frete_motorista * (percentual_comissao / 100)).sum()
            
    valor_quebra_sum = df_viagens_faturamento['valorQuebra'].sum() if 'valorQuebra' in df_viagens_faturamento.columns else 0

    custo_base = df_custos['valorNota'].sum() if 'valorNota' in df_custos.columns else 0
    despesa_base = df_despesas_gerais['valorNota'].sum() if 'valorNota' in df_despesas_gerais.columns else 0
    
    if flags_dict.get('VALOR QUEBRA', {}).get('is_custo_viagem') == 'S':
        custo_base += valor_quebra_sum
    elif flags_dict.get('VALOR QUEBRA', {}).get('is_despesa') == 'S':
        despesa_base += valor_quebra_sum
        
    comissao_flags = flags_dict.get('COMISSÃO DE MOTORISTA', {})
    if comissao_flags.get('is_custo_viagem') == 'S':
        custo_base += total_comissao_motorista
    elif comissao_flags.get('is_despesa') == 'S':
        despesa_base += total_comissao_motorista
    
    summary['faturamento_total_viagens'] = df_viagens_faturamento['freteEmpresa'].sum() if 'freteEmpresa' in df_viagens_faturamento.columns else 0
    summary['custo_total_viagem'] = custo_base
    summary['total_despesas_gerais'] = despesa_base

    custo_operacional_total = summary['custo_total_viagem'] + summary['total_despesas_gerais']
    summary['saldo_geral'] = summary['faturamento_total_viagens'] - custo_operacional_total
    summary['margem_frete'] = (summary['saldo_geral'] / summary['faturamento_total_viagens'] * 100) if summary.get('faturamento_total_viagens', 0) > 0 else 0
    
    return summary

def get_monthly_summary(apartamento_id: int, start_date, end_date, placa_filter, filial_filter) -> pd.DataFrame:
    periodo_format = 'D' if start_date and end_date else 'M'
    
    # --- BUSCA DE DADOS ---
    df_viagens_faturamento_raw = get_data_as_dataframe("relFilViagensFatCliente", apartamento_id)
    df_viagens_faturamento = apply_filters_to_df(df_viagens_faturamento_raw, start_date, end_date, placa_filter, filial_filter)

    df_viagens_cliente_raw = get_data_as_dataframe("relFilViagensCliente", apartamento_id)
    df_viagens_cliente = apply_filters_to_df(df_viagens_cliente_raw, start_date, end_date, placa_filter, filial_filter)

    df_despesas_raw = get_data_as_dataframe("relFilDespesasGerais", apartamento_id)
    df_despesas_filtrado = apply_filters_to_df(df_despesas_raw, start_date, end_date, placa_filter, filial_filter)
    
    df_flags = get_all_group_flags(apartamento_id)
    flags_dict = df_flags.set_index('group_name').to_dict('index') if not df_flags.empty else {}

    df_despesas_processed = df_despesas_filtrado.drop_duplicates(subset=['dataControle', 'numNota', 'valorVenc']) if not df_despesas_filtrado.empty else pd.DataFrame()
    df_com_flags = pd.merge(df_despesas_processed, df_flags, left_on='descGrupoD', right_on='group_name', how='left') if not df_despesas_processed.empty and not df_flags.empty else df_despesas_processed
    
    if 'is_custo_viagem' not in df_com_flags.columns:
        df_com_flags['is_custo_viagem'] = 'N'
    if 'is_despesa' not in df_com_flags.columns:
        df_com_flags['is_despesa'] = 'S'

    if not df_com_flags.empty:
        df_com_flags['is_custo_viagem'] = df_com_flags['is_custo_viagem'].fillna('N')
        df_com_flags['is_despesa'] = df_com_flags['is_despesa'].fillna('S')
    
    df_custos = df_com_flags[df_com_flags['is_custo_viagem'] == 'S'].copy() if not df_com_flags.empty else pd.DataFrame()
    df_despesas_gerais = df_com_flags[df_com_flags['is_despesa'] == 'S'].copy() if not df_com_flags.empty else pd.DataFrame()

    comissao_df_data = pd.DataFrame()
    if not df_viagens_cliente.empty and all(c in df_viagens_cliente.columns for c in ['tipoFrete', 'freteMotorista', 'comissao', 'dataViagemMotorista']):
        df_comissao_base = df_viagens_cliente[(df_viagens_cliente['tipoFrete'].astype(str).str.strip().str.upper() == 'P') & (pd.to_numeric(df_viagens_cliente['freteMotorista'], errors='coerce') > 0)].copy()
        if not df_comissao_base.empty:
            df_comissao_base['valorNota'] = pd.to_numeric(df_comissao_base['freteMotorista'], errors='coerce').fillna(0) * (pd.to_numeric(df_comissao_base['comissao'], errors='coerce').fillna(0) / 100)
            comissao_df_data = df_comissao_base[['dataViagemMotorista', 'valorNota']].rename(columns={'dataViagemMotorista': 'dataControle'})

    quebra_df_data = pd.DataFrame()
    if not df_viagens_faturamento.empty and 'valorQuebra' in df_viagens_faturamento.columns:
        df_quebra_base = df_viagens_faturamento[['dataViagemMotorista', 'valorQuebra']].copy()
        quebra_df_data = df_quebra_base.rename(columns={'valorQuebra': 'valorNota', 'dataViagemMotorista': 'dataControle'})
        
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

    # --- INÍCIO DA CORREÇÃO CIRÚRGICA ---
    faturamento = pd.Series(dtype=float)
    if not df_viagens_faturamento.empty and 'dataViagemMotorista' in df_viagens_faturamento.columns:
        df_viagens_faturamento['Periodo'] = pd.to_datetime(df_viagens_faturamento['dataViagemMotorista'], errors='coerce', dayfirst=True).dt.to_period(periodo_format)
        faturamento = df_viagens_faturamento.groupby('Periodo')['freteEmpresa'].sum()
    faturamento.name = 'Faturamento'

    despesas_agrupadas = pd.Series(dtype=float)
    if not df_despesas_gerais.empty and 'dataControle' in df_despesas_gerais.columns:
        df_despesas_gerais['Periodo'] = pd.to_datetime(df_despesas_gerais['dataControle'], errors='coerce', dayfirst=True).dt.to_period(periodo_format)
        despesas_agrupadas = df_despesas_gerais.groupby('Periodo')['valorNota'].sum()
    despesas_agrupadas.name = 'DespesasGerais'

    custos_agrupados = pd.Series(dtype=float)
    if not df_custos.empty and 'dataControle' in df_custos.columns:
        df_custos['Periodo'] = pd.to_datetime(df_custos['dataControle'], errors='coerce', dayfirst=True).dt.to_period(periodo_format)
        custos_agrupados = df_custos.groupby('Periodo')['valorNota'].sum()
    custos_agrupados.name = 'Custo'
        
    monthly_df = pd.concat([faturamento, custos_agrupados, despesas_agrupadas], axis=1).fillna(0)
    
    if not monthly_df.empty:
        # CORREÇÃO: Garante que PeriodoLabel seja criado corretamente
        if isinstance(monthly_df.index, pd.PeriodIndex):
            # Usa o formato correto dependendo se o período é diário ou mensal
            date_format_str = '%Y-%m-%d' if periodo_format == 'D' else '%Y-%m'
            monthly_df['PeriodoLabel'] = monthly_df.index.strftime(date_format_str)
        else:
            # Fallback caso o índice não seja do tipo Período
            monthly_df['PeriodoLabel'] = monthly_df.index.astype(str)
        
        monthly_df.index.name = 'Periodo'
        monthly_df = monthly_df.reset_index()

        if 'Periodo' in monthly_df.columns:
            monthly_df['Periodo'] = monthly_df['Periodo'].astype(str)
    # --- FIM DA CORREÇÃO CIRÚRGICA ---
        
    return monthly_df

def get_relFilViagensFatCliente_df(apartamento_id: int, start_date=None, end_date=None, placa_filter="Todos", filial_filter="Todos"):
    
    # MODIFICADO: Passa o apartamento_id para a busca inicial no banco de dados.
    df = get_data_as_dataframe("relFilViagensFatCliente", apartamento_id)
    
    if 'permiteFaturar' in df.columns:
        df = df[df['permiteFaturar'].astype(str).str.upper() == 'S']
        
    return apply_filters_to_df(df, start_date, end_date, placa_filter, filial_filter)
def sync_expense_groups(apartamento_id: int):
    
    print(f"Sincronizando grupos de despesa para o apartamento {apartamento_id}...")
    
    # MODIFICADO: Busca despesas apenas do apartamento atual.
    df_despesas = get_data_as_dataframe("relFilDespesasGerais", apartamento_id)
    
    if df_despesas.empty or 'descGrupoD' not in df_despesas.columns:
        print("Nenhum grupo de despesa para sincronizar.")
        return
        
    grupos_dinamicos = df_despesas['descGrupoD'].dropna().unique()
    with db.get_db_connection() as conn:
        if conn is None: return
        cursor = conn.cursor()
        is_sqlite = isinstance(conn, sqlite3.Connection)
        placeholder = "?" if is_sqlite else "%s"
        
        for group_name in grupos_dinamicos:
            # MODIFICADO: A tabela de grupos agora precisa do apartamento_id
            # Assumindo que a tabela static_expense_groups foi alterada para ter uma chave primária/única composta (apartamento_id, group_name)
            if is_sqlite:
                cursor.execute('INSERT OR IGNORE INTO "static_expense_groups" ("apartamento_id", "group_name") VALUES (?, ?)', (apartamento_id, group_name))
            else:
                cursor.execute('INSERT INTO "static_expense_groups" ("apartamento_id", "group_name") VALUES (%s, %s) ON CONFLICT(apartamento_id, group_name) DO NOTHING', (apartamento_id, group_name))
        
        conn.commit()
    print("Sincronização concluída.")
def get_all_group_flags(apartamento_id: int):
    try:
        with db.get_db_connection() as conn:
            if conn is None:
                return pd.DataFrame(columns=['group_name', 'is_despesa', 'is_custo_viagem'])
            
            # MODIFICADO: Adicionada a cláusula WHERE para filtrar as flags por apartamento_id
            sql_query = 'SELECT "group_name", "is_despesa", "is_custo_viagem" FROM "static_expense_groups" WHERE "apartamento_id" = ?'
            df = pd.read_sql(sql_query, conn, params=(apartamento_id,))
            
            return df
    except Exception as e:
        print(f"Erro ao buscar flags de grupo: {e}")
        return pd.DataFrame(columns=['group_name', 'is_despesa', 'is_custo_viagem'])

def get_all_expense_groups(apartamento_id: int):
    # MODIFICADO: Passa o apartamento_id para a função get_all_group_flags
    df_flags = get_all_group_flags(apartamento_id)
    
    if df_flags.empty:
        return []
    return df_flags['group_name'].dropna().unique().tolist()

def update_all_group_flags(apartamento_id: int, update_data):
    with db.get_db_connection() as conn:
        if conn is None: return
        cursor = conn.cursor()
        try:
            is_sqlite = isinstance(conn, sqlite3.Connection)
            placeholder = "?" if is_sqlite else "%s"
            
            # Etapa 1: Atualiza a tabela de regras (static_expense_groups)
            # MODIFICADO: Adicionado AND "apartamento_id" para garantir a alteração apenas no inquilino correto.
            sql_update_flags = f'UPDATE "static_expense_groups" SET "is_despesa" = {placeholder}, "is_custo_viagem" = {placeholder} WHERE "group_name" = {placeholder} AND "apartamento_id" = {placeholder}'
            for group_name, classification in update_data.items():
                is_despesa = 'S' if classification == 'despesa' else 'N'
                is_custo = 'S' if classification == 'custo_viagem' else 'N'
                cursor.execute(sql_update_flags, (is_despesa, is_custo, group_name, apartamento_id))
            
            # Etapa 2: Sincroniza a coluna 'despesa' e 'custoTotal' na tabela principal com base nas regras
            # MODIFICADO: Passa o apartamento_id para buscar as regras corretas.
            df_flags = get_all_group_flags(apartamento_id)

            grupos_de_despesa = df_flags[df_flags['is_despesa'] == 'S']['group_name'].tolist()
            if grupos_de_despesa:
                placeholders_s = ','.join([placeholder] * len(grupos_de_despesa))
                # MODIFICADO: Adicionado AND "apartamento_id"
                sql_update_s = f'UPDATE "relFilDespesasGerais" SET "despesa" = \'S\' WHERE "descGrupoD" IN ({placeholders_s}) AND "apartamento_id" = {placeholder}'
                cursor.execute(sql_update_s, grupos_de_despesa + [apartamento_id])

            grupos_de_custo = df_flags[df_flags['is_custo_viagem'] == 'S']['group_name'].tolist()
            if grupos_de_custo:
                placeholders_n = ','.join([placeholder] * len(grupos_de_custo))
                # MODIFICADO: Adicionado AND "apartamento_id"
                sql_update_n = f'UPDATE "relFilDespesasGerais" SET "despesa" = \'N\' WHERE "descGrupoD" IN ({placeholders_n}) AND "apartamento_id" = {placeholder}'
                cursor.execute(sql_update_n, grupos_de_custo + [apartamento_id])

            grupos_nenhum = df_flags[(df_flags['is_despesa'] == 'N') & (df_flags['is_custo_viagem'] == 'N')]['group_name'].tolist()
            if grupos_nenhum:
                placeholders_zero = ','.join([placeholder] * len(grupos_nenhum))
                # MODIFICADO: Adicionado AND "apartamento_id"
                sql_update_zero = f'UPDATE "relFilDespesasGerais" SET "despesa" = \'0\' WHERE "descGrupoD" IN ({placeholders_zero}) AND "apartamento_id" = {placeholder}'
                cursor.execute(sql_update_zero, grupos_nenhum + [apartamento_id])

            # Etapa 3: Atualiza a coluna custoTotal
            if grupos_de_custo:
                placeholders_custo = ','.join([placeholder]*len(grupos_de_custo))
                # MODIFICADO: Adicionado AND "apartamento_id"
                sql_update_custo = f'UPDATE "relFilDespesasGerais" SET "custoTotal" = "valorNota" WHERE "descGrupoD" IN ({placeholders_custo}) AND "apartamento_id" = {placeholder}'
                cursor.execute(sql_update_custo, grupos_de_custo + [apartamento_id])
            
            # MODIFICADO: Adicionado WHERE/AND "apartamento_id" para garantir que a atualização afete apenas o inquilino
            sql_update_nao_custo_base = f'UPDATE "relFilDespesasGerais" SET "custoTotal" = 0 WHERE "apartamento_id" = {placeholder}'
            params_nao_custo = [apartamento_id]
            if grupos_de_custo:
                placeholders_nao_custo = ','.join([placeholder]*len(grupos_de_custo))
                sql_update_nao_custo = f'{sql_update_nao_custo_base} AND "descGrupoD" NOT IN ({placeholders_nao_custo})'
                params_nao_custo.extend(grupos_de_custo)
                cursor.execute(sql_update_nao_custo, params_nao_custo)
            else:
                 cursor.execute(sql_update_nao_custo_base, params_nao_custo)

            conn.commit()
            print(f"Flags, despesa e custoTotal atualizados com sucesso para o apartamento {apartamento_id}.")
        except Exception as e:
            print(f"Erro ao atualizar flags de grupo de despesa: {e}")
            conn.rollback()

def get_unique_plates(apartamento_id: int) -> list[str]:
    
    # MODIFICADO: Passa o apartamento_id para buscar os dados do inquilino correto.
    df_viagens = get_data_as_dataframe("relFilViagensFatCliente", apartamento_id)
    df_despesas = get_data_as_dataframe("relFilDespesasGerais", apartamento_id)
    
    plates = pd.Series(dtype=str)
    if 'placaVeiculo' in df_viagens.columns:
        plates = pd.concat([plates, df_viagens['placaVeiculo'].dropna().astype(str).str.upper()])
    if 'placaVeiculo' in df_despesas.columns:
        plates = pd.concat([plates, df_despesas['placaVeiculo'].dropna().astype(str).str.upper()])
    
    if plates.empty:
        return ["Todos"]
    return ["Todos"] + sorted(plates.unique().tolist())
def get_unique_filiais(apartamento_id: int) -> list[str]:
    table_names = ["relFilViagensFatCliente", "relFilDespesasGerais", "relFilContasPagarDet", "relFilContasReceber"]
    
    # MODIFICADO: Passa o apartamento_id para a busca de dados em cada tabela.
    all_dfs = [get_data_as_dataframe(name, apartamento_id) for name in table_names]
    
    filiais = pd.Series(dtype=str)
    for df in all_dfs:
        for col in ['nomeFilial', 'nomeFil']:
            if col in df.columns:
                filiais = pd.concat([filiais, df[col].dropna().astype(str).str.upper()])
    
    if filiais.empty:
        return ["Todos"]
    return ["Todos"] + sorted(filiais.unique().tolist())

def get_faturamento_details_dashboard_data(apartamento_id: int, start_date, end_date, placa_filter, filial_filter):
    """Prepara os dados para todos os gráficos da página de detalhes de faturamento."""
    
    # MODIFICADO: Passa o apartamento_id para buscar os dados brutos
    df_fat_raw = get_data_as_dataframe("relFilViagensFatCliente", apartamento_id)
    df_fat = apply_filters_to_df(df_fat_raw, start_date, end_date, placa_filter, filial_filter)

    df_viagens_raw = get_data_as_dataframe("relFilViagensCliente", apartamento_id)
    df_viagens = apply_filters_to_df(df_viagens_raw, start_date, end_date, placa_filter, filial_filter)
    
    dashboard_data = {}
    periodo = 'D' if start_date and end_date else 'M'

    # --- Lógica de Custo completa para o gráfico de evolução ---
    # MODIFICADO: Passa o apartamento_id
    df_despesas_raw = get_data_as_dataframe("relFilDespesasGerais", apartamento_id)
    df_despesas_filtrado = apply_filters_to_df(df_despesas_raw, start_date, end_date, placa_filter, filial_filter)
    
    # MODIFICADO: Passa o apartamento_id
    df_flags = get_all_group_flags(apartamento_id)
    flags_dict = df_flags.set_index('group_name').to_dict('index') if not df_flags.empty else {}
    
    df_despesas_processed = df_despesas_filtrado.drop_duplicates(subset=['dataControle', 'numNota', 'valorVenc']) if not df_despesas_filtrado.empty else pd.DataFrame()
    df_com_flags = pd.merge(df_despesas_processed, df_flags, left_on='descGrupoD', right_on='group_name', how='left') if not df_despesas_processed.empty and not df_flags.empty else df_despesas_processed
    
    if not df_com_flags.empty:
        df_com_flags['is_custo_viagem'] = df_com_flags['is_custo_viagem'].fillna('N')
        df_com_flags['is_despesa'] = df_com_flags['is_despesa'].fillna('S')
    
    df_custos_final = df_com_flags[df_com_flags['is_custo_viagem'] == 'S'].copy() if not df_com_flags.empty else pd.DataFrame()
    
    # --- LÓGICA DE COMISSÃO E QUEBRA ---
    comissao_df_data = pd.DataFrame()
    if not df_viagens.empty and all(c in df_viagens.columns for c in ['tipoFrete', 'freteMotorista', 'comissao', 'dataViagemMotorista']):
        df_comissao_base = df_viagens[(df_viagens['tipoFrete'].astype(str).str.strip().str.upper() == 'P') & (pd.to_numeric(df_viagens['freteMotorista'], errors='coerce') > 0)].copy()
        if not df_comissao_base.empty:
            df_comissao_base['valorNota'] = pd.to_numeric(df_comissao_base['freteMotorista'], errors='coerce').fillna(0) * (pd.to_numeric(df_comissao_base['comissao'], errors='coerce').fillna(0) / 100)
            comissao_df_data = df_comissao_base[['dataViagemMotorista', 'valorNota']].rename(columns={'dataViagemMotorista': 'dataControle'})

    quebra_df_data = pd.DataFrame()
    if not df_fat.empty and 'valorQuebra' in df_fat.columns:
        df_quebra_base = df_fat[['dataViagemMotorista', 'valorQuebra']].copy()
        quebra_df_data = df_quebra_base.rename(columns={'valorQuebra': 'valorNota', 'dataViagemMotorista': 'dataControle'})
        
    if not quebra_df_data.empty:
        if flags_dict.get('VALOR QUEBRA', {}).get('is_custo_viagem') == 'S':
            df_custos_final = pd.concat([df_custos_final, quebra_df_data], ignore_index=True)
        
    if not comissao_df_data.empty:
        comissao_flags = flags_dict.get('COMISSÃO DE MOTORISTA', {})
        if comissao_flags.get('is_custo_viagem') == 'S':
            df_custos_final = pd.concat([df_custos_final, comissao_df_data], ignore_index=True)
    # --- FIM DA LÓGICA ---

    # Gráfico 1: Evolução Faturamento vs. Custo
    fat_evolucao = pd.Series(dtype=float)
    if not df_fat.empty and 'dataViagemMotorista' in df_fat.columns:
        df_fat['Periodo'] = pd.to_datetime(df_fat['dataViagemMotorista'], errors='coerce', dayfirst=True).dt.to_period(periodo)
        fat_evolucao = df_fat.groupby('Periodo')['freteEmpresa'].sum()

    custo_evolucao = pd.Series(dtype=float)
    if not df_custos_final.empty and 'dataControle' in df_custos_final.columns:
        df_custos_final['Periodo'] = pd.to_datetime(df_custos_final['dataControle'], errors='coerce', dayfirst=True).dt.to_period(periodo)
        custo_evolucao = df_custos_final.groupby('Periodo')['valorNota'].sum()
        
    evolucao_df = pd.DataFrame({'Faturamento': fat_evolucao, 'Custo': custo_evolucao}).fillna(0).reset_index()
    
    evolucao_df.rename(columns={'index': 'Periodo'}, inplace=True)
    
    evolucao_df['Periodo'] = evolucao_df['Periodo'].astype(str)
    dashboard_data['evolucao_faturamento_custo'] = evolucao_df.to_dict('records')
    
    # Gráficos de Agrupamento
    if not df_fat.empty:
        top_clientes = df_fat.groupby('nomeCliente')['freteEmpresa'].sum().nlargest(10).reset_index()
        dashboard_data['top_clientes'] = top_clientes.to_dict(orient='records')

        fat_filial = df_fat.groupby('nomeFilial')['freteEmpresa'].sum().reset_index()
        dashboard_data['faturamento_filial'] = fat_filial.to_dict(orient='records')

        viagens_veiculo = df_fat['placa'].value_counts().nlargest(10).reset_index()
        viagens_veiculo.columns = ['placa', 'contagem']
        dashboard_data['viagens_por_veiculo'] = viagens_veiculo.to_dict(orient='records')
        
        fat_motorista = df_fat.groupby('nomeMot')['freteEmpresa'].sum().nlargest(10).reset_index()
        dashboard_data['faturamento_motorista'] = fat_motorista.to_dict(orient='records')
        
        if 'cidOrig' in df_fat.columns and 'cidDest' in df_fat.columns:
            df_fat['rota'] = df_fat['cidOrig'].str.strip() + ' -> ' + df_fat['cidDest'].str.strip()
            top_rotas = df_fat['rota'].value_counts().nlargest(10).reset_index()
            top_rotas.columns = ['rota', 'contagem']
            dashboard_data['top_rotas'] = top_rotas.to_dict(orient='records')

    if not df_viagens.empty:
        if 'cidOrigemFormat' in df_viagens.columns and 'cidDestinoFormat' in df_viagens.columns and 'pesoSaida' in df_viagens.columns:
            df_viagens['rota'] = df_viagens['cidOrigemFormat'].str.strip() + ' -> ' + df_viagens['cidDestinoFormat'].str.strip()
            volume_rota = df_viagens.groupby('rota')['pesoSaida'].sum().nlargest(10).reset_index()
            dashboard_data['volume_por_rota'] = volume_rota.to_dict(orient='records')
            
    return dashboard_data
            
def ler_configuracoes_robo(apartamento_id: int):
    """Lê as configurações do robô de um inquilino específico."""
    
    # MODIFICADO: Passa o apartamento_id para buscar as configurações corretas.
    df = get_data_as_dataframe("configuracoes_robo", apartamento_id)
    
    if df.empty:
        return {}
    # Transforma o dataframe em um dicionário chave: valor
    return pd.Series(df.valor.values, index=df.chave).to_dict()

def salvar_configuracoes_robo(apartamento_id: int, configs: dict):
    """Salva um dicionário de configurações para um inquilino específico."""
    with db.get_db_connection() as conn:
        if conn is None: 
            print("ERRO: Não foi possível conectar ao banco de dados para salvar as configurações.")
            return
            
        is_sqlite = isinstance(conn, sqlite3.Connection)
        
        # MODIFICADO: A query de INSERT agora inclui a coluna 'apartamento_id'.
        if is_sqlite:
            sql = 'INSERT OR REPLACE INTO "configuracoes_robo" (apartamento_id, chave, valor) VALUES (?, ?, ?)'
        else: # PostgreSQL
            # MODIFICADO: A cláusula ON CONFLICT agora usa a chave composta (apartamento_id, chave)
            sql = 'INSERT INTO "configuracoes_robo" (apartamento_id, chave, valor) VALUES (%s, %s, %s) ON CONFLICT (apartamento_id, chave) DO UPDATE SET valor = EXCLUDED.valor'
            
        try:
            cursor = conn.cursor()
            for chave, valor in configs.items():
                if valor is not None:
                    # MODIFICADO: Passa o apartamento_id como o primeiro parâmetro para a query
                    cursor.execute(sql, (apartamento_id, chave, str(valor)))
            
            conn.commit()
            print(f"Configurações salvas com sucesso para o apartamento {apartamento_id}.")
        except Exception as e:
            conn.rollback()
            print(f"ERRO CRÍTICO ao salvar configurações para o apartamento {apartamento_id}: {e}")
            
def get_users_for_apartment(apartamento_id: int):
    """Busca todos os utilizadores de um apartamento específico."""
    try:
        with db.get_db_connection() as conn:
            if conn is None: return []
            # Usamos pd.read_sql para obter uma lista de dicionários facilmente
            df = pd.read_sql('SELECT id, nome, email, role FROM usuarios WHERE apartamento_id = ?', conn, params=(apartamento_id,))
            return df.to_dict(orient='records')
    except Exception as e:
        print(f"Erro ao buscar utilizadores: {e}")
        return []

def add_user_to_apartment(apartamento_id: int, nome: str, email: str, password_hash: str, role: str):
    """Adiciona um novo utilizador a um apartamento específico."""
    with db.get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                'INSERT INTO usuarios (apartamento_id, nome, email, password_hash, role) VALUES (?, ?, ?, ?, ?)',
                (apartamento_id, nome, email, password_hash, role)
            )
            conn.commit()
            return True, "Utilizador adicionado com sucesso."
        except sqlite3.IntegrityError:
            return False, "Erro: Este email já está registado."
        except Exception as e:
            return False, f"Erro ao adicionar utilizador: {e}"

def update_user_in_apartment(user_id: int, apartamento_id: int, nome: str, email: str, role: str, new_password_hash: str = None):
    """Atualiza os dados de um utilizador, opcionalmente a senha."""
    with db.get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            if new_password_hash:
                # Se uma nova senha foi fornecida, atualiza tudo incluindo a senha
                cursor.execute(
                    'UPDATE usuarios SET nome = ?, email = ?, role = ?, password_hash = ? WHERE id = ? AND apartamento_id = ?',
                    (nome, email, role, new_password_hash, user_id, apartamento_id)
                )
            else:
                # Caso contrário, atualiza apenas os outros dados
                cursor.execute(
                    'UPDATE usuarios SET nome = ?, email = ?, role = ? WHERE id = ? AND apartamento_id = ?',
                    (nome, email, role, user_id, apartamento_id)
                )
            conn.commit()
            return True, "Utilizador atualizado com sucesso."
        except sqlite3.IntegrityError:
            return False, "Erro: Este email já pertence a outro utilizador."
        except Exception as e:
            return False, f"Erro ao atualizar utilizador: {e}"

def delete_user_from_apartment(user_id: int, apartamento_id: int):
    """Apaga um utilizador de um apartamento."""
    with db.get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM usuarios WHERE id = ? AND apartamento_id = ?', (user_id, apartamento_id))
            conn.commit()
            return True, "Utilizador apagado com sucesso."
        except Exception as e:
            return False, f"Erro ao apagar utilizador: {e}"

def get_user_by_id(user_id: int, apartamento_id: int):
    """Busca um único utilizador pelo seu ID, garantindo que ele pertence ao apartamento correto."""
    try:
        with db.get_db_connection() as conn:
            if conn is None: return None
            user_data = pd.read_sql('SELECT id, nome, email, role FROM usuarios WHERE id = ? AND apartamento_id = ?', conn, params=(user_id, apartamento_id))
            if user_data.empty:
                return None
            return user_data.to_dict(orient='records')[0]
    except Exception as e:
        print(f"Erro ao buscar utilizador por ID: {e}")
        return None

def get_all_apartments():
    """Busca todos os apartamentos da base de dados."""
    try:
        with db.get_db_connection() as conn:
            if conn is None: return []
            df = pd.read_sql('SELECT id, nome_empresa, status, data_criacao FROM apartamentos', conn)
            # Futuramente, podemos adicionar uma contagem de utilizadores e uso de dados aqui
            return df.to_dict(orient='records')
    except Exception as e:
        print(f"Erro ao buscar apartamentos: {e}")
        return []

def create_apartment_and_admin(nome_empresa: str, admin_nome: str, admin_email: str, password_hash: str):
    """Cria um novo apartamento e o seu primeiro utilizador admin numa única transação."""
    with db.get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            # Cria o apartamento
            now = datetime.now().isoformat()
            cursor.execute(
                'INSERT INTO apartamentos (nome_empresa, status, data_criacao) VALUES (?, ?, ?)',
                (nome_empresa, 'ativo', now)
            )
            apartamento_id = cursor.lastrowid
            
            # Cria o utilizador admin para esse apartamento
            cursor.execute(
                'INSERT INTO usuarios (apartamento_id, nome, email, password_hash, role) VALUES (?, ?, ?, ?, ?)',
                (apartamento_id, admin_nome, admin_email, password_hash, 'admin')
            )
            
            conn.commit()
            return True, f"Apartamento '{nome_empresa}' e admin '{admin_email}' criados com sucesso."
        except sqlite3.IntegrityError:
            conn.rollback()
            return False, "Erro: O email do administrador já existe na base de dados."
        except Exception as e:
            conn.rollback()
            return False, f"Ocorreu um erro inesperado: {e}"
    
def get_apartment_details(apartamento_id: int):
    """Busca os detalhes de um único apartamento pelo seu ID."""
    try:
        with db.get_db_connection() as conn:
            if conn is None: return None
            df = pd.read_sql('SELECT * FROM apartamentos WHERE id = ?', conn, params=(apartamento_id,))
            if df.empty:
                return None
            return df.to_dict(orient='records')[0]
    except Exception as e:
        print(f"Erro ao buscar detalhes do apartamento: {e}")
        return None

def update_apartment_details(apartamento_id: int, nome_empresa: str, status: str, data_vencimento: str, notas: str):
    """Atualiza os detalhes de um apartamento específico."""
    with db.get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE apartamentos SET nome_empresa = ?, status = ?, data_vencimento = ?, notas_admin = ? WHERE id = ?',
                (nome_empresa, status, data_vencimento, notas, apartamento_id)
            )
            conn.commit()
            return True, "Apartamento atualizado com sucesso."
        except Exception as e:
            conn.rollback()
            return False, f"Ocorreu um erro ao atualizar o apartamento: {e}"

def get_apartments_with_usage_stats():
    """
    Busca todos os apartamentos e calcula o total de registros de dados para cada um.
    """
    # Lista de tabelas que contêm dados de clientes e, portanto, a coluna apartamento_id.
    data_tables = [info["table_name"] for info in config.EXCEL_FILES_CONFIG.values()]

    try:
        with db.get_db_connection() as conn:
            if conn is None:
                print("ERRO: Não foi possível conectar ao banco de dados.")
                return []

            # 1. Busca a lista base de todos os apartamentos.
            df_apartamentos = pd.read_sql('SELECT id, nome_empresa, status, data_criacao FROM apartamentos', conn)
            if df_apartamentos.empty:
                return []

            apartamentos_list = df_apartamentos.to_dict(orient='records')
            cursor = conn.cursor()

            # 2. Para cada apartamento, conta os registros em todas as tabelas de dados.
            for apt in apartamentos_list:
                total_registos = 0
                apt_id = apt['id']
                
                for table in data_tables:
                    # Verifica se a tabela realmente existe antes de tentar contar
                    # Usamos a função table_exists() que já existe em database.py
                    if db.table_exists(table):
                        query = f'SELECT COUNT(*) FROM "{table}" WHERE "apartamento_id" = ?'
                        cursor.execute(query, (apt_id,))
                        count_result = cursor.fetchone()
                        if count_result:
                            total_registos += count_result[0]
                
                apt['total_registos'] = total_registos
            
            return apartamentos_list

    except Exception as e:
        print(f"Erro ao buscar apartamentos com estatísticas de uso: {e}")
        return []


        
