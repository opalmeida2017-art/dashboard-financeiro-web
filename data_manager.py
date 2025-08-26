# data_manager.py (versão final com todas as regras implementadas)

import pandas as pd
from sqlalchemy import text
from datetime import datetime
from slugify import slugify
import database as db
from database import engine # <-- ADICIONE ESTA LINHA
import config

def get_data_as_dataframe(table_name: str, apartamento_id: int) -> pd.DataFrame:
    """Busca dados de uma tabela, mantendo os nomes de colunas originais (CamelCase)."""
    if not db.table_exists(table_name):
        print(f"AVISO: Tabela '{table_name}' não existe. Retornando DataFrame vazio.")
        return pd.DataFrame()
    try:
        with db.engine.connect() as conn:
            query = text(f'SELECT * FROM "{table_name}" WHERE apartamento_id = :apt_id')

            # --- ADICIONE ESTA LINHA PARA DEBUGAR ---
            print(f"--- DEBUG SQL --- Executando a consulta: {query}")
            # ----------------------------------------

            df = pd.read_sql_query(query, conn, params={"apt_id": apartamento_id})
            # CORREÇÃO: Apenas remove espaços em branco, MANTÉM O CAMELCASE
            df.columns = [str(col).strip() for col in df.columns]
            return df
    except Exception as e:
        print(f"ERRO CRÍTICO ao carregar dados da tabela '{table_name}': {e}")
        return pd.DataFrame()


