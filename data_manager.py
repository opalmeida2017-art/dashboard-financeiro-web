# data_manager.py (Versão com a regra de duplicatas final)
import pandas as pd
from datetime import datetime
import database as db 
import config
import sqlite3

def get_data_as_dataframe(table_name: str) -> pd.DataFrame:
    try:
        with db.get_db_connection() as conn:
            if conn is None: return pd.DataFrame()
            query_table_name = f'"{table_name}"'
            query_check_table = f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'" if isinstance(conn, sqlite3.Connection) else f"SELECT to_regclass('{table_name}')"
            cursor = conn.cursor()
            cursor.execute(query_check_table)
            result = cursor.fetchone()
            if result is None or result[0] is None:
                 print(f"AVISO: Tabela '{table_name}' não existe. Retornando DataFrame vazio.")
                 return pd.DataFrame()
            df = pd.read_sql_query(f'SELECT * FROM {query_table_name}', conn)
            df.columns = [str(col).strip() for col in df.columns]
            return df
    except Exception as e:
        print(f"ERRO CRÍTICO ao carregar dados da tabela '{table_name}': {e}")
        return pd.DataFrame()

def apply_filters_to_df(df: pd.DataFrame, date_column: str, start_date: datetime, end_date: datetime, placa_filter: str, filial_filter: str) -> pd.DataFrame:
    if df.empty: return df
    df = df.copy()
    
    if date_column in df.columns and (start_date or end_date):
        df[date_column] = pd.to_datetime(df[date_column], errors='coerce')
        df = df.dropna(subset=[date_column])
        if not df.empty:
            if start_date: df = df[df[date_column] >= start_date]
            if end_date: df = df[df[date_column] <= end_date]

    if placa_filter and placa_filter != "Todos":
        for col in config.FILTER_COLUMN_MAPS["placa"]:
            if col in df.columns:
                df = df[df[col].astype(str).str.strip().str.upper() == placa_filter.strip().upper()]
                break

    if filial_filter and filial_filter != "Todos":
        for col in config.FILTER_COLUMN_MAPS["filial"]:
            if col in df.columns:
                df = df[df[col].astype(str).str.strip().str.upper() == filial_filter.strip().upper()]
                break
    return df

def get_relFilViagensFatCliente_df(start_date=None, end_date=None, placa_filter="Todos", filial_filter="Todos") -> pd.DataFrame:
    df = get_data_as_dataframe("relFilViagensFatCliente")
    if 'permiteFaturar' in df.columns:
        df = df[df['permiteFaturar'].astype(str).str.upper() == 'S']
    return apply_filters_to_df(df, 'dataViagemMotorista', start_date, end_date, placa_filter, filial_filter)

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
                sql = 'INSERT OR IGNORE INTO "static_expense_groups" ("group_name") VALUES (?)'
                cursor.execute(sql, (group_name,))
            else:
                sql = 'INSERT INTO "static_expense_groups" ("group_name") VALUES (%s) ON CONFLICT("group_name") DO NOTHING'
                cursor.execute(sql, (group_name,))
        conn.commit()
    print("Sincronização concluída.")

def get_all_group_flags():
    try:
        df = pd.read_sql('SELECT "group_name", "is_despesa", "is_custo_viagem" FROM "static_expense_groups"', db.get_db_connection())
        return df
    except Exception as e:
        print(f"Erro ao buscar flags de grupo: {e}")
        return pd.DataFrame(columns=['group_name', 'is_despesa', 'is_custo_viagem'])

def get_all_expense_groups():
    df_flags = get_all_group_flags()
    return df_flags['group_name'].dropna().unique().tolist()

def update_all_group_flags(update_data):
    with db.get_db_connection() as conn:
        if conn is None: return
        cursor = conn.cursor()
        try:
            is_sqlite = isinstance(conn, sqlite3.Connection)
            placeholder = "?" if is_sqlite else "%s"
            
            sql_update_flags = f'UPDATE "static_expense_groups" SET "is_despesa" = {placeholder}, "is_custo_viagem" = {placeholder} WHERE "group_name" = {placeholder}'
            for group_name, classification in update_data.items():
                is_despesa = 'S' if classification == 'despesa' else 'N'
                is_custo = 'S' if classification == 'custo_viagem' else 'N'
                cursor.execute(sql_update_flags, (is_despesa, is_custo, group_name))
            conn.commit()

            print("Atualizando a coluna custoTotal em relFilDespesasGerais...")
            df_flags = get_all_group_flags()
            grupos_de_custo = df_flags[df_flags['is_custo_viagem'] == 'S']['group_name'].tolist()
            
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
            print("Flags e custoTotal atualizados com sucesso.")
        except Exception as e:
            print(f"Erro ao atualizar flags de grupo de despesa: {e}")
            conn.rollback()

