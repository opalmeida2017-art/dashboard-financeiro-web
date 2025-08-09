# coletor_principal.py (O Orquestrador)

import os
import subprocess
import sys
import time
import logic

# Adiciona a pasta principal ao caminho para encontrar os outros módulos
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# --- CORREÇÃO: Importando os robôs com s nomes de arquivo corretos ---
from robos import base_robo
from robos import coletor_viagens
from robos import coletor_despesas
from robos import coletor_fat_viagens

def executar_todas_as_coletas():
    """
    Função principal que executa cada robô coletor como um processo separado e sequencial.
    """
    print("--- INICIANDO ORQUESTRADOR DE COLETA ---")

    caminho_base = os.path.dirname(os.path.abspath(__file__))

    # --- CORREÇÃO: Usando os nomes de arquivo corretos na lista de tarefas ---
    robos_para_executar = [
        os.path.join(caminho_base, "robos", "coletor_viagens.py"),
        os.path.join(caminho_base, "robos", "coletor_despesas.py"),
        os.path.join(caminho_base, "robos", "coletor_fat_viagens.py"),
    ]

    # Para cada robô na lista, executa-o
    for caminho_do_robo in robos_para_executar:
        nome_do_robo = os.path.basename(caminho_do_robo)
        print(f"\n>>> INICIANDO O SCRIPT: {nome_do_robo}")
        try:
            # Este comando executa o script e ESPERA ele terminar.
            subprocess.run([sys.executable, caminho_do_robo], check=True)
            print(f">>> SCRIPT {nome_do_robo} FINALIZADO COM SUCESSO.")
        except subprocess.CalledProcessError as e:
            print(f">>> ERRO! O SCRIPT {nome_do_robo} FALHOU. Código de erro: {e.returncode}")
        except FileNotFoundError:
            print(f">>> ERRO! O arquivo do robô '{nome_do_robo}' não foi encontrado no caminho '{caminho_do_robo}'.")
        
        time.sleep(5) # Uma pequena pausa entre os robôs

    # No final de tudo, processa os arquivos baixados
    print("\nTodos os roteiros foram executados.")
    print("Processando todos os arquivos baixados na pasta...")
    logic.processar_downloads_na_pasta()
    
    print("\n--- ORQUESTRADOR FINALIZADO ---")

if __name__ == '__main__':
    executar_todas_as_coletas()