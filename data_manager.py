# data_manager.py
import pandas as pd
from datetime import datetime
import database as db 
import config
import sqlite3

def get_data_as_dataframe(table_name: str) -> pd.DataFrame:
    """
    Busca dados de uma tabela do banco de forma segura.
    Sempre retorna um DataFrame, mesmo em caso de erro.
    """
    try:
        with db.get_db_connection() as conn:
            if conn is None:
                print(f"AVISO: Não foi possível conectar ao banco para buscar a tabela '{table_name}'. Retornando DataFrame vazio.")
                return pd.DataFrame()
            
            # Verifica se a tabela existe (funciona para SQLite e PostgreSQL)
            query_check_table = ""
            is_sqlite = isinstance(conn, sqlite3.Connection)
            if is_sqlite:
                query_check_table = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
            else:
                query_check_table = "SELECT to_regclass(%s)"

            cursor = conn.cursor()
            cursor.execute(query_check_table, (table_name,))
            if cursor.fetchone()[0] is None:
                print(f"AVISO: Tabela '{table_name}' não existe no banco de dados. Retornando DataFrame vazio.")
                return pd.DataFrame()

            df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
            return df
            
    except Exception as e:
        print(f"ERRO CRÍTICO ao carregar dados da tabela '{table_name}': {e}")
        print("Retornando um DataFrame vazio para evitar que o programa pare.")
        return pd.DataFrame()

def apply_filters_to_df(df: pd.DataFrame, date_column: str, start_date: datetime, end_date: datetime, placa_filter: str, filial_filter: str) -> pd.DataFrame:
    """
    Aplica os filtros de data, placa e filial a um DataFrame de forma segura e com debug.
    """
    print(f"\n--- Debug: Aplicando Filtros na Coluna '{date_column}' ---")
    if df.empty:
        print(" -> DataFrame vazio. Nenhum filtro aplicado.")
        return df
    
    df = df.copy()
    
    if date_column in df.columns and (start_date or end_date):
        print(" -> Filtro de data ATIVO. Convertendo e limpando datas...")
        linhas_antes = len(df)
        df[date_column] = pd.to_datetime(df[date_column], errors='coerce')
        df = df.dropna(subset=[date_column])
        
        if not df.empty:
            if start_date:
                df = df[df[date_column] >= start_date]
            if end_date:
                df = df[df[date_column] <= end_date]
        
        print(f" -> Número de linhas DEPOIS do filtro de data: {len(df)}")
    else:
        print(" -> Filtro de data INATIVO.")

    if placa_filter and placa_filter != "Todos":
        for col in config.FILTER_COLUMN_MAPS["placa"]:
            if col in df.columns:
                df = df[df[col].astype(str).strip().str.upper() == placa_filter.strip().upper()]
                break

    if filial_filter and filial_filter != "Todos":
        for col in config.FILTER_COLUMN_MAPS["filial"]:
            if col in df.columns:
                df = df[df[col].astype(str).strip().str.upper() == filial_filter.strip().upper()]
                break
                
    return df

