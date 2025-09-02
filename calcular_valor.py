import pandas as pd

# CORREÇÃO 1: Alterado para o nome exato do arquivo que está na sua pasta.
nome_do_arquivo_excel = 'relFilDespesasGerais.xls'

try:
    # CORREÇÃO 2: Usando pd.read_excel() para ler o arquivo Excel.
    # A aba 'Despesas Gerais' é a mais provável, com base no nome original do arquivo.
    df = pd.read_excel(nome_do_arquivo_excel, sheet_name='Despesas Gerais')

    # 1. Filtra para o grupo 'ACESSORIO'
    df_acessorio = df[df['descGrupoD'] == 'ACESSORIOS'].copy()

    # 2. Aplica os filtros de importação do sistema
    df_filtrado = df_acessorio[
        (df_acessorio['VED'] != 'E') &
        (df_acessorio['despesa'] == 'S')
    ].copy()

    # 3. Limpa e converte a coluna 'liquido' para um formato numérico
    if not df_filtrado.empty:
        df_filtrado['liquido'] = df_filtrado['liquido'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False).astype(float)
        
        # 4. Soma a coluna 'liquido'
        soma_liquido = df_filtrado['liquido'].sum()

        print("\n--- CÁLCULO FINALIZADO ---")
        print(f"Grupo: ACESSORIOS")
        print(f"Soma da coluna 'liquido' (após filtros): {soma_liquido:,.2f}")
        print("--------------------------\n")

    else:
        print("Nenhuma linha para o grupo 'ACESSORIO' passou nos filtros do sistema (VED != 'E' e despesa == 'S').")

except FileNotFoundError:
    print(f"ERRO: O arquivo '{nome_do_arquivo_excel}' não foi encontrado na pasta C:\\python\\BIWEB\\.")
except Exception as e:
    print(f"Ocorreu um erro ao processar o arquivo Excel: {e}")
    print("Dica: Verifique se o nome da aba no seu arquivo Excel é realmente 'Despesas Gerais'.")