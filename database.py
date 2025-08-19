import database as db
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import os
import pandas as pd
import config
import glob 
from datetime import datetime
import psycopg2.extras # <-- Importação essencial

db_url = os.getenv('DATABASE_URL')
if not db_url:
    raise ValueError("DATABASE_URL não definida. Verifique seu arquivo .env")

engine = create_engine(db_url)

# --- VERSÃO CORRIGIDA DA FUNÇÃO ---
def get_db_connection():
    """
    Retorna uma conexão DBAPI2 nativa (psycopg2) que é compatível com
    o código existente que usa conn.cursor().
    AGORA RETORNA RESULTADOS COMO DICIONÁRIOS.
    """
    # .raw_connection() extrai a conexão psycopg2 de dentro do pool do SQLAlchemy
    raw_conn = engine.raw_connection()
    
    # Esta linha é a correção crucial. Ela instrui a conexão a devolver
    # os resultados como dicionários, resolvendo o 'TypeError' anterior.
    raw_conn.cursor_factory = psycopg2.extras.DictCursor
    
    return raw_conn
# --- FIM DA CORREÇÃO ---

def create_tables():
    """
    Esta função agora é gerenciada pelo Alembic e não deve ser usada diretamente.
    """
    print("AVISO: A criação de tabelas agora é gerenciada pelo Alembic.")
    pass

# Em database.py - SUBSTITUA SUA FUNÇÃO POR ESTA VERSÃO CORRIGIDA