def get_dashboard_summary(start_date: datetime = None, end_date: datetime = None, placa_filter: str = "Todos", filial_filter: str = "Todos") -> dict:
    summary = {}
    df_viagens_faturamento = get_relFilViagensFatCliente_df(start_date, end_date, placa_filter, filial_filter)
    df_despesas_raw = get_data_as_dataframe("relFilDespesasGerais")
    df_viagens_cliente = get_data_as_dataframe("relFilViagensCliente")

    total_comissao_motorista = 0
    if not df_viagens_cliente.empty:
        df_viagens_cliente_filtrado = apply_filters_to_df(df_viagens_cliente, 'dataViagemMotorista', start_date, end_date, placa_filter, filial_filter)
        df_comissao_base = df_viagens_cliente_filtrado[
            (df_viagens_cliente_filtrado['tipoFrete'].astype(str).str.strip().str.upper() == 'P') &
            (pd.to_numeric(df_viagens_cliente_filtrado['freteMotorista'], errors='coerce').notna()) &
            (pd.to_numeric(df_viagens_cliente_filtrado['freteMotorista'], errors='coerce') > 0)
        ].copy()
        if not df_comissao_base.empty:
            frete_motorista = pd.to_numeric(df_comissao_base['freteMotorista'], errors='coerce').fillna(0)
            percentual_comissao = pd.to_numeric(df_comissao_base.get('comissao', 0), errors='coerce').fillna(0)
            df_comissao_base['valor_comissao'] = frete_motorista * (percentual_comissao / 100)
            total_comissao_motorista = df_comissao_base['valor_comissao'].sum()

    summary['faturamento_total_viagens'] = df_viagens_faturamento['freteEmpresa'].sum() if 'freteEmpresa' in df_viagens_faturamento.columns else 0
    
    df_despesas_gerais_filtrado = df_despesas_raw[df_despesas_raw['despesa'].fillna('').str.upper() == 'S'] if 'despesa' in df_despesas_raw.columns else pd.DataFrame()
    df_custos_viagem_filtrado = df_despesas_raw[df_despesas_raw['e_custo_viagem'].fillna('').str.upper() == 'S'] if 'e_custo_viagem' in df_despesas_raw.columns else pd.DataFrame()
    
    df_despesas = apply_filters_to_df(df_despesas_gerais_filtrado, 'dataControle', start_date, end_date, placa_filter, filial_filter)
    df_custos = apply_filters_to_df(df_custos_viagem_filtrado, 'dataControle', start_date, end_date, placa_filter, filial_filter)
    
    custos_viagem_de_despesas = df_custos['custoTotal'].sum() if not df_custos.empty else 0
    despesas_gerais = df_despesas['valorNota'].sum() if not df_despesas.empty else 0

    valor_quebra_sum = df_viagens_faturamento['valorQuebra'].sum() if 'valorQuebra' in df_viagens_faturamento.columns else 0
    
    summary['custo_total_viagem'] = custos_viagem_de_despesas
    summary['total_despesas_gerais'] = despesas_gerais
    
    all_flags = get_all_group_flags()
    
    if all_flags.get('VALOR QUEBRA', {}).get('custo_viagem') == 'S':
        summary['custo_total_viagem'] += valor_quebra_sum
    elif all_flags.get('VALOR QUEBRA', {}).get('despesa') == 'S':
        summary['total_despesas_gerais'] += valor_quebra_sum

    comissao_flags = all_flags.get('COMISSÃO DE MOTORISTA', {})
    if comissao_flags.get('custo_viagem') == 'S':
        summary['custo_total_viagem'] += total_comissao_motorista
    elif comissao_flags.get('despesa') == 'S':
        summary['total_despesas_gerais'] += total_comissao_motorista
    
    df_contas_pagar_all = get_data_as_dataframe("relFilContasPagarDet")
    pendentes_pagar = df_contas_pagar_all[df_contas_pagar_all['codTransacao'].fillna('').str.strip() == ''] if not df_contas_pagar_all.empty else pd.DataFrame()
    summary['saldo_contas_a_pagar_pendentes'] = pendentes_pagar['valorVenc'].sum() if not pendentes_pagar.empty else 0

    df_contas_receber_all = get_data_as_dataframe("relFilContasReceber")
    pendentes_receber = df_contas_receber_all[df_contas_receber_all['codTransacao'].fillna('').str.strip() == ''] if not df_contas_receber_all.empty else pd.DataFrame()
    summary['saldo_contas_a_receber_pendentes'] = pendentes_receber['valorVenc'].sum() if not pendentes_receber.empty else 0

    custo_operacional_total = summary['custo_total_viagem'] + summary['total_despesas_gerais']
    summary['saldo_geral'] = summary['faturamento_total_viagens'] - custo_operacional_total
    summary['margem_frete'] = (summary['saldo_geral'] / summary['faturamento_total_viagens']) * 100 if summary['faturamento_total_viagens'] > 0 else 0
    
    return summary