def apply_filters_to_df(df: pd.DataFrame, start_date: datetime, end_date: datetime, placa_filter: str, filial_filter: list) -> pd.DataFrame:
    """
    Aplica filtros de data, placa e uma LISTA de filiais a um DataFrame.
    """
    if df.empty:
        return df
    
    df_filtrado = df.copy()
    
    # Lógica de Filtro de Data (sem alterações)
    possible_date_cols = ['dataControle', 'dataViagemMotorista', 'dataVenc']
    date_column_for_filter = next((col for col in possible_date_cols if col in df_filtrado.columns), None)

    for col in possible_date_cols:
        if col in df_filtrado.columns:
            df_filtrado[col] = pd.to_datetime(df_filtrado[col], errors='coerce', dayfirst=True)
    
    if date_column_for_filter and (start_date or end_date):
        df_filtrado.dropna(subset=[date_column_for_filter], inplace=True)
        if not df_filtrado.empty:
            if start_date:
                df_filtrado = df_filtrado[df_filtrado[date_column_for_filter] >= start_date]
            if end_date:
                df_filtrado = df_filtrado[df_filtrado[date_column_for_filter] <= end_date]

    # Lógica de Filtro de Placa (sem alterações)
    if placa_filter and placa_filter != "Todos":
        placa_cols = config.FILTER_COLUMN_MAPS.get("placa", [])
        placa_col_found = next((col for col in placa_cols if col in df_filtrado.columns), None)
        if placa_col_found:
            df_filtrado = df_filtrado[df_filtrado[placa_col_found].astype(str).str.strip().str.upper() == placa_filter.strip().upper()]

    # --- LÓGICA DE FILTRO DE FILIAL ATUALIZADA ---
    # A variável 'filial_filter' agora é uma lista (ex: ['Filial A', 'Filial C'])
    if filial_filter: # Verifica se a lista não está vazia (se alguma checkbox foi marcada)
        filial_cols = config.FILTER_COLUMN_MAPS.get("filial", [])
        filial_col_found = next((col for col in filial_cols if col in df_filtrado.columns), None)
        
        if filial_col_found:
            # O método .isin() do Pandas filtra as linhas onde o valor da coluna
            # está PRESENTE na lista 'filial_filter'.
            filial_filter_upper = [f.strip().upper() for f in filial_filter]
            df_filtrado = df_filtrado[df_filtrado[filial_col_found].astype(str).str.strip().str.upper().isin(filial_filter_upper)]
    # --- FIM DA ALTERAÇÃO ---
            
    return df_filtrado

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
    
    # --- ETAPA 1: LEITURA DE TODOS OS DADOS BRUTOS ---
    df_contas_pagar_raw = get_data_as_dataframe("relFilContasPagarDet", apartamento_id)
    df_contas_receber_raw = get_data_as_dataframe("relFilContasReceber", apartamento_id)
    df_viagens_faturamento_raw = get_data_as_dataframe("relFilViagensFatCliente", apartamento_id)
    df_viagens_cliente_raw = get_data_as_dataframe("relFilViagensCliente", apartamento_id)
    df_despesas_raw = get_data_as_dataframe("relFilDespesasGerais", apartamento_id)
    df_flags = get_all_group_flags(apartamento_id)
    flags_dict = df_flags.set_index('group_name').to_dict('index') if not df_flags.empty else {}

    if not df_viagens_faturamento_raw.empty and 'permiteFaturar' in df_viagens_faturamento_raw.columns:
        df_viagens_faturamento_raw = df_viagens_faturamento_raw[df_viagens_faturamento_raw['permiteFaturar'].astype(str).str.upper() == 'S']

    # --- ETAPA 2: CÁLCULO PRECISO DE PENDÊNCIAS (AGORA SEM FILTROS) ---
    
    # Lógica para "Contas a Pagar Pendentes"
    df_cp_pendentes = df_contas_pagar_raw.copy()
    if not df_cp_pendentes.empty:
        # --- INÍCIO DA CORREÇÃO ---
        # REMOVIDOS OS BLOCOS DE FILTRO DE DATA DESTA SEÇÃO
        # --- FIM DA CORREÇÃO ---
        
        df_cp_pendentes = df_cp_pendentes[df_cp_pendentes['codTransacao'].isnull()]
        key_cols_cp = ['nomeForn', 'numNota', 'valorVenc']
        if all(col in df_cp_pendentes.columns for col in key_cols_cp):
             df_cp_pendentes = df_cp_pendentes.drop_duplicates(subset=key_cols_cp)
        summary['saldo_contas_a_pagar_pendentes'] = df_cp_pendentes['valorVenc'].sum()
    else:
        summary['saldo_contas_a_pagar_pendentes'] = 0
        
    # Lógica para "Contas a Receber Pendentes"
    df_cr_pendentes = df_contas_receber_raw.copy()
    if not df_cr_pendentes.empty:
        # --- INÍCIO DA CORREÇÃO ---
        # REMOVIDOS OS BLOCOS DE FILTRO DE DATA DESTA SEÇÃO
        # --- FIM DA CORREÇÃO ---

        df_cr_pendentes = df_cr_pendentes[df_cr_pendentes['codTransacao'].isnull()]
        summary['saldo_contas_a_receber_pendentes'] = df_cr_pendentes['valorVenc'].sum()
    else:
        summary['saldo_contas_a_receber_pendentes'] = 0

    # --- ETAPA 3: CÁLCULOS DE FATURAMENTO, CUSTO E DESPESA (QUE CONTINUAM USANDO OS FILTROS) ---
    df_viagens_faturamento = apply_filters_to_df(df_viagens_faturamento_raw, start_date, end_date, placa_filter, filial_filter)
    df_viagens_cliente = apply_filters_to_df(df_viagens_cliente_raw, start_date, end_date, placa_filter, filial_filter)
    df_despesas_limpo = df_despesas_raw.drop_duplicates(subset=['dataControle', 'numNota', 'valorVenc', 'nomeForn']) if not df_despesas_raw.empty else df_despesas_raw
    df_despesas_filtrado = apply_filters_to_df(df_despesas_limpo, start_date, end_date, placa_filter, filial_filter)
    
    if not df_despesas_filtrado.empty and not df_flags.empty:
        df_com_flags = pd.merge(df_despesas_filtrado, df_flags, left_on='descGrupoD', right_on='group_name', how='left')
        df_com_flags['is_custo_viagem'] = df_com_flags['is_custo_viagem'].fillna('N')
        df_com_flags['is_despesa'] = df_com_flags['is_despesa'].fillna('S')
        df_custos = df_com_flags[df_com_flags['is_custo_viagem'] == 'S']
        df_despesas_gerais = df_com_flags[df_com_flags['is_despesa'] == 'S']
    else:
        df_custos = pd.DataFrame()
        df_despesas_gerais = df_despesas_filtrado
    
    total_comissao_motorista = 0
    df_comissao_base = df_viagens_cliente.copy()
    if not df_comissao_base.empty and all(c in df_comissao_base.columns for c in ['tipoFrete', 'freteMotorista', 'comissao', 'pagar']):
        df_comissao_base = df_comissao_base[df_comissao_base['pagar'].astype(str).str.upper() != 'N']
        df_comissao_base = df_comissao_base[(df_comissao_base['tipoFrete'].astype(str).str.strip().str.upper() == 'P') & (pd.to_numeric(df_comissao_base['freteMotorista'], errors='coerce') > 0)]
        if not df_comissao_base.empty:
            frete_motorista = pd.to_numeric(df_comissao_base['freteMotorista'], errors='coerce').fillna(0)
            percentual_comissao = pd.to_numeric(df_comissao_base['comissao'], errors='coerce').fillna(0)
            total_comissao_motorista = (frete_motorista * (percentual_comissao / 100)).sum()
            
    valor_quebra_sum = df_viagens_faturamento['valorQuebra'].sum() if 'valorQuebra' in df_viagens_faturamento.columns else 0

    custo_base = df_custos['valorNota'].sum() if not df_custos.empty else 0
    despesa_base = df_despesas_gerais['valorNota'].sum() if not df_despesas_gerais.empty else 0
    
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

