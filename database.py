# database.py
from sqlalchemy import create_engine, text,inspect
from sqlalchemy.exc import SQLAlchemyError
import shutil
import os
import pandas as pd
import config
import glob 
from datetime import datetime
import psycopg2.extras 
import numpy as np
from dotenv import load_dotenv
load_dotenv()

# Inicializa a conexão do banco de dados de forma consistente
db_url = os.getenv('DATABASE_URL')
if not db_url:
    raise ValueError("DATABASE_URL não definida. Verifique seu arquivo .env")
engine = create_engine(db_url)

def logar_progresso(apartamento_id, mensagem):
    """
    Salva uma mensagem de progresso do robô no banco de dados,
    usando a conexão principal da aplicação.
    """
    print(mensagem) 
    
    try:
        with engine.connect() as conn:
            query = text("""
                INSERT INTO tb_logs_robo (apartamento_id, timestamp, mensagem)
                VALUES (:apartamento_id, NOW(), :mensagem)
            """)
            conn.execute(query, {"apartamento_id": apartamento_id, "mensagem": mensagem})
            conn.commit()
    except Exception as e:
        print(f"--- ERRO CRÍTICO NO LOG: Não foi possível salvar a mensagem no banco. Erro: {e} ---")

def get_db_connection():
    """
    Retorna uma conexão DBAPI2 nativa (psycopg2) que é compatível com
    o código existente que usa conn.cursor().
    AGORA RETORNA RESULTADOS COMO DICIONÁRIOS.
    """
    raw_conn = engine.raw_connection()
    raw_conn.cursor_factory = psycopg2.extras.DictCursor
    return raw_conn

def create_tables():
    """
    Esta função agora é gerenciada pelo Alembic e não deve ser usada diretamente.
    """
    print("AVISO: A criação de tabelas agora é gerenciada pelo Alembic.")
    pass

def _clean_and_convert_data(df, table_key):
    """Limpa e converte os tipos de dados do DataFrame, usando uma limpeza inicial agressiva."""
    
    # --- PASSO 1: Limpeza agressiva inicial ---
    # Substitui o TEXTO 'nan' (case-insensitive) por um nulo real (np.nan) em todo o DataFrame.
    df.replace(to_replace=r'^(nan|NaT)$', value=np.nan, regex=True, inplace=True)

    original_columns = df.columns.tolist()
    df.columns = [str(col).strip() for col in original_columns]

    col_maps = config.TABLE_COLUMN_MAPS.get(table_key, {})
    
    # --- PASSO 2: Conversões de Tipo ---
    # Processa colunas de data
    date_columns_info = col_maps.get('date_formats', {})
    for col_db, date_format in date_columns_info.items():
        if col_db in df.columns:
            df[col_db] = pd.to_datetime(df[col_db], errors='coerce', format=date_format, dayfirst=not date_format)

    # Processa colunas numéricas e inteiras
    for col_type in ['numeric', 'integer']:
        for col_db in col_maps.get(col_type, []):
            if col_db in df.columns:
                if df[col_db].dtype == 'object':
                    # Limpeza específica para colunas que serão convertidas para número
                    df[col_db] = df[col_db].astype(str).str.strip()
                    df[col_db] = df[col_db].str.replace('.', '', regex=False)
                    df[col_db] = df[col_db].str.replace(',', '.', regex=False)
                
                df[col_db] = pd.to_numeric(df[col_db], errors='coerce').fillna(0)
                
                if col_type == 'integer':
                    df[col_db] = df[col_db].astype(int)
    
    # --- PASSO 3: Garantia Final de Conversão de Nulos ---
    # Converte todos os nulos restantes (NaN, NaT) para None.
    df = df.astype(object).where(pd.notna(df), None)
                    
    return df

