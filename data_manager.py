# data_manager.py (versão final com todas as regras implementadas)

import pandas as pd
from datetime import datetime
import database as db 
import config
import sqlite3
import os

def get_data_as_dataframe(table_name: str) -> pd.DataFrame:
    db_url = os.getenv('DATABASE_URL')
    if not db_url and not os.path.exists(db.DATABASE_NAME):
        return pd.DataFrame()
    try:
        with db.get_db_connection() as conn:
            if conn is None: return pd.DataFrame()
            query_check_table = f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"
            cursor = conn.cursor()
            cursor.execute(query_check_table)
            result = cursor.fetchone()
            if result is None or result[0] is None:
                 return pd.DataFrame()
            df = pd.read_sql_query(f'SELECT * FROM "{table_name}"', conn)
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
def _get_final_dataframes(start_date, end_date, placa_filter, filial_filter):
    # 1. Pega os dados brutos e aplica os filtros globais
    df_viagens_faturamento = apply_filters_to_df(get_data_as_dataframe("relFilViagensFatCliente"), start_date, end_date, placa_filter, filial_filter)
    df_viagens_cliente = apply_filters_to_df(get_data_as_dataframe("relFilViagensCliente"), start_date, end_date, placa_filter, filial_filter)
    df_despesas_raw = get_data_as_dataframe("relFilDespesasGerais")
    df_despesas_filtrado = apply_filters_to_df(df_despesas_raw, start_date, end_date, placa_filter, filial_filter)
    
    df_flags = get_all_group_flags()
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