def get_relFilViagensFatCliente_df(apartamento_id: int, start_date=None, end_date=None, placa_filter="Todos", filial_filter="Todos"):
    
    # MODIFICADO: Passa o apartamento_id para a busca inicial no banco de dados.
    df = get_data_as_dataframe("relFilViagensFatCliente", apartamento_id)
    
    if 'permiteFaturar' in df.columns:
        df = df[df['permiteFaturar'].astype(str).str.upper() == 'S']
        
    return apply_filters_to_df(df, start_date, end_date, placa_filter, filial_filter)


def sync_expense_groups(apartamento_id: int):
    """
    Sincroniza os grupos de despesa, garantindo que os grupos especiais
    (Quebra e Comissão) também existam para classificação.
    """
    print(f"Sincronizando grupos de despesa para o apartamento {apartamento_id}...")

    # 1. Busca os grupos dinâmicos da tabela de despesas
    df_despesas = get_data_as_dataframe("relFilDespesasGerais", apartamento_id)
    if not df_despesas.empty and 'descGrupoD' in df_despesas.columns:
        grupos_dinamicos = set(df_despesas['descGrupoD'].dropna().unique())
    else:
        grupos_dinamicos = set()

    # 2. Define os grupos especiais que são calculados e não importados
    grupos_especiais = {'VALOR QUEBRA', 'COMISSÃO DE MOTORISTA'}

    # 3. Combina todos os grupos, garantindo que não haja duplicatas
    todos_os_grupos = list(grupos_dinamicos.union(grupos_especiais))

    if not todos_os_grupos:
        print("Nenhum grupo de despesa para sincronizar.")
        return

    # 4. Insere todos os grupos que ainda não existem na tabela de regras
    try:
        with engine.connect() as conn:
            with conn.begin() as trans:
                sql = text("""
                    INSERT INTO "static_expense_groups" (apartamento_id, group_name)
                    VALUES (:apt_id, :group_name)
                    ON CONFLICT (apartamento_id, group_name) DO NOTHING
                """)

                for group_name in todos_os_grupos:
                    if group_name: # Garante que não insira nomes vazios
                        conn.execute(sql, {"apt_id": apartamento_id, "group_name": group_name})

        print("Sincronização de grupos concluída com sucesso.")
    except Exception as e:
        print(f"ERRO CRÍTICO durante a sincronização de grupos: {e}")

