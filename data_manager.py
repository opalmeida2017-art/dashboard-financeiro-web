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
            
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            if cursor.fetchone() is None:
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
        
        linhas_com_datas_validas = df[date_column].notna().sum()
        linhas_invalidas_removidas = linhas_antes - linhas_com_datas_validas
        
        if linhas_invalidas_removidas > 0:
            print(f" -> ALERTA: Removidas {linhas_invalidas_removidas} linhas com datas inválidas ou vazias na coluna '{date_column}'.")

        df = df.dropna(subset=[date_column])
        
        if not df.empty:
            print(f" -> Intervalo de Datas no DataFrame: de {df[date_column].min().strftime('%d/%m/%Y')} a {df[date_column].max().strftime('%d/%m/%Y')}")
            
            if start_date:
                print(f" -> Aplicando filtro de data INICIAL: >= {start_date.strftime('%d/%m/%Y')}")
                df = df[df[date_column] >= start_date]
            
            if end_date:
                print(f" -> Aplicando filtro de data FINAL: <= {end_date.strftime('%d/%m/%Y')}")
                df = df[df[date_column] <= end_date]
        
        print(f" -> Número de linhas DEPOIS do filtro de data: {len(df)}")
    else:
        print(" -> Filtro de data INATIVO. Nenhuma linha será removida por data.")

    if placa_filter and placa_filter != "Todos":
        for col in config.FILTER_COLUMN_MAPS["placa"]:
            if col in df.columns:
                linhas_antes_placa = len(df)
                df = df[df[col].astype(str).str.strip().str.upper() == placa_filter.strip().upper()]
                print(f" -> Filtro de Placa '{placa_filter}': {linhas_antes_placa} -> {len(df)} linhas")
                break

    if filial_filter and filial_filter != "Todos":
        for col in config.FILTER_COLUMN_MAPS["filial"]:
            if col in df.columns:
                linhas_antes_filial = len(df)
                df = df[df[col].astype(str).str.strip().str.upper() == filial_filter.strip().upper()]
                print(f" -> Filtro de Filial '{filial_filter}' na coluna '{col}': {linhas_antes_filial} -> {len(df)} linhas")
                break
                
    print("--- Fim do Debug de Filtros ---")
    return df