def get_dashboard_summary(start_date: datetime = None, end_date: datetime = None, placa_filter: str = "Todos", filial_filter: str = "Todos") -> dict:
    summary = {}
    
    # --- 1. LÓGICA DE CONTAS PENDENTES (Inalterada) ---
    df_contas_pagar_raw = get_data_as_dataframe("relFilContasPagarDet")
    pending_pagar = 0
    if not df_contas_pagar_raw.empty and 'codTransacao' in df_contas_pagar_raw.columns:
        pendentes_df = df_contas_pagar_raw[df_contas_pagar_raw['codTransacao'].fillna('').str.strip() == '']
        unicas_df = pendentes_df.drop_duplicates(subset=['dataVenc', 'numNota', 'nomeForn'])
        pending_pagar = unicas_df['valorVenc'].sum() if 'valorVenc' in unicas_df.columns else 0
    summary['saldo_contas_a_pagar_pendentes'] = pending_pagar
    
    df_contas_receber_raw = get_data_as_dataframe("relFilContasReceber")
    summary['saldo_contas_a_receber_pendentes'] = df_contas_receber_raw[df_contas_receber_raw['codTransacao'].fillna('').str.strip() == '']['valorVenc'].sum() if not df_contas_receber_raw.empty and 'codTransacao' in df_contas_receber_raw.columns else 0
    
    # --- 2. LÓGICA DE CÁLCULO COMPLETA ---
    # Carrega e aplica os filtros globais a todas as tabelas necessárias
    df_viagens_faturamento = apply_filters_to_df(get_data_as_dataframe("relFilViagensFatCliente"), start_date, end_date, placa_filter, filial_filter)
    df_viagens_cliente = apply_filters_to_df(get_data_as_dataframe("relFilViagensCliente"), start_date, end_date, placa_filter, filial_filter)
    df_despesas_filtrado = apply_filters_to_df(get_data_as_dataframe("relFilDespesasGerais"), start_date, end_date, placa_filter, filial_filter)
    
    df_flags = get_all_group_flags()
    flags_dict = df_flags.set_index('group_name').to_dict('index') if not df_flags.empty else {}
    
    # Processa as despesas base (remove duplicatas e junta com as flags)
    df_despesas_processed = df_despesas_filtrado.drop_duplicates(subset=['dataControle', 'numNota', 'valorVenc']) if not df_despesas_filtrado.empty else pd.DataFrame()
    df_com_flags = pd.merge(df_despesas_processed, df_flags, left_on='descGrupoD', right_on='group_name', how='left') if not df_despesas_processed.empty and not df_flags.empty else df_despesas_processed
    
    if not df_com_flags.empty:
        df_com_flags['is_custo_viagem'] = df_com_flags['is_custo_viagem'].fillna('N')
        df_com_flags['is_despesa'] = df_com_flags['is_despesa'].fillna('S')
    
    # Separa os DataFrames de Custo e Despesa com base nas flags
    df_custos = df_com_flags[df_com_flags['is_custo_viagem'] == 'S'].copy() if not df_com_flags.empty else pd.DataFrame()
    df_despesas_gerais = df_com_flags[df_com_flags['is_despesa'] == 'S'].copy() if not df_com_flags.empty else pd.DataFrame()

    # --- LÓGICA DE COMISSÃO E QUEBRA QUE FALTAVA ---
    # Calcula a Comissão do Motorista
    total_comissao_motorista = 0
    if not df_viagens_cliente.empty and all(c in df_viagens_cliente.columns for c in ['tipoFrete', 'freteMotorista', 'comissao']):
        df_comissao_base = df_viagens_cliente[(df_viagens_cliente['tipoFrete'].astype(str).str.strip().str.upper() == 'P') & (pd.to_numeric(df_viagens_cliente['freteMotorista'], errors='coerce') > 0)].copy()
        if not df_comissao_base.empty:
            frete_motorista = pd.to_numeric(df_comissao_base['freteMotorista'], errors='coerce').fillna(0)
            percentual_comissao = pd.to_numeric(df_comissao_base['comissao'], errors='coerce').fillna(0)
            total_comissao_motorista = (frete_motorista * (percentual_comissao / 100)).sum()
            
    # Calcula o Valor Quebra
    valor_quebra_sum = df_viagens_faturamento['valorQuebra'].sum() if 'valorQuebra' in df_viagens_faturamento.columns else 0

    # Pega os totais base de Custo e Despesa
    custo_base = df_custos['valorNota'].sum() if 'valorNota' in df_custos.columns else 0
    despesa_base = df_despesas_gerais['valorNota'].sum() if 'valorNota' in df_despesas_gerais.columns else 0
    
    # Adiciona comissão e quebra aos totais, de acordo com as regras
    if flags_dict.get('VALOR QUEBRA', {}).get('is_custo_viagem') == 'S':
        custo_base += valor_quebra_sum
    elif flags_dict.get('VALOR QUEBRA', {}).get('is_despesa') == 'S':
        despesa_base += valor_quebra_sum
        
    comissao_flags = flags_dict.get('COMISSÃO DE MOTORISTA', {})
    if comissao_flags.get('is_custo_viagem') == 'S':
        custo_base += total_comissao_motorista
    elif comissao_flags.get('is_despesa') == 'S':
        despesa_base += total_comissao_motorista
    
    # --- 3. Atribui os valores FINAIS e COMPLETOS ao summary ---
    summary['faturamento_total_viagens'] = df_viagens_faturamento['freteEmpresa'].sum() if 'freteEmpresa' in df_viagens_faturamento.columns else 0
    summary['custo_total_viagem'] = custo_base
    summary['total_despesas_gerais'] = despesa_base

    # Calcula os KPIs finais com base nos valores corretos
    custo_operacional_total = summary['custo_total_viagem'] + summary['total_despesas_gerais']
    summary['saldo_geral'] = summary['faturamento_total_viagens'] - custo_operacional_total
    summary['margem_frete'] = (summary['saldo_geral'] / summary['faturamento_total_viagens'] * 100) if summary.get('faturamento_total_viagens', 0) > 0 else 0
    
    return summary

# data_manager.py (substitua esta função)