# SUBSTITUA a função get_all_group_flags pela versão abaixo

def get_all_group_flags(apartamento_id: int):
    try:
        # CORREÇÃO: Usando o engine para a conexão, que suporta 'with...as...'
        with db.engine.connect() as conn:
            query = text('SELECT "group_name", "is_despesa", "is_custo_viagem" FROM "static_expense_groups" WHERE "apartamento_id" = :apt_id')
            df = pd.read_sql(query, conn, params={"apt_id": apartamento_id})
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

def update_all_group_flags(apartamento_id: int, update_data: dict):
    """
    Atualiza as flags de classificação e sincroniza as colunas na tabela de dados.
    VERSÃO FINAL: Usa SQLAlchemy Core para todas as operações de forma segura e transacional.
    """
    # A importação 'from database import engine' no topo do arquivo é essencial.
    try:
        with engine.connect() as conn:
            # Este bloco gerencia a transação (commit/rollback) automaticamente.
            with conn.begin() as trans:
                
                # Etapa 1: Atualiza a tabela de regras (static_expense_groups)
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

                # Busca as regras recém-atualizadas para usar na sincronização
                df_flags = get_all_group_flags(apartamento_id)

                # Etapa 2: Sincroniza a coluna 'despesa'
                grupos_de_despesa = tuple(df_flags[df_flags['is_despesa'] == 'S']['group_name'])
                if grupos_de_despesa:
                    conn.execute(text(
                        'UPDATE "relFilDespesasGerais" SET "despesa" = \'S\' WHERE "descGrupoD" IN :lista AND "apartamento_id" = :apt_id'
                    ), {"lista": grupos_de_despesa, "apt_id": apartamento_id})

                grupos_de_custo = tuple(df_flags[df_flags['is_custo_viagem'] == 'S']['group_name'])
                if grupos_de_custo:
                    conn.execute(text(
                        'UPDATE "relFilDespesasGerais" SET "despesa" = \'N\' WHERE "descGrupoD" IN :lista AND "apartamento_id" = :apt_id'
                    ), {"lista": grupos_de_custo, "apt_id": apartamento_id})

                grupos_nenhum = tuple(df_flags[(df_flags['is_despesa'] == 'N') & (df_flags['is_custo_viagem'] == 'N')]['group_name'])
                if grupos_nenhum:
                    conn.execute(text(
                        'UPDATE "relFilDespesasGerais" SET "despesa" = \'0\' WHERE "descGrupoD" IN :lista AND "apartamento_id" = :apt_id'
                    ), {"lista": grupos_nenhum, "apt_id": apartamento_id})

                # Etapa 3: Sincroniza a coluna 'custoTotal'
                if grupos_de_custo:
                    conn.execute(text(
                        'UPDATE "relFilDespesasGerais" SET "custoTotal" = "valorNota" WHERE "descGrupoD" IN :lista AND "apartamento_id" = :apt_id'
                    ), {"lista": grupos_de_custo, "apt_id": apartamento_id})
                
                # Zera o custoTotal para todos os outros grupos do apartamento
                grupos_nao_custo = tuple(df_flags[df_flags['is_custo_viagem'] != 'S']['group_name'])
                if grupos_nao_custo:
                    conn.execute(text(
                        'UPDATE "relFilDespesasGerais" SET "custoTotal" = 0 WHERE "descGrupoD" IN :lista AND "apartamento_id" = :apt_id'
                    ), {"lista": grupos_nao_custo, "apt_id": apartamento_id})

        print(f"Flags, despesa e custoTotal atualizados com sucesso para o apartamento {apartamento_id}.")

    except Exception as e:
        # O rollback é automático ao sair do 'with' com erro.
        print(f"Erro ao atualizar flags de grupo de despesa: {e}")
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

# Em data_manager.py

