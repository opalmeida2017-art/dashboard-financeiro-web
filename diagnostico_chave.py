# diagnostico_chave.py (VERSÃO CORRIGIDA)
import pandas as pd
from sqlalchemy import text
from db_connection import engine
import config
import numpy as np # <-- 1. IMPORTAÇÃO ADICIONADA

def comparar_chaves(apartamento_id: int):
    """
    Este script compara um único registro entre a tabela principal e a tabela temporária
    para encontrar a discrepância exata na chave primária.
    """
    TABLE_NAME = 'relFilContasPagarDet'
    TEMP_TABLE_NAME = 'temp_import'
    KEY_COLUMNS = config.TABLE_PRIMARY_KEYS.get(TABLE_NAME)

    print("="*60)
    print("--- INICIANDO SCRIPT DE DIAGNÓSTICO DE CHAVE DUPLICADA ---")
    print(f"Tabela Alvo: {TABLE_NAME}")
    print(f"Chave Primária em Uso: {KEY_COLUMNS}")
    print("="*60)

    try:
        with engine.connect() as conn:
            print("\nBuscando um registro de amostra da tabela temporária (novos dados)...")
            amostra_query = text(f'SELECT * FROM "{TEMP_TABLE_NAME}" LIMIT 1')
            amostra_df = pd.read_sql(amostra_query, conn)

            if amostra_df.empty:
                print("\nERRO: A tabela temporária 'temp_import' está vazia. Por favor, execute o upload do arquivo primeiro e depois rode este script.")
                return

            amostra = amostra_df.iloc[0]
            print("Amostra encontrada. Usando os seguintes valores para a busca:")
            
            where_conditions = ["apartamento_id = :apt_id"]
            params = {'apt_id': apartamento_id}
            
            # --- 2. INÍCIO DA CORREÇÃO ---
            for col in KEY_COLUMNS:
                valor = amostra[col]
                # Converte tipos numpy para tipos nativos do Python
                if isinstance(valor, np.integer):
                    params[col] = int(valor)
                elif isinstance(valor, np.floating):
                    params[col] = float(valor)
                else:
                    params[col] = valor
                where_conditions.append(f'"{col}" = :{col}')
            # --- FIM DA CORREÇÃO ---
            
            where_str = " AND ".join(where_conditions)
            
            query_bd = text(f'SELECT * FROM "{TABLE_NAME}" WHERE {where_str}')
            registro_bd_df = pd.read_sql(query_bd, conn, params=params)

            if registro_bd_df.empty:
                print(f"\nCONCLUSÃO INESPERADA: O registro com a chave {params} NÃO FOI ENCONTRADO na tabela principal '{TABLE_NAME}'.")
                print("Isso pode significar que os dados são realmente novos ou a correspondência já está falhando aqui.")
                print("Amostra do novo registro:")
                print(amostra[KEY_COLUMNS])
                return

            registro_bd = registro_bd_df.iloc[0]
            print("\n--- COMPARAÇÃO DETALHADA ---")

            for col in KEY_COLUMNS:
                val_bd = registro_bd[col]
                val_temp = amostra[col]
                
                print(f"\nCampo: '{col}'")
                print(f"  - Valor no BD Principal: {repr(val_bd)} (Tipo: {type(val_bd)})")
                print(f"  - Valor no Novo Excel  : {repr(val_temp)} (Tipo: {type(val_temp)})")
                print(f"  - São iguais? (==)   : {val_bd == val_temp}")

            print("\n--- FIM DA COMPARAÇÃO ---")
            print("\nANÁLISE: Verifique acima se os tipos de dados são diferentes ou se há caracteres invisíveis (espaços, etc.) mostrados por repr().")

    except Exception as e:
        print(f"\nOcorreu um erro durante o diagnóstico: {e}")

if __name__ == '__main__':
    ID_APARTAMENTO_PARA_TESTE = 2
    comparar_chaves(ID_APARTAMENTO_PARA_TESTE)