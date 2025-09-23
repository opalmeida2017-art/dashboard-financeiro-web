# calcular_valor.py (VERSÃO CORRIGIDA)

import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os
import database as db # <-- 1. IMPORTA O ARQUIVO database.py

load_dotenv()

# Configurações do banco de dados e arquivos
db_url = os.getenv('DATABASE_URL')
engine = create_engine(db_url)

# Caminho para o arquivo Excel e nome da tabela de destino
caminho_arquivo = "downloads/2/relFilViagensFatCliente.xls"
tabela_destino = "relFilViagensFatCliente"

# IMPORTANTE: Chave da tabela conforme definido em config.py
# Use a chave correta que corresponde a 'tabela_destino'
key_da_tabela_no_config = 'viagens' # Ex: 'viagens' ou 'viagens_cliente'

try:
    print(f"Lendo o arquivo: {caminho_arquivo}...")
    df = pd.read_excel(caminho_arquivo)
    print("Leitura concluída com sucesso.")

    # --- INÍCIO DA CORREÇÃO ---
    # 2. CHAMA A FUNÇÃO DE LIMPEZA ANTES DE SALVAR
    # Usa a mesma função de limpeza do sistema principal para garantir a consistência dos dados
    print("Aplicando limpeza e conversão de dados...")
    df = db._clean_and_convert_data(df, key_da_tabela_no_config)
    print("Limpeza de dados concluída.")
    # --- FIM DA CORREÇÃO ---

    # Insere os dados limpos no banco de dados
    print(f"Inserindo dados na tabela '{tabela_destino}'...")
    df.to_sql(tabela_destino, engine, if_exists='replace', index=False)
    print("Dados inseridos com sucesso!")

except FileNotFoundError:
    print(f"Erro: O arquivo '{caminho_arquivo}' não foi encontrado.")
except Exception as e:
    print(f"Ocorreu um erro durante o processo: {e}")