def get_faturamento_details_dashboard_data(apartamento_id: int, start_date, end_date, placa_filter, filial_filter):
    """Prepara os dados para todos os gráficos da página de detalhes de faturamento."""
    
    df_fat_raw = get_data_as_dataframe("relFilViagensFatCliente", apartamento_id)
    df_fat = apply_filters_to_df(df_fat_raw, start_date, end_date, placa_filter, filial_filter)

    df_viagens_raw = get_data_as_dataframe("relFilViagensCliente", apartamento_id)
    df_viagens = apply_filters_to_df(df_viagens_raw, start_date, end_date, placa_filter, filial_filter)
    
    dashboard_data = {}
    periodo = 'D' if start_date and end_date else 'M'

    df_despesas_raw = get_data_as_dataframe("relFilDespesasGerais", apartamento_id)
    df_despesas_filtrado = apply_filters_to_df(df_despesas_raw, start_date, end_date, placa_filter, filial_filter)
    
    df_flags = get_all_group_flags(apartamento_id)
    flags_dict = df_flags.set_index('group_name').to_dict('index') if not df_flags.empty else {}
    
    df_despesas_processed = df_despesas_filtrado.drop_duplicates(subset=['dataControle', 'numNota', 'valorVenc']) if not df_despesas_filtrado.empty else pd.DataFrame()
    df_com_flags = pd.merge(df_despesas_processed, df_flags, left_on='descGrupoD', right_on='group_name', how='left') if not df_despesas_processed.empty and not df_flags.empty else df_despesas_processed
    
    if not df_com_flags.empty:
        df_com_flags['is_custo_viagem'] = df_com_flags['is_custo_viagem'].fillna('N')
        df_com_flags['is_despesa'] = df_com_flags['is_despesa'].fillna('S')
    
    df_custos_final = df_com_flags[df_com_flags['is_custo_viagem'] == 'S'].copy() if not df_com_flags.empty else pd.DataFrame()
    
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

    fat_evolucao = pd.Series(dtype=float)
    if not df_fat.empty and 'dataViagemMotorista' in df_fat.columns:
        df_fat_copy = df_fat.copy()
        df_fat_copy['Periodo'] = pd.to_datetime(df_fat_copy['dataViagemMotorista'], errors='coerce', dayfirst=True).dt.to_period(periodo)
        fat_evolucao = df_fat_copy.groupby('Periodo')['freteEmpresa'].sum()

    custo_evolucao = pd.Series(dtype=float)
    if not df_custos_final.empty and 'dataControle' in df_custos_final.columns:
        df_custos_copy = df_custos_final.copy()
        df_custos_copy['Periodo'] = pd.to_datetime(df_custos_copy['dataControle'], errors='coerce', dayfirst=True).dt.to_period(periodo)
        custo_evolucao = df_custos_copy.groupby('Periodo')['valorNota'].sum()
        
    evolucao_df = pd.DataFrame({'Faturamento': fat_evolucao, 'Custo': custo_evolucao}).fillna(0).reset_index()
    evolucao_df.rename(columns={'index': 'Periodo'}, inplace=True)
    evolucao_df['Periodo'] = evolucao_df['Periodo'].astype(str)
    dashboard_data['evolucao_faturamento_custo'] = evolucao_df.to_dict('records')
    
    if not df_fat.empty:
        top_clientes = df_fat.groupby('nomeCliente')['freteEmpresa'].sum().nlargest(10).reset_index()
        dashboard_data['top_clientes'] = top_clientes.to_dict(orient='records')

        fat_filial = df_fat.groupby('nomeFilial')['freteEmpresa'].sum().reset_index()
        dashboard_data['faturamento_filial'] = fat_filial.to_dict(orient='records')
            
    if not df_viagens.empty:
        if 'cidOrigemFormat' in df_viagens.columns and 'cidDestinoFormat' in df_viagens.columns:
            df_viagens['rota'] = df_viagens['cidOrigemFormat'].str.strip() + ' -> ' + df_viagens['cidDestinoFormat'].str.strip()
            top_rotas = df_viagens['rota'].value_counts().nlargest(10).reset_index()
            top_rotas.columns = ['rota', 'contagem']
            dashboard_data['top_rotas'] = top_rotas.to_dict(orient='records')
            
        if 'pesoSaida' in df_viagens.columns and 'rota' in df_viagens.columns:
            volume_rota = df_viagens.groupby('rota')['pesoSaida'].sum().nlargest(10).reset_index()
            dashboard_data['volume_por_rota'] = volume_rota.to_dict(orient='records')

        if 'placaVeiculo' in df_viagens.columns:
            viagens_veiculo = df_viagens['placaVeiculo'].value_counts().nlargest(10).reset_index()
            viagens_veiculo.columns = ['placa', 'contagem']
            dashboard_data['viagens_por_veiculo'] = viagens_veiculo.to_dict(orient='records')
        
        # --- CORREÇÃO FINAL AQUI ---
        # Usando 'freteEmpresa' para o faturamento e não 'freteMotorista'
        if 'nomeMotorista' in df_viagens.columns and 'freteEmpresa' in df_viagens.columns:
            fat_motorista = df_viagens.groupby('nomeMotorista')['freteEmpresa'].sum().nlargest(10).reset_index()
            dashboard_data['faturamento_motorista'] = fat_motorista.to_dict(orient='records')
            
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
    """Salva um dicionário de configurações para um inquilino específico usando SQLAlchemy Core."""
    try:
        # CORREÇÃO: Usando o método de conexão moderno e seguro
        with db.engine.connect() as conn:
            # Inicia uma transação que faz commit/rollback automaticamente
            with conn.begin() as trans:
                # A cláusula ON CONFLICT é específica do PostgreSQL e faz o "UPSERT" (UPDATE ou INSERT)
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
    """Busca todos os utilizadores de um apartamento específico, EXCLUINDO o Super Admin."""
    # Precisamos aceder à configuração do email do super admin
    from app import app 
    super_admin_email = app.config.get('SUPER_ADMIN_EMAIL')

    with engine.connect() as conn:
        # A query agora tem uma condição extra para excluir o email do super admin
        sql = text("""
            SELECT id, nome, email, role 
            FROM usuarios 
            WHERE apartamento_id = :apt_id AND email != :super_admin_email
        """)
        df = pd.read_sql(sql, conn, params={"apt_id": apartamento_id, "super_admin_email": super_admin_email})
        return df.to_dict(orient='records')
    