def get_dashboard_summary(start_date: datetime = None, end_date: datetime = None, placa_filter: str = "Todos", filial_filter: str = "Todos") -> dict:
    # A função inteira é a mesma, a única alteração está na seção de Contas a Receber
    
    # ... (todo o início da função, incluindo o cálculo da comissão, permanece igual) ...

    # ETAPA 1: INICIALIZAÇÃO E CARGA DE DADOS
    print("\n" + "="*50)
    print("INICIANDO DEBUG DETALHADO DO CÁLCULO DO DASHBOARD")
    print("="*50)
    print(f"[ETAPA 1.1] Filtros recebidos: \n  - Data Início: {start_date} \n  - Data Fim: {end_date} \n  - Placa: {placa_filter} \n  - Filial: {filial_filter}")
    
    summary = {}
    df_viagens_faturamento = get_relFilViagensFatCliente_df(start_date, end_date, placa_filter, filial_filter)
    df_despesas_raw = get_data_as_dataframe("relFilDespesasGerais")
    df_viagens_cliente = get_data_as_dataframe("relFilViagensCliente")

    print(f"[ETAPA 1.2] Dados carregados:\n  - Viagens para Faturamento: {len(df_viagens_faturamento)} linhas (já filtrado)\n  - Todas as Despesas: {len(df_despesas_raw)} linhas\n  - Todas as Viagens (para comissão): {len(df_viagens_cliente)} linhas")
    print("-"*50)

    # ETAPA 2: CÁLCULO DA COMISSÃO
    print("[ETAPA 2] Iniciando cálculo da COMISSÃO DE MOTORISTA...")
    total_comissao_motorista = 0
    if not df_viagens_cliente.empty and all(col in df_viagens_cliente.columns for col in ['tipoFrete', 'freteMotorista', 'comissao', 'dataViagemMotorista']):
        
        df_viagens_cliente_filtrado = apply_filters_to_df(df_viagens_cliente, 'dataViagemMotorista', start_date, end_date, placa_filter, filial_filter)
        print(f"[ETAPA 2.1] Linhas restantes após aplicação dos filtros do dashboard: {len(df_viagens_cliente_filtrado)}")
        
        df_comissao_base = df_viagens_cliente_filtrado[
            (df_viagens_cliente_filtrado['tipoFrete'].astype(str).str.strip().str.upper() == 'P') &
            (pd.to_numeric(df_viagens_cliente_filtrado['freteMotorista'], errors='coerce').notna()) &
            (pd.to_numeric(df_viagens_cliente_filtrado['freteMotorista'], errors='coerce') > 0)
        ].copy()
        print(f"[ETAPA 2.2] Linhas restantes após filtro 'tipoFrete == P': {len(df_comissao_base)}")

        if not df_comissao_base.empty:
            frete_motorista = pd.to_numeric(df_comissao_base['freteMotorista'], errors='coerce').fillna(0)
            percentual_comissao = pd.to_numeric(df_comissao_base['comissao'], errors='coerce').fillna(0)
            df_comissao_base['valor_comissao'] = frete_motorista * (percentual_comissao / 100)
            total_comissao_motorista = df_comissao_base['valor_comissao'].sum()
            print(f"[ETAPA 2.3] AMOSTRA DOS DADOS USADOS PARA CÁLCULO DA COMISSÃO (5 primeiras linhas):")
            print(df_comissao_base[['dataViagemMotorista', 'freteMotorista', 'comissao', 'valor_comissao']].head().to_string())

    print(f"\n[ETAPA 2.4] >> VALOR TOTAL DA COMISSÃO CALCULADO: {total_comissao_motorista:.2f} <<")
    print("-"*50)
    
    # ETAPA 3: CÁLCULO DOS KPIs PRINCIPAIS (CUSTOS E DESPESAS)
    print("[ETAPA 3] Calculando KPIs principais (Faturamento, Custos, Despesas)...")
    summary['faturamento_total_viagens'] = df_viagens_faturamento['freteEmpresa'].sum() if 'freteEmpresa' in df_viagens_faturamento.columns else 0
    print(f"[ETAPA 3.1] Faturamento Total (filtrado): {summary['faturamento_total_viagens']:.2f}")

    df_despesas_gerais_filtrado = df_despesas_raw[df_despesas_raw['despesa'].fillna('').str.upper() == 'S'] if 'despesa' in df_despesas_raw.columns else df_despesas_raw
    df_custos_viagem_filtrado = df_despesas_raw[df_despesas_raw['e_custo_viagem'].fillna('').str.upper() == 'S'] if 'e_custo_viagem' in df_despesas_raw.columns else pd.DataFrame()
    df_despesas = apply_filters_to_df(df_despesas_gerais_filtrado, 'dataControle', start_date, end_date, placa_filter, filial_filter)
    df_custos_despesas = apply_filters_to_df(df_custos_viagem_filtrado, 'dataControle', start_date, end_date, placa_filter, filial_filter)
    
    custos_viagem_de_despesas = df_custos_despesas.drop_duplicates(subset=['codNota', 'dataControle'])['custoTotal'].sum() if not df_custos_despesas.empty else 0
    despesas_gerais = df_despesas.drop_duplicates(subset=['codNota', 'dataControle'])['valorNota'].sum() if not df_despesas.empty else 0
    print(f"[ETAPA 3.2] Custos de Viagem (baseado em Despesas Gerais): {custos_viagem_de_despesas:.2f}")
    print(f"[ETAPA 3.3] Despesas Gerais (baseado em Despesas Gerais): {despesas_gerais:.2f}")
    
    all_flags = get_all_group_flags()
    valor_quebra_sum = 0
    if 'descQuebraSaldoEmp' in df_viagens_faturamento.columns:
        df_quebra = df_viagens_faturamento[df_viagens_faturamento['descQuebraSaldoEmp'].astype(str).str.strip().str.upper() == 'S']
        if 'valorQuebra' in df_quebra.columns:
            valor_quebra_sum = df_quebra['valorQuebra'].sum()
    print(f"[ETAPA 3.4] Valor de Quebra (filtrado): {valor_quebra_sum:.2f}")
    
    summary['custo_total_viagem'] = custos_viagem_de_despesas
    summary['total_despesas_gerais'] = despesas_gerais
    
    print(f"\n[ETAPA 3.5] KPIs ANTES de somar Quebra e Comissão:\n  - Custo Viagem: {summary['custo_total_viagem']:.2f}\n  - Despesas Gerais: {summary['total_despesas_gerais']:.2f}")

    # --- CORREÇÃO APLICADA AQUI ---
    # A chave foi alterada de 'VALORQUEBRA' para 'VALOR QUEBRA' para corresponder à configuração do grupo.
    if all_flags.get('VALOR QUEBRA', {}).get('custo_viagem') == 'S':
        summary['custo_total_viagem'] += valor_quebra_sum
        print("  -> 'VALOR QUEBRA' somado a CUSTO DE VIAGEM")
    if all_flags.get('VALOR QUEBRA', {}).get('despesa') == 'S':
        summary['total_despesas_gerais'] += valor_quebra_sum
        print("  -> 'VALOR QUEBRA' somado a DESPESA GERAL")
    # --- FIM DA CORREÇÃO ---

    comissao_flags = all_flags.get('COMISSÃO DE MOTORISTA', {})
    if comissao_flags.get('custo_viagem') == 'S':
        summary['custo_total_viagem'] += total_comissao_motorista
        print("  -> 'COMISSÃO DE MOTORISTA' somada a CUSTO DE VIAGEM")
    elif comissao_flags.get('despesa') == 'S':
        summary['total_despesas_gerais'] += total_comissao_motorista
        print("  -> 'COMISSÃO DE MOTORISTA' somada a DESPESA GERAL")
    
    
    print(f"\n[ETAPA 3.6] >> KPIs FINAIS (Custo e Despesa) <<\n  - Custo Total de Viagem: {summary['custo_total_viagem']:.2f}\n  - Total Despesas Gerais: {summary['total_despesas_gerais']:.2f}")
    print("-"*50)

     # LÓGICA DE CONTAS A PAGAR (com alterações)
    df_contas_pagar_all = get_data_as_dataframe("relFilContasPagarDet")
    summary['saldo_contas_a_pagar_pendentes'] = 0
    if not df_contas_pagar_all.empty and all(col in df_contas_pagar_all.columns for col in ['numNota', 'dataControle', 'codTransacao', 'valorVenc']):
        # --- CORREÇÃO APLICADA AQUI ---
        # Adicionada a coluna 'parcela' para garantir que cada parcela seja única.
        subset_cols_pagar = ['numNota', 'dataControle']
        if 'parcela' in df_contas_pagar_all.columns:
            subset_cols_pagar.append('parcela')
        df_pagar_unique = df_contas_pagar_all.drop_duplicates(subset=subset_cols_pagar)
        # --- FIM DA CORREÇÃO ---
        pendentes_pagar = df_pagar_unique[df_pagar_unique['codTransacao'].fillna('').str.strip() == '']
        summary['saldo_contas_a_pagar_pendentes'] = pendentes_pagar['valorVenc'].sum()
    # --- LÓGICA DE CONTAS A RECEBER CORRIGIDA ---
    # --- LÓGICA DE CONTAS A RECEBER CORRIGIDA ---
    df_contas_receber_all = get_data_as_dataframe("relFilContasReceber")
    summary['saldo_contas_a_receber_pendentes'] = 0
    if not df_contas_receber_all.empty and all(col in df_contas_receber_all.columns for col in ['numConhec', 'dataEmissao', 'codTransacao', 'valorVenc']):
        # --- CORREÇÃO APLICADA AQUI ---
        # Adicionada a coluna 'parcela' para garantir que cada parcela seja única.
        subset_cols_receber = ['numConhec', 'dataEmissao']
        if 'parcela' in df_contas_receber_all.columns:
            subset_cols_receber.append('parcela')
        df_receber_unique = df_contas_receber_all.drop_duplicates(subset=subset_cols_receber)
        # --- FIM DA CORREÇÃO ---
        
        pendentes_receber = df_receber_unique[df_receber_unique['codTransacao'].fillna('').str.strip() == '']
        summary['saldo_contas_a_receber_pendentes'] = pendentes_receber['valorVenc'].sum()

    # ETAPA 4: CÁLCULO FINAL DO SALDO (sem alterações)
    print("[ETAPA 4] Calculando Saldo e Indicadores Finais...")
    custo_operacional_total = summary['custo_total_viagem'] + summary['total_despesas_gerais']
    summary['saldo_geral'] = summary['faturamento_total_viagens'] - custo_operacional_total
    summary['margem_frete'] = (summary['saldo_geral'] / summary['faturamento_total_viagens']) * 100 if summary['faturamento_total_viagens'] > 0 else 0
    print(f"[ETAPA 4.1] Custo Operacional Total: {custo_operacional_total:.2f}")
    print(f"[ETAPA 4.2] >> Saldo Geral: {summary['saldo_geral']:.2f} <<")
    print(f"[ETAPA 4.3] >> Margem sobre Frete: {summary['margem_frete']:.2f}% <<")
    print("="*50)
    print("FIM DO DEBUG DETALHADO")
    print("="*50 + "\n")

    if not df_viagens_faturamento.empty:
        km_total = df_viagens_faturamento['kmRodado'].sum() if 'kmRodado' in df_viagens_faturamento.columns else 0
        numero_de_viagens = len(df_viagens_faturamento)
        summary['custo_medio_por_viagem'] = summary['custo_total_viagem'] / numero_de_viagens if numero_de_viagens > 0 else 0
        summary['custo_por_km'] = summary['custo_total_viagem'] / km_total if km_total > 0 else 0
    else:
        summary['custo_medio_por_viagem'] = 0
        summary['custo_por_km'] = 0
    
    return summary