def get_monthly_summary(start_date, end_date, placa_filter, filial_filter) -> pd.DataFrame:
    periodo_format = 'D' if start_date and end_date else 'M'
    
    # --- LÓGICA COMPLETA E CORRIGIDA (ESPELHADA NOS KPIs) ---
    
    # 1. Carrega e aplica filtros globais a todas as tabelas
    df_viagens_faturamento = apply_filters_to_df(get_data_as_dataframe("relFilViagensFatCliente"), start_date, end_date, placa_filter, filial_filter)
    df_viagens_cliente = apply_filters_to_df(get_data_as_dataframe("relFilViagensCliente"), start_date, end_date, placa_filter, filial_filter)
    df_despesas_filtrado = apply_filters_to_df(get_data_as_dataframe("relFilDespesasGerais"), start_date, end_date, placa_filter, filial_filter)
    
    df_flags = get_all_group_flags()
    flags_dict = df_flags.set_index('group_name').to_dict('index') if not df_flags.empty else {}

    # 2. Processa despesas base (remove duplicatas e junta com as flags)
    df_despesas_processed = df_despesas_filtrado.drop_duplicates(subset=['dataControle', 'numNota', 'valorVenc']) if not df_despesas_filtrado.empty else pd.DataFrame()
    df_com_flags = pd.merge(df_despesas_processed, df_flags, left_on='descGrupoD', right_on='group_name', how='left') if not df_despesas_processed.empty and not df_flags.empty else df_despesas_processed
    
    if not df_com_flags.empty:
        df_com_flags['is_custo_viagem'] = df_com_flags['is_custo_viagem'].fillna('N')
        df_com_flags['is_despesa'] = df_com_flags['is_despesa'].fillna('S')
    
    df_custos = df_com_flags[df_com_flags['is_custo_viagem'] == 'S'].copy() if not df_com_flags.empty else pd.DataFrame()
    df_despesas_gerais = df_com_flags[df_com_flags['is_despesa'] == 'S'].copy() if not df_com_flags.empty else pd.DataFrame()

    # 3. Calcula e adiciona "Comissão" e "Quebra" (A LÓGICA QUE FALTAVA)
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
    # --- FIM DA LÓGICA COMPLETA ---

    # 4. Agrupa os resultados FINAIS para o gráfico
    faturamento = pd.Series(dtype=float)
    if not df_viagens_faturamento.empty and 'dataViagemMotorista' in df_viagens_faturamento.columns:
        df_viagens_faturamento['Periodo'] = pd.to_datetime(df_viagens_faturamento['dataViagemMotorista'], errors='coerce', dayfirst=True).dt.to_period(periodo_format)
        faturamento = df_viagens_faturamento.groupby('Periodo')['freteEmpresa'].sum()

    despesas_agrupadas = pd.Series(dtype=float)
    if not df_despesas_gerais.empty and 'dataControle' in df_despesas_gerais.columns:
        df_despesas_gerais['Periodo'] = pd.to_datetime(df_despesas_gerais['dataControle'], errors='coerce', dayfirst=True).dt.to_period(periodo_format)
        despesas_agrupadas = df_despesas_gerais.groupby('Periodo')['valorNota'].sum()

    custos_agrupados = pd.Series(dtype=float)
    if not df_custos.empty and 'dataControle' in df_custos.columns:
        df_custos['Periodo'] = pd.to_datetime(df_custos['dataControle'], errors='coerce', dayfirst=True).dt.to_period(periodo_format)
        custos_agrupados = df_custos.groupby('Periodo')['valorNota'].sum()
        
    monthly_df = pd.DataFrame({'Faturamento': faturamento, 'Custo': custos_agrupados, 'DespesasGerais': despesas_agrupadas}).fillna(0)
    
    if isinstance(monthly_df.index, pd.PeriodIndex):
        monthly_df['PeriodoLabel'] = monthly_df.index.strftime('%Y-%m-%d' if periodo_format == 'D' else '%Y-%m')
    else:
        monthly_df['PeriodoLabel'] = None
        
    return monthly_df.reset_index(drop=True)

def get_relFilViagensFatCliente_df(start_date=None, end_date=None, placa_filter="Todos", filial_filter="Todos"):
    df = get_data_as_dataframe("relFilViagensFatCliente")
    if 'permiteFaturar' in df.columns:
        df = df[df['permiteFaturar'].astype(str).str.upper() == 'S']
    return apply_filters_to_df(df, start_date, end_date, placa_filter, filial_filter)

def sync_expense_groups():
    print("Sincronizando grupos de despesa...")
    df_despesas = get_data_as_dataframe("relFilDespesasGerais")
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
            if is_sqlite:
                cursor.execute('INSERT OR IGNORE INTO "static_expense_groups" ("group_name") VALUES (?)', (group_name,))
            else:
                cursor.execute('INSERT INTO "static_expense_groups" ("group_name") VALUES (%s) ON CONFLICT("group_name") DO NOTHING', (group_name,))
        conn.commit()
    print("Sincronização concluída.")

def get_all_group_flags():
    try:
        with db.get_db_connection() as conn:
            if conn is None:
                return pd.DataFrame(columns=['group_name', 'is_despesa', 'is_custo_viagem'])
            df = pd.read_sql('SELECT "group_name", "is_despesa", "is_custo_viagem" FROM "static_expense_groups"', conn)
            return df
    except Exception as e:
        print(f"Erro ao buscar flags de grupo: {e}")
        return pd.DataFrame(columns=['group_name', 'is_despesa', 'is_custo_viagem'])