def get_monthly_summary(start_date, end_date, placa_filter, filial_filter) -> pd.DataFrame:
    df_viagens = get_relFilViagensFatCliente_df(start_date, end_date, placa_filter, filial_filter)
    df_despesas_raw = get_data_as_dataframe("relFilDespesasGerais")

    faturamento = pd.Series(dtype=float)
    if not df_viagens.empty and 'dataViagemMotorista' in df_viagens.columns:
        df_viagens_dated = df_viagens.copy()
        df_viagens_dated['AnoMes'] = pd.to_datetime(df_viagens_dated['dataViagemMotorista'], errors='coerce').dt.to_period('M')
        faturamento = df_viagens_dated.groupby('AnoMes')['freteEmpresa'].sum()

    despesas = pd.Series(dtype=float)
    if not df_despesas_raw.empty and 'dataControle' in df_despesas_raw.columns:
        df_despesas_gerais = df_despesas_raw[df_despesas_raw['despesa'].fillna('').str.upper() == 'S']
        df_despesas_filtrado = apply_filters_to_df(df_despesas_gerais, 'dataControle', start_date, end_date, placa_filter, filial_filter)
        if not df_despesas_filtrado.empty:
            df_despesas_filtrado_dated = df_despesas_filtrado.copy()
            df_despesas_filtrado_dated['AnoMes'] = pd.to_datetime(df_despesas_filtrado_dated['dataControle'], errors='coerce').dt.to_period('M')
            despesas = df_despesas_filtrado_dated.groupby('AnoMes')['valorNota'].sum()

    monthly_df = pd.DataFrame({'Faturamento': faturamento, 'Despesas': despesas}).fillna(0)
    monthly_df['AnoMes'] = monthly_df.index.strftime('%Y-%m')
    return monthly_df.reset_index(drop=True)

def get_relFilViagensFatCliente_df(start_date=None, end_date=None, placa_filter="Todos", filial_filter="Todos") -> pd.DataFrame:
    df = get_data_as_dataframe("relFilViagensFatCliente")
    if 'permiteFaturar' in df.columns:
        df = df[df['permiteFaturar'].astype(str).str.upper() == 'S']
    return apply_filters_to_df(df, 'dataViagemMotorista', start_date, end_date, placa_filter, filial_filter)

def get_unique_plates() -> list[str]:
    df_viagens = get_data_as_dataframe("relFilViagensFatCliente")
    df_despesas = get_data_as_dataframe("relFilDespesasGerais")
    plates = pd.concat([
        df_viagens['placaVeiculo'].dropna().astype(str).str.upper() if 'placaVeiculo' in df_viagens.columns else pd.Series(dtype=str),
        df_despesas['placaVeiculo'].dropna().astype(str).str.upper() if 'placaVeiculo' in df_despesas.columns else pd.Series(dtype=str)
    ])
    return ["Todos"] + sorted(plates.unique().tolist())

def get_unique_filiais() -> list[str]:
    all_dfs = [get_data_as_dataframe(table) for table in ["relFilViagensFatCliente", "relFilDespesasGerais", "relFilContasPagarDet", "relFilContasReceber"]]
    filiais = pd.Series(dtype=str)
    for df in all_dfs:
        for col in ['nomeFilial', 'nomeFil']:
            if col in df.columns:
                filiais = pd.concat([filiais, df[col].dropna().astype(str).str.upper()])
    return ["Todos"] + sorted(filiais.unique().tolist())

def get_all_expense_groups():
    """Busca grupos dinâmicos da tabela de despesas e estáticos da tabela de grupos."""
    df = get_data_as_dataframe("relFilDespesasGerais")
    grupos_dinamicos = []
    if not df.empty and 'descGrupoD' in df.columns:
        grupos_dinamicos = df['descGrupoD'].dropna().unique().tolist()
    
    static_groups = []
    with db.get_db_connection() as conn:
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT group_name FROM static_expense_groups")
                static_groups = [row[0] for row in cursor.fetchall()]
            except Exception as e:
                print(f"Erro ao buscar grupos estáticos: {e}")

    all_groups = sorted(list(set(grupos_dinamicos + static_groups)))
    return all_groups