def get_monthly_summary(start_date, end_date, placa_filter, filial_filter) -> pd.DataFrame:
    df_viagens = get_relFilViagensFatCliente_df(start_date, end_date, placa_filter, filial_filter)
    df_despesas_raw = get_data_as_dataframe("relFilDespesasGerais")

    faturamento = pd.Series(dtype=float)
    if not df_viagens.empty and 'dataViagemMotorista' in df_viagens.columns:
        df_viagens['AnoMes'] = pd.to_datetime(df_viagens['dataViagemMotorista']).dt.to_period('M')
        faturamento = df_viagens.groupby('AnoMes')['freteEmpresa'].sum()

    despesas = pd.Series(dtype=float)
    if not df_despesas_raw.empty and 'dataControle' in df_despesas_raw.columns:
        if 'despesa' in df_despesas_raw.columns:
            df_despesas_gerais = df_despesas_raw[df_despesas_raw['despesa'].fillna('').str.upper() == 'S']
        else:
            df_despesas_gerais = df_despesas_raw

        df_despesas_filtrado = apply_filters_to_df(df_despesas_gerais, 'dataControle', start_date, end_date, placa_filter, filial_filter)
        
        if not df_despesas_filtrado.empty:
            df_despesas_filtrado['AnoMes'] = pd.to_datetime(df_despesas_filtrado['dataControle']).dt.to_period('M')
            despesas = df_despesas_filtrado.drop_duplicates(subset=['codNota', 'dataControle']).groupby('AnoMes')['valorNota'].sum()

    monthly_df = pd.DataFrame({'Faturamento': faturamento, 'Despesas': despesas}).fillna(0)
    if isinstance(monthly_df.index, pd.PeriodIndex):
        monthly_df['AnoMes'] = monthly_df.index.strftime('%Y-%m')
    else:
        monthly_df['AnoMes'] = None
    return monthly_df.reset_index(drop=True)