# Em data_manager.py

def add_user_to_apartment(apartamento_id: int, nome: str, email: str, password_hash: str, role: str):
    """Adiciona um novo utilizador a um apartamento específico. VERSÃO FINAL."""
    try:
        with engine.connect() as conn:
            # O bloco 'begin' gere a transação (commit/rollback) automaticamente
            with conn.begin() as trans:
                query = text('INSERT INTO usuarios (apartamento_id, nome, email, password_hash, role) VALUES (:apt_id, :nome, :email, :hash, :role)')
                conn.execute(query, {
                    "apt_id": apartamento_id, "nome": nome, "email": email, "hash": password_hash, "role": role
                })
        return True, "Utilizador adicionado com sucesso."
    except Exception as e:
        # Captura erro de email duplicado específico do PostgreSQL
        if "usuarios_email_key" in str(e):
             return False, "Erro: Este email já está registado."
        return False, f"Erro ao adicionar utilizador: {e}"
def update_user_in_apartment(user_id: int, apartamento_id: int, nome: str, email: str, role: str, new_password_hash: str = None):
    """Atualiza os dados de um utilizador, opcionalmente a senha. CORRIGIDO."""
    try:
        with engine.connect() as conn:
            with conn.begin() as trans:
                if new_password_hash:
                    # Se uma nova senha foi fornecida, atualiza tudo incluindo a senha
                    sql = text("""
                        UPDATE usuarios SET nome = :nome, email = :email, role = :role, password_hash = :hash
                        WHERE id = :user_id AND apartamento_id = :apt_id
                    """)
                    conn.execute(sql, {
                        "nome": nome, "email": email, "role": role, "hash": new_password_hash,
                        "user_id": user_id, "apt_id": apartamento_id
                    })
                else:
                    # Caso contrário, atualiza apenas os outros dados
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
        # Captura erro de email duplicado específico do PostgreSQL
        if "usuarios_email_key" in str(e):
             return False, "Erro: Este email já pertence a outro utilizador."
        return False, f"Erro ao atualizar utilizador: {e}"

