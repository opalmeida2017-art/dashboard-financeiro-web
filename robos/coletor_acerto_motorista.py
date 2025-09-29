# robos/coletor_acerto_motorista.py (VERSÃO REATORADA)

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logic
import database as db
import robos.base_robo as base_robo  # Importa nossa nova base
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

def executar_coleta_acerto_motorista(apartamento_id: int):
    db.logar_progresso(apartamento_id, f"\n--- INICIANDO ROBÔ: ACERTO DE MOTORISTA ---")
    
    driver = None
    try:
        # --- ETAPA 1: CONFIGURAÇÃO ---
        configs = logic.ler_configuracoes_robo(apartamento_id)
        configs['apartamento_id'] = apartamento_id # Adiciona o ID ao dict para uso no login
        CODIGO_RELATORIO = configs.get('CODIGO_ACERTO_MOTORISTA')
        DATA_INICIAL = configs.get('DATA_INICIAL_ROBO')
        DATA_FINAL = configs.get('DATA_FINAL_ROBO')

        if not all([configs.get('USUARIO_ROBO'), configs.get('SENHA_ROBO'), configs.get('URL_LOGIN')]):
            db.logar_progresso(apartamento_id, "ERRO: As configurações de URL, Usuário ou Senha não foram definidas.")
            return

        driver, pasta_downloads = base_robo.configurar_driver(apartamento_id)
        wait = WebDriverWait(driver, 60) # Aumentado para 60s para mais robustez
        actions = ActionChains(driver)

        # --- ETAPA 2: EXECUÇÃO (USANDO A BASE) ---
        base_robo.fazer_login(driver, wait, configs)
        base_robo.navegar_para_relatorio(driver, wait, actions, CODIGO_RELATORIO, apartamento_id)

        # --- ETAPA 3: LÓGICA ESPECIALIZADA DESTE ROBÔ ---
        db.logar_progresso(apartamento_id, "Preenchendo o formulário específico de Acerto de Motorista...")
        
        wait.until(EC.visibility_of_element_located((By.ID, 'formrelFilAcertoMot:RelFilAcertoMot_dataIniInputDate'))).clear()
        driver.find_element(By.ID, 'formrelFilAcertoMot:RelFilAcertoMot_dataIniInputDate').send_keys(DATA_INICIAL)
        driver.find_element(By.ID, 'formrelFilAcertoMot:RelFilAcertoMot_dataFimInputDate').clear()
        driver.find_element(By.ID, 'formrelFilAcertoMot:RelFilAcertoMot_dataFimInputDate').send_keys(DATA_FINAL)
        
        Select(driver.find_element(By.ID, 'formrelFilAcertoMot:RelFilAcertoMot_tipoData')).select_by_value('1')
        Select(driver.find_element(By.ID, 'formrelFilAcertoMot:RelFilAcertoMot_tipoFrete')).select_by_value('T')
        Select(driver.find_element(By.ID, 'formrelFilAcertoMot:RelFilAcertoMot_somenteAcertados')).select_by_value('T')
        Select(driver.find_element(By.ID, 'formrelFilAcertoMot:RelFilAcertoMot_resumido')).select_by_value('N')
        Select(driver.find_element(By.ID, 'formrelFilAcertoMot:RelFilAcertoMot_statusCTe')).select_by_value('99')
        Select(driver.find_element(By.ID, 'formrelFilAcertoMot:RelFilAcertoMot_mostraRelAcertoMotAdiant')).select_by_value('S')
        Select(driver.find_element(By.ID, 'formrelFilAcertoMot:RelFilAcertoMot_mostraRelAcertoMotDesp')).select_by_value('S')
        Select(driver.find_element(By.ID, 'formrelFilAcertoMot:RelFilAcertoMot_mostraObsDesp')).select_by_value('S')
        
        actions.key_down(Keys.CONTROL).send_keys(Keys.ENTER).key_up(Keys.CONTROL).perform()
        wait.until(EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, "Clique aqui para visualizar"))).click()
        
        # --- ETAPA 4: DOWNLOAD (USANDO A BASE) ---
        nome_arquivo = "relFilAcertoMot.xls"
        base_robo.esperar_download_concluir(pasta_downloads, nome_arquivo, apartamento_id)
        
        db.logar_progresso(apartamento_id, "ROTEIRO DE COLETA CONCLUÍDO.")

    except Exception as e:
        db.logar_progresso(apartamento_id, f"ERRO CRÍTICO no robô de acerto de motorista: {e}")
    finally:
        if driver:
            db.logar_progresso(apartamento_id, "Fechando o navegador.")
            driver.quit()

# Bloco para teste manual (opcional, mas recomendado)
if __name__ == '__main__':
    if len(sys.argv) > 1:
        apartamento_id_teste = int(sys.argv[1])
        executar_coleta_acerto_motorista(apartamento_id_teste)
    else:
        print("Para testar, forneça um ID de apartamento. Ex: python robos/coletor_acerto_motorista.py 1")