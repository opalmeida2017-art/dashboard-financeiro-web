# coletor_principal.py (VERSÃO COM DATAS PERSONALIZADAS)

import os
import sys
import time
import logic
import shutil
import database as db

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from robos.coletor_viagens import executar_coleta_viagens
from robos.coletor_despesas import executar_coleta_despesas
from robos.coletor_fat_viagens import executar_coleta_fat_viagens
from robos.coletor_contas_pagar import executar_coleta_contas_pagar
from robos.coletor_contas_receber import executar_coleta_contas_receber
from robos.coletor_acerto_motorista import executar_coleta_acerto_motorista

# --- ALTERAÇÃO 1: Adiciona parâmetros de data ---
def executar_todas_as_coletas(apartamento_id: int, start_date_str: str = None, end_date_str: str = None):
    """
    Executa cada robô. Se datas forem fornecidas, os robôs as usarão.
    """
    # --- ALTERAÇÃO 2: Log mais informativo ---
    if start_date_str and end_date_str:
        db.logar_progresso(apartamento_id, f"--- ORQUESTRADOR: Iniciando coleta para o período de {start_date_str} a {end_date_str} ---")
    else:
        db.logar_progresso(apartamento_id, f"--- ORQUESTRADOR: Iniciando coleta com datas da configuração ---")

    pasta_principal = os.path.dirname(os.path.abspath(__file__))
    pasta_downloads = os.path.join(pasta_principal, 'downloads', str(apartamento_id))
    if os.path.exists(pasta_downloads):
        shutil.rmtree(pasta_downloads)

    robos_para_executar = [
        #executar_coleta_viagens,
        #executar_coleta_despesas,
        executar_coleta_fat_viagens,
        #executar_coleta_contas_pagar,
        #executar_coleta_contas_receber,
        #executar_coleta_acerto_motorista
    ]

    for funcao_robo in robos_para_executar:
        nome_do_robo = funcao_robo.__name__
        try:
            # --- ALTERAÇÃO 3: Repassa as datas para cada robô ---
            funcao_robo(apartamento_id, start_date_str=start_date_str, end_date_str=end_date_str)
            db.logar_progresso(apartamento_id, f">>> Robô {nome_do_robo} finalizado com sucesso.")
        except Exception as e:
            db.logar_progresso(apartamento_id, f">>> ERRO CRÍTICO ao executar {nome_do_robo}. Erro: {e}")
        
        time.sleep(2)

    db.logar_progresso(apartamento_id, "Todos os roteiros de coleta foram executados. Iniciando processamento dos arquivos baixados...")
    logic.processar_downloads_na_pasta(apartamento_id)
    db.logar_progresso(apartamento_id, "--- ORQUESTRADOR FINALIZADO COM SUCESSO ---")

if __name__ == '__main__':
    # ... (bloco de teste permanece o mesmo)
    pass