def _validate_columns(excel_columns, table_name):
    """Valida colunas do Excel contra as colunas do banco de dados usando SQLAlchemy."""
    try:
        with engine.connect() as conn:
            query = text("SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = :table_name")
            result = conn.execute(query, {'table_name': table_name})
            db_columns_case_sensitive = {row[0] for row in result}
    except SQLAlchemyError as e:
        print(f"AVISO: Não foi possível ler colunas da tabela '{table_name}'. Erro: {e}")
        return excel_columns, []

    db_columns_lower = {col.lower() for col in db_columns_case_sensitive}
    extra_cols_names = [col for col in excel_columns if col.lower() not in db_columns_lower]
    valid_columns_original_case = [col for col in excel_columns if col.lower() in db_columns_lower]
    return valid_columns_original_case, extra_cols_names

def import_excel_to_db(excel_source, sheet_name: str, table_name: str, key_columns: list, apartamento_id: int):
    """
    Importa dados do Excel, apagando apenas registros correspondentes para atualizar.
    Usa SQLAlchemy engine para compatibilidade total com pandas e PostgreSQL.
    """
    extra_columns = []
    try:
        df_novo = pd.read_excel(excel_source, sheet_name=sheet_name)
        df_novo = _clean_and_convert_data(df_novo, table_name)
        
        df_novo['apartamento_id'] = apartamento_id

        valid_columns, extra_columns = _validate_columns(df_novo.columns.tolist(), table_name)
        df_import = df_novo[valid_columns]

        if df_import.empty:
            print(f"Nenhum dado válido para importar para a tabela '{table_name}'.")
            return extra_columns
        
        with engine.begin() as conn:
            print(f"Iniciando importação com atualização para a tabela '{table_name}'...")
            
            df_import.to_sql('temp_import', conn, if_exists='replace', index=False)
            
            where_clauses = [f'CAST("{col}" AS TEXT) IN (SELECT DISTINCT CAST("{col}" AS TEXT) FROM temp_import)' for col in key_columns]
            where_str = ' AND '.join(where_clauses)
            
            sql_delete = text(f'DELETE FROM "{table_name}" WHERE {where_str} AND "apartamento_id" = :apt_id;')
            print(f" -> Removendo registros antigos/correspondentes para evitar duplicatas...")
            result = conn.execute(sql_delete, {'apt_id': apartamento_id})
            print(f" -> {result.rowcount} registros antigos foram removidos.")
            
            print(f" -> Inserindo {len(df_import)} novos/atualizados registros...")
            df_import.to_sql(table_name, conn, if_exists='append', index=False)
            
            print(f" -> Importação para a tabela '{table_name}' concluída com sucesso.")

        return extra_columns
    except Exception as e:
        print(f"Erro ao importar dados da planilha '{sheet_name}' para '{table_name}': {e}")
        raise e

def process_and_import_despesas(excel_source, sheet_name: str, table_name: str, apartamento_id: int):
    extra_columns = []
    try:
        df_novo = pd.read_excel(excel_source, sheet_name=sheet_name)
        df_novo = _clean_and_convert_data(df_novo, table_name)
        df_novo['apartamento_id'] = apartamento_id

        if 'VED' in df_novo.columns:
            df_novo = df_novo[df_novo['VED'] != 'E']
        if 'despesa' in df_novo.columns:
            df_novo = df_novo[df_novo['despesa'] == 'S']
        
        valid_columns, extra_columns = _validate_columns(df_novo.columns.tolist(), table_name)
        df_import = df_novo[valid_columns]
        
        if df_import.empty:
            print(f"Nenhum dado válido para importar para a tabela '{table_name}'.")
            return extra_columns
            
        key_columns = ['codItemNota']

        with engine.begin() as conn:
            print(f"Iniciando importação com atualização para a tabela '{table_name}'...")
            
            df_import.to_sql('temp_import', conn, if_exists='replace', index=False)
            
            where_clauses = [f'CAST("{col}" AS TEXT) IN (SELECT DISTINCT CAST("{col}" AS TEXT) FROM temp_import)' for col in key_columns]
            where_str = ' AND '.join(where_clauses)
            
            sql_delete = text(f'DELETE FROM "{table_name}" WHERE {where_str} AND "apartamento_id" = :apt_id;')
            print(f" -> Removendo registros antigos/correspondentes para evitar duplicatas...")
            result = conn.execute(sql_delete, {'apt_id': apartamento_id})
            print(f" -> {result.rowcount} registros antigos foram removidos.")
            
            print(f" -> Inserindo {len(df_import)} novos/atualizados registros...")
            df_import.to_sql(table_name, conn, if_exists='append', index=False)
            
            print(f" -> Importação para a tabela '{table_name}' concluída com sucesso.")

        return extra_columns
    except Exception as e:
        print(f"Erro ao processar e importar dados de despesas: {e}")
        raise e
    