def get_dashboard_summary(start_date: datetime = None, end_date: datetime = None, placa_filter: str = "Todos", filial_filter: str = "Todos") -> dict:
    summary = {}
    df_viagens_faturamento = get_relFilViagensFatCliente_df(start_date, end_date, placa_filter, filial_filter)
    df_despesas_raw = get_data_as_dataframe("relFilDespesasGerais")
    df_flags = get_all_group_flags()
    
    # --- NOVA LÓGICA DE PRÉ-PROCESSAMENTO APLICADA ---
    df_despesas_processed = pd.DataFrame()
    if not df_despesas_raw.empty and 'despesa' in df_despesas_raw.columns:
        # 1. Filtra apenas as linhas onde a coluna 'despesa' é 'S'
        df_despesas_s = df_despesas_raw[df_despesas_raw['despesa'].fillna('').str.strip().str.upper() == 'S']
        # 2. Remove duplicatas com base na nova regra
        df_despesas_processed = df_despesas_s.drop_duplicates(subset=['dataControle', 'numNota', 'valorVenc'])
    
    if df_despesas_processed.empty:
        df_despesas_com_flags = pd.DataFrame(columns=['descGrupoD', 'group_name', 'is_custo_viagem', 'is_despesa'])
    else:
        df_despesas_com_flags = pd.merge(df_despesas_processed, df_flags, left_on='descGrupoD', right_on='group_name', how='left')
    
    df_despesas_com_flags['is_custo_viagem'] = df_despesas_com_flags['is_custo_viagem'].fillna('N')
    df_despesas_com_flags['is_despesa'] = df_despesas_com_flags['is_despesa'].fillna('S')

    df_custos_viagem = df_despesas_com_flags[df_despesas_com_flags['is_custo_viagem'] == 'S']
    df_despesas_gerais = df_despesas_com_flags[df_despesas_com_flags['is_despesa'] == 'S']

    df_custos = apply_filters_to_df(df_custos_viagem, 'dataControle', start_date, end_date, placa_filter, filial_filter)
    df_despesas = apply_filters_to_df(df_despesas_gerais, 'dataControle', start_date, end_date, placa_filter, filial_filter)

    summary['faturamento_total_viagens'] = df_viagens_faturamento['freteEmpresa'].sum() if 'freteEmpresa' in df_viagens_faturamento.columns else 0
    summary['custo_total_viagem'] = df_custos['custoTotal'].sum() if not df_custos.empty and 'custoTotal' in df_custos.columns else 0
    summary['total_despesas_gerais'] = df_despesas['valorNota'].sum() if not df_despesas.empty and 'valorNota' in df_despesas.columns else 0
    
    df_viagens_cliente = get_data_as_dataframe("relFilViagensCliente")
    total_comissao_motorista = 0
    if not df_viagens_cliente.empty and 'tipoFrete' in df_viagens_cliente.columns and 'freteMotorista' in df_viagens_cliente.columns:
        df_viagens_cliente_filtrado = apply_filters_to_df(df_viagens_cliente, 'dataViagemMotorista', start_date, end_date, placa_filter, filial_filter)
        df_comissao_base = df_viagens_cliente_filtrado[
            (df_viagens_cliente_filtrado['tipoFrete'].astype(str).str.strip().str.upper() == 'P') &
            (pd.to_numeric(df_viagens_cliente_filtrado['freteMotorista'], errors='coerce') > 0)
        ].copy()
        if not df_comissao_base.empty:
            frete_motorista = pd.to_numeric(df_comissao_base['freteMotorista'], errors='coerce').fillna(0)
            percentual_comissao = pd.to_numeric(df_comissao_base.get('comissao', 0), errors='coerce').fillna(0)
            df_comissao_base['valor_comissao'] = frete_motorista * (percentual_comissao / 100)
            total_comissao_motorista = df_comissao_base['valor_comissao'].sum()

    valor_quebra_sum = df_viagens_faturamento['valorQuebra'].sum() if 'valorQuebra' in df_viagens_faturamento.columns else 0
    
    flags_dict = df_flags.set_index('group_name').to_dict('index') if not df_flags.empty else {}

    if flags_dict.get('VALOR QUEBRA', {}).get('is_custo_viagem') == 'S':
        summary['custo_total_viagem'] += valor_quebra_sum
    elif flags_dict.get('VALOR QUEBRA', {}).get('is_despesa') == 'S':
        summary['total_despesas_gerais'] += valor_quebra_sum

    comissao_flags = flags_dict.get('COMISSÃO DE MOTORISTA', {})
    if comissao_flags.get('is_custo_viagem') == 'S':
        summary['custo_total_viagem'] += total_comissao_motorista
    elif comissao_flags.get('is_despesa') == 'S':
        summary['total_despesas_gerais'] += total_comissao_motorista

    df_contas_pagar_all = get_data_as_dataframe("relFilContasPagarDet")
    if not df_contas_pagar_all.empty and 'codTransacao' in df_contas_pagar_all.columns:
        pendentes_pagar_raw = df_contas_pagar_all[df_contas_pagar_all['codTransacao'].fillna('').str.strip() == '']
        pendentes_pagar = pendentes_pagar_raw.drop_duplicates(subset=['dataVenc', 'numNota', 'nomeForn'])
        summary['saldo_contas_a_pagar_pendentes'] = pendentes_pagar['valorVenc'].sum() if not pendentes_pagar.empty and 'valorVenc' in pendentes_pagar.columns else 0
    else:
        summary['saldo_contas_a_pagar_pendentes'] = 0

    df_contas_receber_all = get_data_as_dataframe("relFilContasReceber")
    if not df_contas_receber_all.empty and 'codTransacao' in df_contas_receber_all.columns:
        pendentes_receber = df_contas_receber_all[df_contas_receber_all['codTransacao'].fillna('').str.strip() == '']
        summary['saldo_contas_a_receber_pendentes'] = pendentes_receber['valorVenc'].sum() if not pendentes_receber.empty and 'valorVenc' in pendentes_receber.columns else 0
    else:
        summary['saldo_contas_a_receber_pendentes'] = 0

    custo_operacional_total = summary['custo_total_viagem'] + summary['total_despesas_gerais']
    summary['saldo_geral'] = summary['faturamento_total_viagens'] - custo_operacional_total
    summary['margem_frete'] = (summary['saldo_geral'] / summary['faturamento_total_viagens']) * 100 if summary['faturamento_total_viagens'] > 0 else 0
    
    return summary

