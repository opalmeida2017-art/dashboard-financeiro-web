# coletor_principal.py (O Orquestrador - Corrigido)

import os
import subprocess
import sys
import time
import logic

# Adiciona a pasta principal ao caminho para encontrar os outros módulos
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# --- CORREÇÃO: Importando os robôs com os nomes de arquivo corretos ---
from robos import base_robo
from robos import coletor_viagens
from robos import coletor_despesas
from robos import coletor_fat_viagens

# MODIFICADO: A função agora aceita o apartamento_id
def executar_todas_as_coletas(apartamento_id: int):
    """
    Função principal que executa cada robô coletor, passando o ID do apartamento.
    """
    print(f"--- INICIANDO ORQUESTRADOR DE COLETA PARA O APARTAMENTO ID: {apartamento_id} ---")

    caminho_base = os.path.dirname(os.path.abspath(__file__))

    robos_para_executar = [
        os.path.join(caminho_base, "robos", "coletor_viagens.py"),
        os.path.join(caminho_base, "robos", "coletor_despesas.py"),
        os.path.join(caminho_base, "robos", "coletor_fat_viagens.py"),
    ]

    for caminho_do_robo in robos_para_executar:
        nome_do_robo = os.path.basename(caminho_do_robo)
        print(f"\n>>> INICIANDO O SCRIPT: {nome_do_robo}")
        try:
            # MODIFICADO: Passa o apartamento_id como um argumento de linha de comando para o script do robô.
            subprocess.run([sys.executable, caminho_do_robo, str(apartamento_id)], check=True)
            print(f">>> SCRIPT {nome_do_robo} FINALIZADO COM SUCESSO.")
        except subprocess.CalledProcessError as e:
            print(f">>> ERRO! O SCRIPT {nome_do_robo} FALHOU. Código de erro: {e.returncode}")
        except FileNotFoundError:
            print(f">>> ERRO! O arquivo do robô '{nome_do_robo}' não foi encontrado.")
        
        time.sleep(5) # Uma pequena pausa entre os robôs

    print("\nTodos os roteiros foram executados.")
    print("Processando todos os arquivos baixados na pasta...")
    # MODIFICADO: Passa o apartamento_id para a função de processamento final.
    logic.processar_downloads_na_pasta(apartamento_id)
    
    print("\n--- ORQUESTRADOR FINALIZADO ---")

if __name__ == '__main__':
    # Bloco para teste manual. Exemplo: python coletor_principal.py 1
    if len(sys.argv) > 1:
        apartamento_id_teste = int(sys.argv[1])
        executar_todas_as_coletas(apartamento_id_teste)
    else:
        print("Para testar, forneça um ID de apartamento. Ex: python coletor_principal.py 1")