def import_single_excel_to_db(filepath: str, file_key: str, apartamento_id: int):
    try:
        df = pd.read_excel(filepath)
        df['apartamento_id'] = apartamento_id
        
        table_info = config.EXCEL_FILES_CONFIG[file_key]
        table_name = table_info['table']
        
        with engine.connect() as conn:
            inspector = inspect(engine)
            db_columns = [col['name'] for col in inspector.get_columns(table_name)]
            df_final = df[[col for col in df.columns if col in db_columns]]

        df_final.to_sql(table_name, con=engine, if_exists='append', index=False)
        
        print(f"Sucesso: Dados de '{os.path.basename(filepath)}' importados para a tabela '{table_name}'.")
        
    except Exception as e:
        print(f"ERRO ao importar o arquivo '{os.path.basename(filepath)}': {e}")
        raise e
    
def table_exists(table_name: str) -> bool:
    try:
        with engine.connect() as conn:
            query = text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = :table_name)")
            result = conn.execute(query, {'table_name': table_name}).scalar()
            return result or False
    except SQLAlchemyError as e:
        print(f"Erro ao verificar existência da tabela {table_name}: {e}")
        return False

def process_and_import_contas_pagar(excel_source, sheet_name: str, table_name: str, apartamento_id: int):
    extra_columns = []
    try:
        df_novo = pd.read_excel(excel_source, sheet_name=sheet_name)
        df_novo = _clean_and_convert_data(df_novo, table_name)
        df_novo['apartamento_id'] = apartamento_id

        valid_columns, extra_columns = _validate_columns(df_novo.columns.tolist(), table_name)
        df_import = df_novo[valid_columns]
        
        if df_import.empty:
            print(f"Nenhum dado válido para importar para a tabela '{table_name}'.")
            return extra_columns
            
        key_columns = ['codItemNota']

        with engine.begin() as conn:
            print(f"Iniciando importação com atualização para a tabela '{table_name}'...")
            
            df_import.to_sql('temp_import', conn, if_exists='replace', index=False)
            
            where_clauses = [f'CAST("{col}" AS TEXT) IN (SELECT DISTINCT CAST("{col}" AS TEXT) FROM temp_import)' for col in key_columns]
            where_str = ' AND '.join(where_clauses)
            
            sql_delete = text(f'DELETE FROM "{table_name}" WHERE {where_str} AND "apartamento_id" = :apt_id;')
            print(f" -> Removendo registros antigos com base em 'codItemNota'...")
            result = conn.execute(sql_delete, {'apt_id': apartamento_id})
            print(f" -> {result.rowcount} registros antigos foram removidos.")
            
            print(f" -> Inserindo {len(df_import)} novos/atualizados registros...")
            df_import.to_sql(table_name, conn, if_exists='append', index=False)
            
            print(f" -> Importação para a tabela '{table_name}' concluída com sucesso.")

        return extra_columns
    except Exception as e:
        print(f"Erro ao processar e importar dados de Contas a Pagar: {e}")
        raise e