def _clean_and_convert_data(df, table_key):
    """Limpa e converte os tipos de dados do DataFrame antes da importação."""
    original_columns = df.columns.tolist()
    df.columns = [str(col).strip() for col in original_columns]

    # --- INÍCIO DA CORREÇÃO ---
    # Bloco adicionado para tratar colunas que deveriam ser booleanas

    # Mapeamento para colunas com lógica "Sim/Não"
    mapeamento_sim_nao = {
        'S': True,
        'N': False
    }

    # Mapeamento especial para a coluna 'cancelado', que usa 'Ativo'/'Inativo'
    mapeamento_status_cancelado = {
        'Ativo': False,   # Se a viagem está 'Ativa', ela NÃO está cancelada.
        'Inativo': True,  # Se a viagem está 'Inativa', ela ESTÁ cancelada.
        'S': True,        # Adicionando S/N para consistência
        'N': False
    }

    # Lista de colunas a serem tratadas
    colunas_booleanas_gerais = ['fretePago', 'pagaICMS', 'pagaISS', 'quebraSegurada', 'permiteFaturar']

    # Aplica o mapeamento especial para a coluna 'cancelado'
    if 'cancelado' in df.columns:
        df['cancelado'] = df['cancelado'].astype(str).str.strip().map(mapeamento_status_cancelado)

    # Aplica o mapeamento geral para as outras colunas
    for col in colunas_booleanas_gerais:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().map(mapeamento_sim_nao)

    # --- FIM DA CORREÇÃO ---

    for col in df.select_dtypes(include=['object']).columns:
        if df[col].notna().any():
            df[col] = df[col].str.strip()
    
    col_maps = config.TABLE_COLUMN_MAPS.get(table_key, {})
    date_columns_to_process = col_maps.get('date_formats', {}).keys()
    for col_db in date_columns_to_process:
        if col_db in df.columns:
            df[col_db] = pd.to_datetime(df[col_db], errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S')

    for col_type in ['numeric', 'integer']:
        for col_db in col_maps.get(col_type, []):
            if col_db in df.columns:
                df[col_db] = pd.to_numeric(df[col_db], errors='coerce').fillna(0)
                if col_type == 'integer':
                    df[col_db] = df[col_db].astype(int)
    return df

def _validate_columns(excel_columns, table_name):
    """Valida colunas do Excel contra as colunas do banco de dados usando SQLAlchemy."""
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'public' AND table_name = :table_name
            """)
            result = conn.execute(query, {'table_name': table_name})
            db_columns_case_sensitive = {row[0] for row in result}
    except SQLAlchemyError as e:
        print(f"AVISO: Não foi possível ler colunas da tabela '{table_name}'. Erro: {e}")
        return excel_columns, []

    db_columns_lower = {col.lower() for col in db_columns_case_sensitive}
    extra_cols_names = [col for col in excel_columns if col.lower() not in db_columns_lower]
    valid_columns_original_case = [col for col in excel_columns if col.lower() in db_columns_lower]
    return valid_columns_original_case, extra_cols_names

# Em database.py

def import_excel_to_db(excel_source, sheet_name: str, table_name: str, key_columns: list, apartamento_id: int):
    """
    Importa dados do Excel, apagando apenas registros correspondentes para atualizar.
    Usa SQLAlchemy engine para compatibilidade total com pandas e PostgreSQL.
    """
    extra_columns = []
    try:
        df_novo = pd.read_excel(excel_source, sheet_name=sheet_name)
        # A função _clean_and_convert_data já foi corrigida para usar minúsculas
        df_novo = _clean_and_convert_data(df_novo, table_name)
        
        df_novo['apartamento_id'] = apartamento_id

        valid_columns, extra_columns = _validate_columns(df_novo.columns.tolist(), table_name)
        df_import = df_novo[valid_columns]

        if df_import.empty:
            print(f"Nenhum dado válido para importar para a tabela '{table_name}'.")
            return extra_columns
        
        # Inicia uma transação para garantir que a operação seja atômica (ou tudo funciona, ou nada é alterado)
        with engine.begin() as conn:
            print(f"Iniciando importação com atualização para a tabela '{table_name}'...")
            
            # Envia os novos dados para uma tabela temporária
            df_import.to_sql('temp_import', conn, if_exists='replace', index=False)

            # --- INÍCIO DA CORREÇÃO ---
            # Para evitar o erro de "text = bigint", vamos converter (CAST)
            # as colunas de ambos os lados da comparação para TEXT.
            # Isso garante que a comparação de chaves funcione independentemente do tipo de dado.
            
            where_clauses = [
                f'CAST("{col}" AS TEXT) IN (SELECT DISTINCT CAST("{col}" AS TEXT) FROM temp_import)' 
                for col in key_columns
            ]
            where_str = ' AND '.join(where_clauses)
            
            # --- FIM DA CORREÇÃO ---
            
            sql_delete = text(f'DELETE FROM "{table_name}" WHERE {where_str} AND "apartamento_id" = :apt_id;')
            print(f" -> Removendo registros antigos/correspondentes para evitar duplicatas...")
            result = conn.execute(sql_delete, {'apt_id': apartamento_id})
            print(f" -> {result.rowcount} registros antigos foram removidos.")
            
            print(f" -> Inserindo {len(df_import)} novos/atualizados registros...")
            # Insere os dados da planilha na tabela principal
            df_import.to_sql(table_name, conn, if_exists='append', index=False)
            
            print(f" -> Importação para a tabela '{table_name}' concluída com sucesso.")

        return extra_columns
    except Exception as e:
        print(f"Erro ao importar dados da planilha '{sheet_name}' para '{table_name}': {e}")
        raise e

def import_single_excel_to_db(excel_source, file_key: str, apartamento_id: int):
    """Função auxiliar para importar uma única planilha com base na configuração."""
    file_info = config.EXCEL_FILES_CONFIG.get(file_key)
    if not file_info:
        raise ValueError(f"Chave de arquivo '{file_key}' não encontrada na configuração.")
    
    table_name = file_info["table_name"]
    key_columns = config.TABLE_PRIMARY_KEYS.get(table_name, [])
    if not key_columns:
        raise ValueError(f"Colunas-chave não definidas para a tabela '{table_name}' no config.py")

    return import_excel_to_db(excel_source, file_info["sheet_name"], table_name, key_columns, apartamento_id)

def table_exists(table_name: str) -> bool:
    """Verifica se uma tabela existe no banco de dados, especificando o schema 'public'."""
    try:
        with engine.connect() as conn:
            # CORREÇÃO: Esta query não depende do 'search_path' da sessão.
            # Ela pergunta diretamente ao catálogo do sistema se a tabela existe
            # no schema 'public' com o nome exato fornecido.
            query = text("""
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = :table_name
                )
            """)
            result = conn.execute(query, {'table_name': table_name}).scalar()
            return result or False # Garante o retorno de um booleano

    except SQLAlchemyError as e:
        print(f"Erro ao verificar existência da tabela {table_name}: {e}")
        return False
def processar_downloads_na_pasta(apartamento_id: int):
    """
    Verifica a pasta do projeto por planilhas baixadas, importa-as para o apartamento_id correto,
    renomeia com data/hora e limpa versões antigas.
    """
    print(f"\n--- INICIANDO PROCESSAMENTO PÓS-DOWNLOAD PARA APARTAMENTO {apartamento_id} ---")
    caminho_base = os.getcwd()
    mapa_arquivos_config = {info['path']: chave for chave, info in config.EXCEL_FILES_CONFIG.items()}
    
    for nome_arquivo_base, chave_config in mapa_arquivos_config.items():
        caminho_novo_arquivo = os.path.join(caminho_base, nome_arquivo_base)
        
        if os.path.exists(caminho_novo_arquivo):
            print(f"\nArquivo novo encontrado: '{nome_arquivo_base}'")

            nome_sem_ext, extensao = os.path.splitext(nome_arquivo_base)
            padrao_busca_antigos = os.path.join(caminho_base, f"{nome_sem_ext}_*{extensao}")
            arquivos_antigos_encontrados = glob.glob(padrao_busca_antigos)
            
            if arquivos_antigos_encontrados:
                print(f" -> Excluindo {len(arquivos_antigos_encontrados)} versão(ões) antiga(s)...")
                for arquivo_antigo in arquivos_antigos_encontrados:
                    os.remove(arquivo_antigo)

            try:
                print(f" -> Importando dados para a tabela '{config.EXCEL_FILES_CONFIG[chave_config]['table_name']}'...")
                import_single_excel_to_db(caminho_novo_arquivo, chave_config, apartamento_id)
                print(" -> Importação bem-sucedida.")
            except Exception as e:
                print(f" -> ERRO! Falha ao importar os dados: {e}")
                continue

            try:
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                novo_nome_renomeado = f"{nome_sem_ext}_{timestamp}{extensao}"
                caminho_renomeado = os.path.join(caminho_base, novo_nome_renomeado)
                print(f" -> Renomeando arquivo para '{novo_nome_renomeado}'...")
                os.rename(caminho_novo_arquivo, caminho_renomeado)
            except Exception as e:
                print(f" -> ERRO! Falha ao renomear o arquivo: {e}")

    print("\n--- PROCESSAMENTO PÓS-DOWNLOAD FINALIZADO ---")