def delete_user_from_apartment(user_id: int, apartamento_id: int):
    """Apaga um utilizador de um apartamento. CORRIGIDO."""
    try:
        with engine.connect() as conn:
            with conn.begin() as trans:
                sql = text("DELETE FROM usuarios WHERE id = :user_id AND apartamento_id = :apt_id")
                conn.execute(sql, {"user_id": user_id, "apt_id": apartamento_id})
        return True, "Utilizador apagado com sucesso."
    except Exception as e:
        return False, f"Erro ao apagar utilizador: {e}"
# Em data_manager.py

def get_user_by_id(user_id: int, apartamento_id: int):
    """Busca um único utilizador pelo seu ID, garantindo que ele pertence ao apartamento correto. CORRIGIDO."""
    try:
        with engine.connect() as conn:
            sql = text('SELECT id, nome, email, role FROM usuarios WHERE id = :user_id AND apartamento_id = :apt_id')
            result = conn.execute(sql, {"user_id": user_id, "apt_id": apartamento_id})
            user_data = result.mappings().first() # Pega a primeira linha como um dicionário

            if user_data:
                return dict(user_data) # Retorna o dicionário
            return None
    except Exception as e:
        print(f"Erro ao buscar utilizador por ID: {e}")
        return None
    
def get_all_apartments():
    """Busca todos os apartamentos da base de dados. CORRIGIDO."""
    try:
        with engine.connect() as conn: # <--- Método moderno e correto
            df = pd.read_sql('SELECT id, nome_empresa, status, data_criacao FROM apartamentos', conn)
            return df.to_dict(orient='records')
    except Exception as e:
        print(f"Erro ao buscar apartamentos: {e}")
        return []
# Em data_manager.py
# SUBSTITUA a sua função create_apartment_and_admin inteira por esta versão:

# Em data_manager.py

def create_apartment_and_admin(nome_empresa: str, admin_nome: str, admin_email: str, password_hash: str):
    """Cria um novo apartamento e o seu primeiro utilizador admin numa única transação."""
    try:
        with engine.connect() as conn:
            with conn.begin() as trans:
                now = datetime.now().isoformat()
                
                # Gera um slug a partir do nome da empresa (ex: "Empresa Teste" -> "empresa-teste")
                apartamento_slug = slugify(nome_empresa)
                
                # Modifica a query para incluir o slug
                sql_apartamento = text('INSERT INTO apartamentos (nome_empresa, status, data_criacao, slug) VALUES (:nome, :status, :data, :slug) RETURNING id')
                result = conn.execute(sql_apartamento, {
                    "nome": nome_empresa, 
                    "status": 'ativo', 
                    "data": now,
                    "slug": apartamento_slug
                })
                
                apartamento_id = result.scalar_one()

                # O resto da função continua igual...
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
    """Busca os detalhes de um único apartamento pelo seu ID usando SQLAlchemy Core."""
    try:
        # Usando o engine para uma conexão consistente e segura
        with db.engine.connect() as conn:
            # Usando a função text() com named parameters (:apt_id), que é o correto
            query = text('SELECT * FROM apartamentos WHERE id = :apt_id')
            result = conn.execute(query, {"apt_id": apartamento_id})

            # Pega a primeira linha do resultado no formato de dicionário
            apartamento = result.mappings().first()

            return apartamento # Retorna o dicionário ou None se não encontrar
    except Exception as e:
        print(f"Erro ao buscar detalhes do apartamento: {e}")
        return None