def get_relFilViagensFatCliente_df(start_date=None, end_date=None, placa_filter="Todos", filial_filter="Todos") -> pd.DataFrame:
    df = get_data_as_dataframe("relFilViagensFatCliente")
    if 'permiteFaturar' in df.columns:
        df = df[df['permiteFaturar'].astype(str).str.upper() == 'S']

    if 'custoTotal' not in df.columns:
        df['custoTotal'] = 0.0
    
    date_col = 'dataViagemMotorista'
    return apply_filters_to_df(df, date_col, start_date, end_date, placa_filter, filial_filter)

def get_viagens_frame_df(start_date=None, end_date=None, placa_filter="Todos", filial_filter="Todos") -> pd.DataFrame:
    return get_relFilViagensFatCliente_df(start_date, end_date, placa_filter, filial_filter)

def get_relFilDespesasGerais_df(start_date=None, end_date=None, placa_filter="Todos", filial_filter="Todos") -> pd.DataFrame:
    df_raw = get_data_as_dataframe("relFilDespesasGerais")
    
    if 'despesa' in df_raw.columns:
        df = df_raw[df_raw['despesa'].fillna('').str.upper() == 'S']
    else:
        df = df_raw
        
    date_col = 'dataControle' if 'dataControle' in df.columns else 'dataEmissao'
    return apply_filters_to_df(df, date_col, start_date, end_date, placa_filter, filial_filter)