def process_and_import_contas_receber(excel_source, sheet_name: str, table_name: str, apartamento_id: int):
    extra_columns = []
    try:
        df_novo = pd.read_excel(excel_source, sheet_name=sheet_name)
        df_novo = _clean_and_convert_data(df_novo, table_name)
        df_novo['apartamento_id'] = apartamento_id

        valid_columns, extra_columns = _validate_columns(df_novo.columns.tolist(), table_name)
        df_import = df_novo[valid_columns]
        
        if df_import.empty:
            print(f"Nenhum dado válido para importar para a tabela '{table_name}'.")
            return extra_columns
            
        key_columns = ['codDuplicataReceber']

        with engine.begin() as conn:
            print(f"Iniciando importação com atualização para a tabela '{table_name}'...")
            
            df_import.to_sql('temp_import', conn, if_exists='replace', index=False)
            
            where_clauses = [f'CAST("{col}" AS TEXT) IN (SELECT DISTINCT CAST("{col}" AS TEXT) FROM temp_import)' for col in key_columns]
            where_str = ' AND '.join(where_clauses)
            
            sql_delete = text(f'DELETE FROM "{table_name}" WHERE {where_str} AND "apartamento_id" = :apt_id;')
            print(f" -> Removendo registros antigos com base em 'codDuplicataReceber'...")
            result = conn.execute(sql_delete, {'apt_id': apartamento_id})
            print(f" -> {result.rowcount} registros antigos foram removidos.")
            
            print(f" -> Inserindo {len(df_import)} novos/atualizados registros...")
            df_import.to_sql(table_name, conn, if_exists='append', index=False)
            
            print(f" -> Importação para a tabela '{table_name}' concluída com sucesso.")

        return extra_columns
    except Exception as e:
        print(f"Erro ao processar e importar dados de Contas a Receber: {e}")
        raise e

def processar_downloads_na_pasta(apartamento_id: int):
    logar_progresso(apartamento_id, f"--- INICIANDO PROCESSAMENTO PÓS-DOWNLOAD PARA APARTAMENTO {apartamento_id} ---")
    
    pasta_principal = os.path.dirname(os.path.abspath(__file__))
    pasta_downloads = os.path.join(pasta_principal, 'downloads', str(apartamento_id))

    if not os.path.exists(pasta_downloads):
        logar_progresso(apartamento_id, f"Aviso: Pasta de downloads não encontrada: {pasta_downloads}")
        return

    for filename in os.listdir(pasta_downloads):
        if filename.endswith(('.xls', '.xlsx')):
            file_key = {info['path']: key for key, info in config.EXCEL_FILES_CONFIG.items()}.get(filename)
            
            if file_key:
                caminho_completo = os.path.join(pasta_downloads, filename)
                try:
                    table_info = config.EXCEL_FILES_CONFIG[file_key]
                    sheet_name = table_info.get('sheet_name')
                    table_name = table_info['table']
                    
                    if table_name == 'relFilDespesasGerais':
                        process_and_import_despesas(caminho_completo, sheet_name, table_name, apartamento_id)
                    elif table_name == 'relFilContasPagarDet':
                        process_and_import_contas_pagar(caminho_completo, sheet_name, table_name, apartamento_id)
                    elif table_name == 'relFilContasReceber':
                        process_and_import_contas_receber(caminho_completo, sheet_name, table_name, apartamento_id)
                    else:
                        key_columns = config.TABLE_PRIMARY_KEYS.get(table_name)
                        if not key_columns:
                            logar_progresso(apartamento_id, f"ERRO: Chaves primárias não definidas para '{table_name}'.")
                            continue
                        import_excel_to_db(caminho_completo, sheet_name, table_name, key_columns, apartamento_id)
                    
                    os.unlink(caminho_completo)
                    logar_progresso(apartamento_id, f"Ficheiro '{filename}' processado e removido com sucesso.")

                except Exception as e:
                    logar_progresso(apartamento_id, f"Falha ao processar '{filename}'. Erro: {e}")
            else:
                logar_progresso(apartamento_id, f"Aviso: Ficheiro '{filename}' não reconhecido.")

    logar_progresso(apartamento_id, "--- PROCESSAMENTO PÓS-DOWNLOAD FINALIZADO ---")