def update_apartment_details(apartamento_id: int, nome_empresa: str, status: str, data_vencimento: str, notas: str):
    """Atualiza os detalhes de um apartamento específico usando SQLAlchemy Core."""
    try:
        # CORREÇÃO: Usando o engine para a conexão, que suporta 'with...as...'
        with db.engine.connect() as conn:
            # Inicia uma transação que faz commit/rollback automaticamente
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
        # O rollback é automático ao sair do 'with' com erro
        return False, f"Ocorreu um erro ao atualizar o apartamento: {e}"


def get_apartments_with_usage_stats():
    data_tables = [info["table"] for info in config.EXCEL_FILES_CONFIG.values()]

    try:
        with engine.connect() as conn:
            # CORREÇÃO: Adicionamos a coluna 'slug' à consulta SQL
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
    
def get_monthly_summary(apartamento_id: int, start_date, end_date, placa_filter, filial_filter) -> pd.DataFrame:
    """
    Calcula os totais mensais ou diários de faturamento, custos e despesas
    para alimentar o gráfico principal do dashboard. (Versão Final Robusta)
    """
    periodo_format = 'M'
    if start_date and end_date:
        duracao_dias = (end_date - start_date).days
        if duracao_dias <= 62:
            periodo_format = 'D'

    # --- (Toda a lógica de busca e preparação dos dataframes até o final permanece a mesma) ---
    df_viagens_faturamento_raw = get_data_as_dataframe("relFilViagensFatCliente", apartamento_id)
    df_viagens_faturamento = apply_filters_to_df(df_viagens_faturamento_raw, start_date, end_date, placa_filter, filial_filter)

    df_viagens_cliente_raw = get_data_as_dataframe("relFilViagensCliente", apartamento_id)
    df_viagens_cliente = apply_filters_to_df(df_viagens_cliente_raw, start_date, end_date, placa_filter, filial_filter)

    df_despesas_raw = get_data_as_dataframe("relFilDespesasGerais", apartamento_id)
    df_despesas_filtrado = apply_filters_to_df(df_despesas_raw, start_date, end_date, placa_filter, filial_filter)
    
    df_flags = get_all_group_flags(apartamento_id)
    flags_dict = df_flags.set_index('group_name').to_dict('index') if not df_flags.empty else {}

    df_despesas_processed = df_despesas_filtrado.drop_duplicates(subset=['dataControle', 'numNota', 'valorVenc']) if not df_despesas_filtrado.empty else pd.DataFrame()
    
    df_com_flags = (pd.merge(df_despesas_processed, df_flags, left_on='descGrupoD', right_on='group_name', how='left') 
                    if not df_despesas_processed.empty and not df_flags.empty 
                    else df_despesas_processed).copy()
    
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
    
    if monthly_df.empty:
        return monthly_df

    # --- INÍCIO DA CORREÇÃO ---
    # Simplifica a lógica para ser mais direta e segura.
    monthly_df = monthly_df.reset_index()
    monthly_df.rename(columns={'index': 'Periodo'}, inplace=True)
    
    # Converte o período para um formato de data padrão ANTES de formatar
    monthly_df['Periodo'] = monthly_df['Periodo'].dt.to_timestamp()

    date_format_str = '%d/%m/%Y' if periodo_format == 'D' else '%Y-%m'
    monthly_df['PeriodoLabel'] = monthly_df['Periodo'].dt.strftime(date_format_str)
    
    monthly_df['Periodo'] = monthly_df['Periodo'].astype(str)
    monthly_df = monthly_df.sort_values(by='Periodo', ascending=True)
    # --- FIM DA CORREÇÃO ---
            
    return monthly_df
def get_apartment_by_slug(slug: str):
    """Busca os detalhes de um apartamento pelo seu slug."""
    try:
        with engine.connect() as conn:
            sql = text("SELECT * FROM apartamentos WHERE slug = :slug")
            result = conn.execute(sql, {"slug": slug}).mappings().first()
            return dict(result) if result else None
    except Exception as e:
        print(f"Erro ao buscar apartamento por slug: {e}")
        return None
        
