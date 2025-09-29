# robos/coletor_despesas.py (VERSÃO REATORADA)
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logic
import database as db
import robos.base_robo as base_robo
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

def executar_coleta_despesas(apartamento_id: int):
    db.logar_progresso(apartamento_id, f"\n--- INICIANDO ROBÔ: DESPESAS GERAIS E CUSTO ---")
    
    driver = None
    try:
        # --- ETAPA 1: CONFIGURAÇÃO ---
        configs = logic.ler_configuracoes_robo(apartamento_id)
        configs['apartamento_id'] = apartamento_id
        CODIGO_RELATORIO = configs.get('CODIGO_DESPESAS', '') 
        DATA_INICIAL = configs.get('DATA_INICIAL_ROBO', '01/01/2000')
        DATA_FINAL = configs.get('DATA_FINAL_ROBO', '31/12/2999')
        
        if not all([configs.get('USUARIO_ROBO'), configs.get('SENHA_ROBO'), configs.get('URL_LOGIN')]):
            db.logar_progresso(apartamento_id, "ERRO: As configurações de URL, Usuário ou Senha não foram definidas.")
            return

        driver, pasta_downloads = base_robo.configurar_driver(apartamento_id)
        wait = WebDriverWait(driver, 60)
        actions = ActionChains(driver)

        # --- ETAPA 2: EXECUÇÃO (USANDO A BASE) ---
        base_robo.fazer_login(driver, wait, configs)
        base_robo.navegar_para_relatorio(driver, wait, actions, CODIGO_RELATORIO, apartamento_id)

        # --- ETAPA 3: LÓGICA ESPECIALIZADA DESTE ROBÔ ---
        db.logar_progresso(apartamento_id, "Preenchendo o formulário específico de Despesas...")
        
        wait.until(EC.visibility_of_element_located((By.ID, 'formrelFilDespesasGerais:RelFilDespesasGerais_dataIniInputDate'))).clear()
        driver.find_element(By.ID, 'formrelFilDespesasGerais:RelFilDespesasGerais_dataIniInputDate').send_keys(DATA_INICIAL)
        driver.find_element(By.ID, 'formrelFilDespesasGerais:RelFilDespesasGerais_dataFimInputDate').clear()
        driver.find_element(By.ID, 'formrelFilDespesasGerais:RelFilDespesasGerais_dataFimInputDate').send_keys(DATA_FINAL)
        
        Select(driver.find_element(By.ID, 'formrelFilDespesasGerais:RelFilDespesasGerais_despesa')).select_by_value('S')
        Select(driver.find_element(By.ID, 'formrelFilDespesasGerais:RelFilDespesasGerais_investimento')).select_by_value('T')
        Select(driver.find_element(By.ID, 'formrelFilDespesasGerais:RelFilDespesasGerais_rateio')).select_by_value('T')
        Select(driver.find_element(By.ID, 'formrelFilDespesasGerais:RelFilDespesasGerais_finalizada')).select_by_value('T')
        Select(driver.find_element(By.ID, 'formrelFilDespesasGerais:RelFilDespesasGerais_tipoDespesa')).select_by_value('7')
        Select(driver.find_element(By.ID, 'formrelFilDespesasGerais:RelFilDespesasGerais_faturada')).select_by_value('T')
        Select(driver.find_element(By.ID, 'formrelFilDespesasGerais:RelFilDespesasGerais_mostrarItemDet')).select_by_value('N')
        Select(driver.find_element(By.ID, 'formrelFilDespesasGerais:RelFilDespesasGerais_serieRQ')).select_by_value('T')
        Select(driver.find_element(By.ID, 'formrelFilDespesasGerais:RelFilDespesasGerais_mostrarObs')).select_by_value('N')
        Select(driver.find_element(By.ID, 'formrelFilDespesasGerais:RelFilDespesasGerais_mostrarValoresRateados')).select_by_value('N')
        
        actions.key_down(Keys.CONTROL).send_keys(Keys.ENTER).key_up(Keys.CONTROL).perform()
        wait.until(EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, "Clique aqui para visualizar"))).click()
        
        # --- ETAPA 4: DOWNLOAD (USANDO A BASE) ---
        nome_arquivo = "relFilDespesasGerais.xls"
        base_robo.esperar_download_concluir(pasta_downloads, nome_arquivo, apartamento_id)

        db.logar_progresso(apartamento_id, "ROTEIRO DE COLETA CONCLUÍDO.")
             
    except Exception as e:
        db.logar_progresso(apartamento_id, f"ERRO CRÍTICO no robô de despesas: {e}")
    finally:
        if driver:
            db.logar_progresso(apartamento_id, "Fechando o navegador.")
            driver.quit()           
             
if __name__ == '__main__':
    if len(sys.argv) > 1:
        apartamento_id_teste = int(sys.argv[1])
        executar_coleta_despesas(apartamento_id_teste)
    else:
        print("Para testar, forneça um ID de apartamento. Ex: python robos/coletor_despesas.py 1")