def get_all_expense_groups():
    df_flags = get_all_group_flags()
    if df_flags.empty:
        return []
    return df_flags['group_name'].dropna().unique().tolist()

def update_all_group_flags(update_data):
    with db.get_db_connection() as conn:
        if conn is None: return
        cursor = conn.cursor()
        try:
            is_sqlite = isinstance(conn, sqlite3.Connection)
            placeholder = "?" if is_sqlite else "%s"
            
            # Etapa 1: Atualiza a tabela de regras (static_expense_groups)
            sql_update_flags = f'UPDATE "static_expense_groups" SET "is_despesa" = {placeholder}, "is_custo_viagem" = {placeholder} WHERE "group_name" = {placeholder}'
            for group_name, classification in update_data.items():
                is_despesa = 'S' if classification == 'despesa' else 'N'
                is_custo = 'S' if classification == 'custo_viagem' else 'N'
                cursor.execute(sql_update_flags, (is_despesa, is_custo, group_name))
            
            # Etapa 2: Sincroniza a coluna 'despesa' na tabela principal com base nas regras
            print("Sincronizando a coluna 'despesa' em relFilDespesasGerais com as novas regras...")
            df_flags = get_all_group_flags()

            grupos_de_despesa = df_flags[df_flags['is_despesa'] == 'S']['group_name'].tolist()
            if grupos_de_despesa:
                placeholders_s = ','.join([placeholder] * len(grupos_de_despesa))
                sql_update_s = f'UPDATE "relFilDespesasGerais" SET "despesa" = \'S\' WHERE "descGrupoD" IN ({placeholders_s})'
                cursor.execute(sql_update_s, grupos_de_despesa)
                print(f"{cursor.rowcount} linhas atualizadas para despesa = 'S'")

            grupos_de_custo = df_flags[df_flags['is_custo_viagem'] == 'S']['group_name'].tolist()
            if grupos_de_custo:
                placeholders_n = ','.join([placeholder] * len(grupos_de_custo))
                sql_update_n = f'UPDATE "relFilDespesasGerais" SET "despesa" = \'N\' WHERE "descGrupoD" IN ({placeholders_n})'
                cursor.execute(sql_update_n, grupos_de_custo)
                print(f"{cursor.rowcount} linhas atualizadas para despesa = 'N'")

            grupos_nenhum = df_flags[(df_flags['is_despesa'] == 'N') & (df_flags['is_custo_viagem'] == 'N')]['group_name'].tolist()
            if grupos_nenhum:
                placeholders_zero = ','.join([placeholder] * len(grupos_nenhum))
                sql_update_zero = f'UPDATE "relFilDespesasGerais" SET "despesa" = \'0\' WHERE "descGrupoD" IN ({placeholders_zero})'
                cursor.execute(sql_update_zero, grupos_nenhum)
                print(f"{cursor.rowcount} linhas atualizadas para despesa = '0'")

            # Etapa 3: Atualiza a coluna custoTotal
            print("Atualizando a coluna custoTotal em relFilDespesasGerais...")
            if grupos_de_custo:
                placeholders_custo = ','.join([placeholder]*len(grupos_de_custo))
                sql_update_custo = f'UPDATE "relFilDespesasGerais" SET "custoTotal" = "valorNota" WHERE "descGrupoD" IN ({placeholders_custo})'
                cursor.execute(sql_update_custo, grupos_de_custo)
            
            sql_update_nao_custo_base = 'UPDATE "relFilDespesasGerais" SET "custoTotal" = 0'
            if grupos_de_custo:
                placeholders_nao_custo = ','.join([placeholder]*len(grupos_de_custo))
                sql_update_nao_custo = f'{sql_update_nao_custo_base} WHERE "descGrupoD" NOT IN ({placeholders_nao_custo})'
                cursor.execute(sql_update_nao_custo, grupos_de_custo)
            else:
                 cursor.execute(sql_update_nao_custo_base)

            conn.commit()
            print("Flags, despesa e custoTotal atualizados com sucesso.")
        except Exception as e:
            print(f"Erro ao atualizar flags de grupo de despesa: {e}")
            conn.rollback()

def get_unique_plates() -> list[str]:
    df_viagens = get_data_as_dataframe("relFilViagensFatCliente")
    df_despesas = get_data_as_dataframe("relFilDespesasGerais")
    plates = pd.Series(dtype=str)
    if 'placaVeiculo' in df_viagens.columns:
        plates = pd.concat([plates, df_viagens['placaVeiculo'].dropna().astype(str).str.upper()])
    if 'placaVeiculo' in df_despesas.columns:
        plates = pd.concat([plates, df_despesas['placaVeiculo'].dropna().astype(str).str.upper()])
    if plates.empty:
        return ["Todos"]
    return ["Todos"] + sorted(plates.unique().tolist())