def get_monthly_summary(start_date, end_date, placa_filter, filial_filter) -> pd.DataFrame:
    df_viagens = get_relFilViagensFatCliente_df(start_date, end_date, placa_filter, filial_filter)
    df_despesas_raw = get_data_as_dataframe("relFilDespesasGerais")
    df_flags = get_all_group_flags()
    
    faturamento = pd.Series(dtype=float)
    if not df_viagens.empty and 'dataViagemMotorista' in df_viagens.columns:
        df_viagens_dated = df_viagens.copy()
        df_viagens_dated['AnoMes'] = pd.to_datetime(df_viagens_dated['dataViagemMotorista'], errors='coerce').dt.to_period('M')
        faturamento = df_viagens_dated.groupby('AnoMes')['freteEmpresa'].sum()

    despesas = pd.Series(dtype=float)
    if not df_despesas_raw.empty:
        # APLICA A NOVA REGRA DE PRÉ-FILTRO E DUPLICATAS TAMBÉM NO GRÁFICO
        df_despesas_processed = pd.DataFrame()
        if 'despesa' in df_despesas_raw.columns:
            df_despesas_s = df_despesas_raw[df_despesas_raw['despesa'].fillna('').str.strip().str.upper() == 'S']
            df_despesas_processed = df_despesas_s.drop_duplicates(subset=['dataControle', 'numNota', 'valorVenc'])

        df_despesas_com_flags = pd.merge(df_despesas_processed, df_flags, left_on='descGrupoD', right_on='group_name', how='left')
        df_despesas_com_flags['is_despesa'] = df_despesas_com_flags['is_despesa'].fillna('S')
        df_despesas_gerais = df_despesas_com_flags[df_despesas_com_flags['is_despesa'] == 'S']
        df_despesas_filtrado = apply_filters_to_df(df_despesas_gerais, 'dataControle', start_date, end_date, placa_filter, filial_filter)
        if not df_despesas_filtrado.empty:
            df_despesas_filtrado_dated = df_despesas_filtrado.copy()
            df_despesas_filtrado_dated['AnoMes'] = pd.to_datetime(df_despesas_filtrado_dated['dataControle'], errors='coerce').dt.to_period('M')
            despesas = df_despesas_filtrado_dated.groupby('AnoMes')['valorNota'].sum()

    monthly_df = pd.DataFrame({'Faturamento': faturamento, 'Despesas': despesas}).fillna(0)
    
    if isinstance(monthly_df.index, pd.PeriodIndex):
        monthly_df['AnoMes'] = monthly_df.index.strftime('%Y-%m')
    else:
        monthly_df['AnoMes'] = None
        
    return monthly_df.reset_index(drop=True)

def get_unique_plates() -> list[str]:
    df_viagens = get_data_as_dataframe("relFilViagensFatCliente")
    df_despesas = get_data_as_dataframe("relFilDespesasGerais")
    plates = pd.concat([
        df_viagens['placaVeiculo'].dropna().astype(str).str.upper() if 'placaVeiculo' in df_viagens.columns else pd.Series(dtype=str),
        df_despesas['placaVeiculo'].dropna().astype(str).str.upper() if 'placaVeiculo' in df_despesas.columns else pd.Series(dtype=str)
    ])
    return ["Todos"] + sorted(plates.unique().tolist())

def get_unique_filiais() -> list[str]:
    table_names = ["relFilViagensFatCliente", "relFilDespesasGerais", "relFilContasPagarDet", "relFilContasReceber"]
    all_dfs = [get_data_as_dataframe(name) for name in table_names]
    filiais = pd.Series(dtype=str)
    for df in all_dfs:
        for col in ['nomeFilial', 'nomeFil']:
            if col in df.columns:
                filiais = pd.concat([filiais, df[col].dropna().astype(str).str.upper()])
    return ["Todos"] + sorted(filiais.unique().tolist())