def get_all_group_flags():
    """Busca o status das flags para grupos dinâmicos e estáticos."""
    flags_map = {}
    df_despesas = get_data_as_dataframe("relFilDespesasGerais")
    if not df_despesas.empty and 'descGrupoD' in df_despesas.columns:
        if 'despesa' not in df_despesas.columns: df_despesas['despesa'] = 'S'
        if 'e_custo_viagem' not in df_despesas.columns: df_despesas['e_custo_viagem'] = 'N'
        df_despesas['despesa'] = df_despesas['despesa'].fillna('S')
        df_despesas['e_custo_viagem'] = df_despesas['e_custo_viagem'].fillna('N')
        grouped = df_despesas.groupby('descGrupoD').first()
        for grupo, row in grouped.iterrows():
            flags_map[grupo] = {
                'despesa': str(row.get('despesa', 'S')).upper(),
                'custo_viagem': str(row.get('e_custo_viagem', 'N')).upper()
            }

    with db.get_db_connection() as conn:
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT group_name, is_despesa, is_custo_viagem FROM static_expense_groups")
                for row in cursor.fetchall():
                    flags_map[row[0]] = {
                        'despesa': str(row[1]).upper(),
                        'custo_viagem': str(row[2]).upper()
                    }
            except Exception as e:
                print(f"Erro ao buscar flags de grupos estáticos: {e}")
    return flags_map

# Em data_manager.py, substitua a função update_all_group_flags inteira
def update_all_group_flags(update_data):
    """Atualiza as flags para grupos dinâmicos e estáticos de forma inteligente."""
    with db.get_db_connection() as conn:
        if conn is None: return
        cursor = conn.cursor()
        try:
            is_sqlite = isinstance(conn, sqlite3.Connection)
            placeholder = "?" if is_sqlite else "%s"

            cursor.execute("SELECT group_name FROM static_expense_groups")
            static_groups = [row[0] for row in cursor.fetchall()]

            for group_name, classification in update_data.items():
                is_despesa = 'S' if classification == 'despesa' else 'N'
                is_custo = 'S' if classification == 'custo_viagem' else 'N'

                if group_name in static_groups:
                    print(f"Atualizando grupo ESTÁTICO '{group_name}': Despesa={is_despesa}, Custo={is_custo}")
                    sql = f"UPDATE static_expense_groups SET is_despesa = {placeholder}, is_custo_viagem = {placeholder} WHERE group_name = {placeholder}"
                    cursor.execute(sql, (is_despesa, is_custo, group_name))
                else:
                    # Lógica CORRIGIDA para grupos dinâmicos
                    print(f"Atualizando grupo DINÂMICO '{group_name}': Despesa={is_despesa}, Custo={is_custo}")
                    sql_flags = f"UPDATE relFilDespesasGerais SET despesa = {placeholder}, e_custo_viagem = {placeholder} WHERE descGrupoD = {placeholder}"
                    cursor.execute(sql_flags, (is_despesa, is_custo, group_name))
                    
                    # Atualiza o custoTotal baseado na nova classificação
                    if is_custo == 'S':
                        sql_custo = f"UPDATE relFilDespesasGerais SET custoTotal = valorNota WHERE descGrupoD = {placeholder}"
                        cursor.execute(sql_custo, (group_name,))
                    else:
                        sql_custo = f"UPDATE relFilDespesasGerais SET custoTotal = 0 WHERE descGrupoD = {placeholder}"
                        cursor.execute(sql_custo, (group_name,))
            
            conn.commit()
            print("Flags de grupo de despesa atualizadas com sucesso.")
        except Exception as e:
            print(f"Erro ao atualizar flags de grupo de despesa: {e}")
            conn.rollback()