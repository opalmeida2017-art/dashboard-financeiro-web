import sys
import os
from sqlalchemy import text
import shutil # Importação necessária para remover pastas
import config

# Importa a conexão centralizada com o banco de dados
try:
    from db_connection import engine
except ImportError:
    print("ERRO: Não foi possível encontrar 'db_connection.py'.")
    print("Certifique-se de que o arquivo com a conexão do SQLAlchemy (engine) existe.")
    sys.exit(1)


def limpar_pasta_downloads(apartamento_id: int):
    """
    Remove todos os arquivos e a pasta de downloads de um apartamento específico.
    """
    pasta_principal = os.path.dirname(os.path.abspath(__file__))
    pasta_downloads = os.path.join(pasta_principal, 'downloads', str(apartamento_id))

    if os.path.exists(pasta_downloads):
        print(f"-> Removendo pasta de downloads temporária: {pasta_downloads}")
        try:
            shutil.rmtree(pasta_downloads)
            print("-> Pasta removida com sucesso.")
        except Exception as e:
            print(f"Aviso: Não foi possível remover a pasta. Erro: {e}")
    else:
        print("-> Aviso: Pasta de downloads não encontrada.")


def limpar_dados_importados(apartamento_id: int):
    """
    Remove todos os registros associados a um apartamento específico das tabelas de dados importados.
    A confirmação manual foi removida para permitir a automação.
    """
    
    tabelas_importadas = [
        info["table"] for info in config.EXCEL_FILES_CONFIG.values()
    ]
    
    tabelas_dependentes = [
        "static_expense_groups", 
        "tb_logs_robo" 
    ]
    
    tabelas_para_limpar = tabelas_importadas + tabelas_dependentes
    
    print(f"\nAs seguintes tabelas serão limpas para o apartamento ID {apartamento_id}:")
    for tabela in tabelas_para_limpar:
        print(f"- {tabela}")

    try:
        with engine.connect() as conn:
            with conn.begin() as trans:
                print("\nIniciando a limpeza dos dados...")
                for tabela in tabelas_para_limpar:
                    try:
                        query = text(f'DELETE FROM "{tabela}" WHERE apartamento_id = :apt_id')
                        result = conn.execute(query, {"apt_id": apartamento_id})
                        print(f"-> {result.rowcount} registros removidos de '{tabela}'.")
                    except Exception as e:
                        print(f"Aviso: Não foi possível limpar a tabela '{tabela}'. Erro: {e}")
            
            print("\nLimpeza de dados no banco de dados concluída com sucesso!")
        
        # Chama a função para limpar a pasta de downloads após a limpeza do banco
        limpar_pasta_downloads(apartamento_id)


    except Exception as e:
        print(f"\nOcorreu um erro crítico durante a operação. Nenhuma alteração foi salva. Erro: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("ERRO: Por favor, forneça o ID do apartamento que deseja limpar.")
        print("Uso: python limpar_dados.py <ID_DO_APARTAMENTO>")
        sys.exit(1)

    try:
        apartamento_id_alvo = int(sys.argv[1])
        limpar_dados_importados(apartamento_id_alvo)
    except ValueError:
        print(f"ERRO: O ID '{sys.argv[1]}' não é um número válido.")
        sys.exit(1)