def get_unique_filiais() -> list[str]:
    table_names = ["relFilViagensFatCliente", "relFilDespesasGerais", "relFilContasPagarDet", "relFilContasReceber"]
    all_dfs = [get_data_as_dataframe(name) for name in table_names]
    filiais = pd.Series(dtype=str)
    for df in all_dfs:
        for col in ['nomeFilial', 'nomeFil']:
            if col in df.columns:
                filiais = pd.concat([filiais, df[col].dropna().astype(str).str.upper()])
    if filiais.empty:
        return ["Todos"]
    return ["Todos"] + sorted(filiais.unique().tolist())


# data_manager.py (substitua esta função)

def get_faturamento_details_dashboard_data(start_date, end_date, placa_filter, filial_filter):
    """Prepara os dados para todos os gráficos da página de detalhes de faturamento."""
    
    # Busca os dados base já filtrados
    df_fat = apply_filters_to_df(get_data_as_dataframe("relFilViagensFatCliente"), start_date, end_date, placa_filter, filial_filter)
    df_viagens = apply_filters_to_df(get_data_as_dataframe("relFilViagensCliente"), start_date, end_date, placa_filter, filial_filter)
    
    dashboard_data = {}
    periodo = 'D' if start_date and end_date else 'M'

    # --- Lógica de Custo completa para o gráfico de evolução ---
    df_despesas_filtrado = apply_filters_to_df(get_data_as_dataframe("relFilDespesasGerais"), start_date, end_date, placa_filter, filial_filter)
    df_flags = get_all_group_flags()
    flags_dict = df_flags.set_index('group_name').to_dict('index') if not df_flags.empty else {}
    df_despesas_processed = df_despesas_filtrado.drop_duplicates(subset=['dataControle', 'numNota', 'valorVenc']) if not df_despesas_filtrado.empty else pd.DataFrame()
    df_com_flags = pd.merge(df_despesas_processed, df_flags, left_on='descGrupoD', right_on='group_name', how='left') if not df_despesas_processed.empty and not df_flags.empty else df_despesas_processed
    
    if not df_com_flags.empty:
        df_com_flags['is_custo_viagem'] = df_com_flags['is_custo_viagem'].fillna('N')
        df_com_flags['is_despesa'] = df_com_flags['is_despesa'].fillna('S')
    
    df_custos_final = df_com_flags[df_com_flags['is_custo_viagem'] == 'S'].copy() if not df_com_flags.empty else pd.DataFrame()
    
    # --- LÓGICA DE COMISSÃO E QUEBRA QUE FALTAVA ---
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
    # --- FIM DA LÓGICA FALTANTE ---

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
    
    # --- ADICIONE ESTA LINHA DE CORREÇÃO ---
    evolucao_df.rename(columns={'index': 'Periodo'}, inplace=True)
    # --- FIM DA CORREÇÃO ---
    
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
            
    # --- LINHA FALTANTE ADICIONADA ---
    return dashboard_data
            
def ler_configuracoes_robo():
    """Lê todas as configurações do robô do banco de dados."""
    df = get_data_as_dataframe("configuracoes_robo")
    if df.empty:
        return {}
    # Transforma o dataframe em um dicionário chave: valor
    return pd.Series(df.valor.values, index=df.chave).to_dict()
# data_manager.py (substitua esta função)

def salvar_configuracoes_robo(configs: dict):
    """Salva um dicionário de configurações no banco de dados."""
    with db.get_db_connection() as conn:
        if conn is None: return
        is_sqlite = isinstance(conn, sqlite3.Connection)
        placeholder = "?" if is_sqlite else "%s"
        
        if is_sqlite:
            sql = f'INSERT OR REPLACE INTO "configuracoes_robo" (chave, valor) VALUES ({placeholder}, {placeholder})'
        else: # PostgreSQL
            sql = f'INSERT INTO "configuracoes_robo" (chave, valor) VALUES ({placeholder}, {placeholder}) ON CONFLICT (chave) DO UPDATE SET valor = EXCLUDED.valor'
            
        cursor = conn.cursor()
        for chave, valor in configs.items():
            cursor.execute(sql, (chave, valor))
        conn.commit()