def get_relFilContasPagarDet_df(start_date=None, end_date=None, filial_filter="Todos") -> pd.DataFrame:
    df = get_data_as_dataframe("relFilContasPagarDet")
    date_col = 'dataVenc' if 'dataVenc' in df.columns else 'dataControle'
    return apply_filters_to_df(df, date_col, start_date, end_date, "Todos", filial_filter)

def get_relFilContasReceber_df(start_date=None, end_date=None, filial_filter="Todos") -> pd.DataFrame:
    df = get_data_as_dataframe("relFilContasReceber")
    date_col = 'dataVenc' if 'dataVenc' in df.columns else 'dataViagemMotorista'
    return apply_filters_to_df(df, date_col, start_date, end_date, "Todos", filial_filter)

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
                static_groups = [row['group_name'] for row in cursor.fetchall()]
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
                    flags_map[row['group_name']] = {
                        'despesa': str(row['is_despesa']).upper(),
                        'custo_viagem': str(row['is_custo_viagem']).upper()
                    }
            except Exception as e:
                print(f"Erro ao buscar flags de grupos estáticos: {e}")
    return flags_map

def update_all_group_flags(final_states: dict):
    """Atualiza as flags para grupos dinâmicos e estáticos."""
    with db.get_db_connection() as conn:
        if conn is None: return
        cursor = conn.cursor()
        try:
            for grupo, flags in final_states.items():
                despesa_flag = 'S' if flags['despesa'] == 'on' else 'N'
                custo_flag = 'S' if flags['custo_viagem'] == 'on' else 'N'

                cursor.execute("SELECT COUNT(*) FROM static_expense_groups WHERE group_name = ?", (grupo,))
                is_static = cursor.fetchone()[0] > 0

                if is_static:
                    cursor.execute(
                        "UPDATE static_expense_groups SET is_despesa = ?, is_custo_viagem = ? WHERE group_name = ?",
                        (despesa_flag, custo_flag, grupo)
                    )
                else:
                    cursor.execute(
                        "UPDATE relFilDespesasGerais SET despesa = ?, e_custo_viagem = ? WHERE descGrupoD = ?",
                        (despesa_flag, custo_flag, grupo)
                    )
                    if custo_flag == 'S':
                        cursor.execute("UPDATE relFilDespesasGerais SET custoTotal = valorNota WHERE descGrupoD = ?", (grupo,))
                    else:
                        cursor.execute("UPDATE relFilDespesasGerais SET custoTotal = 0 WHERE descGrupoD = ?", (grupo,))
            conn.commit()
            print("Flags de grupo de despesa atualizadas com sucesso.")
        except Exception as e:
            print(f"Erro ao atualizar flags de grupo de despesa: {e}")
            conn.rollback()