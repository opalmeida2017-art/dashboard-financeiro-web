# coletor_principal.py (VERSÃO REATORADA)

import os
import sys
import time
import logic
import shutil
import database as db

# Adiciona a pasta principal ao caminho para encontrar os outros módulos
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Importa as FUNÇÕES diretamente, não os arquivos
from robos.coletor_viagens import executar_coleta_viagens
from robos.coletor_despesas import executar_coleta_despesas
from robos.coletor_fat_viagens import executar_coleta_fat_viagens
from robos.coletor_contas_pagar import executar_coleta_contas_pagar
from robos.coletor_contas_receber import executar_coleta_contas_receber
from robos.coletor_acerto_motorista import executar_coleta_acerto_motorista

def executar_todas_as_coletas(apartamento_id: int):
    """
    Função principal que executa cada robô coletor de forma direta e sequencial.
    """
    db.logar_progresso(apartamento_id, f"--- INICIANDO ORQUESTRADOR DE COLETA PARA O APARTAMENTO ID: {apartamento_id} ---")

    # Limpa a pasta de downloads antes de iniciar
    pasta_principal = os.path.dirname(os.path.abspath(__file__))
    pasta_downloads = os.path.join(pasta_principal, 'downloads', str(apartamento_id))
    if os.path.exists(pasta_downloads):
        db.logar_progresso(apartamento_id, f"Limpando a pasta de downloads antiga: {pasta_downloads}")
        shutil.rmtree(pasta_downloads)

    # Lista de funções de robôs a serem executadas
    robos_para_executar = [
        executar_coleta_viagens,
        executar_coleta_despesas,
        executar_coleta_fat_viagens,
        executar_coleta_contas_pagar,
        executar_coleta_contas_receber,
        executar_coleta_acerto_motorista
    ]

    for funcao_robo in robos_para_executar:
        nome_do_robo = funcao_robo.__name__
        try:
            # Chama a função do robô diretamente
            funcao_robo(apartamento_id)
            db.logar_progresso(apartamento_id, f">>> Robô {nome_do_robo} finalizado com sucesso.")
        except Exception as e:
            # Captura exceções de forma muito mais eficaz que o subprocess
            db.logar_progresso(apartamento_id, f">>> ERRO CRÍTICO ao executar {nome_do_robo}. A execução continuará com o próximo robô. Erro: {e}")
            # Considerar adicionar um 'return' aqui se a falha de um robô deve parar todo o processo
        
        time.sleep(2) # Pausa entre robôs para estabilidade

    db.logar_progresso(apartamento_id, "Todos os roteiros de coleta foram executados. Iniciando processamento dos arquivos baixados...")
    logic.processar_downloads_na_pasta(apartamento_id)
    db.logar_progresso(apartamento_id, "--- ORQUESTRADOR FINALIZADO COM SUCESSO ---")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        apartamento_id_teste = int(sys.argv[1])
        executar_todas_as_coletas(apartamento_id_teste)
    else:
        print("Para testar, forneça um ID de apartamento. Ex: python coletor_principal.py 1")