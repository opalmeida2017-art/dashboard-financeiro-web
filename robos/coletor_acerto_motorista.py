# robos/coletor_acerto_motorista.py
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import logic
import config
import database as db 
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select

def executar_coleta_acerto_motorista(apartamento_id: int):
    db.logar_progresso(apartamento_id,f"\n--- INICIANDO ROBÔ: ACERTO DE MOTORISTA PARA TRANSPORTADORA ID: {apartamento_id} ---")
    
    configs = logic.ler_configuracoes_robo(apartamento_id)
    USUARIO = configs.get('USUARIO_ROBO')
    SENHA = configs.get('SENHA_ROBO')
    URL_LOGIN = configs.get('URL_LOGIN')
    CODIGO_RELATORIO = configs.get('CODIGO_ACERTO_MOTORISTA', 'SEU_CODIGO_AQUI') 
    DATA_INICIAL = configs.get('DATA_INICIAL_ROBO', '01/01/2000')
    DATA_FINAL = configs.get('DATA_FINAL_ROBO', '31/12/2999')

    if not all([USUARIO, SENHA, URL_LOGIN]):
        print("ERRO: As configurações de URL, Usuário ou Senha não foram definidas.")
        return 
        
    SELECTOR_CAMPO_USUARIO = "input[id='formCad:nome']"
    SELECTOR_CAMPO_SENHA = "input[id='formCad:senha']"
    SELECTOR_BOTAO_ENTRAR = "input[id='formCad:entrar']"

# 1. Configurar as opções do NAVEGADOR
    chrome_options = Options()
    # Ativa o modo "invisível" e adiciona todas as flags de estabilidade e otimização
    #chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-images")
    chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    chrome_options.add_argument("--start-maximized")
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    chrome_options.add_argument(f'user-agent={user_agent}')

    # Configura a pasta de download
    pasta_principal = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pasta_downloads = os.path.join(pasta_principal, 'downloads', str(apartamento_id))
    os.makedirs(pasta_downloads, exist_ok=True)
    prefs = {'download.default_directory': pasta_downloads}
    chrome_options.add_experimental_option('prefs', prefs)

    
    driver = webdriver.Chrome(options=chrome_options)

   
    wait = WebDriverWait(driver, 300)
    driver.set_page_load_timeout(300)
    actions = ActionChains(driver)

    try:
        # --- ETAPA DE LOGIN ---
        db.logar_progresso(apartamento_id, f"Acessando: {URL_LOGIN}")
        driver.get(URL_LOGIN)
        time.sleep(1)
        try:
            WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Limpar Cache e Continuar')]"))).click()
            time.sleep(1)
        except: pass
        try:
            WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, "//button[text()='Fechar']"))).click()
            time.sleep(1)
        except: pass
        
        db.logar_progresso(apartamento_id,"Preenchendo credenciais...")
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, SELECTOR_CAMPO_USUARIO))).send_keys(USUARIO)
        driver.find_element(By.CSS_SELECTOR, SELECTOR_CAMPO_SENHA).send_keys(SENHA)
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, SELECTOR_BOTAO_ENTRAR))).click()
        print("Aguardando login...")
        time.sleep(1)
        
        
        db.logar_progresso(apartamento_id,"Passo 1-2: Acessando 'Cadastro de Exportações'...")

       
        menu_exp_imp = wait.until(EC.visibility_of_element_located((By.XPATH, "//div[contains(@id, '_label') and contains(text(), 'Exp./Imp.')]")))
        actions.move_to_element(menu_exp_imp).perform()
        time.sleep(1)

        
        submenu_cadastro = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Cadastro de Exportações')]")))
        submenu_cadastro.click()
        time.sleep(1)
        
        db.logar_progresso(apartamento_id,f"Passo 3: Preenchendo código '{CODIGO_RELATORIO}'...")
        SELECTOR_CAMPO_CODIGO = "input[id='formexpFil:ExpFil_codExp']"
        campo_codigo = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, SELECTOR_CAMPO_CODIGO)))
        campo_codigo.clear()
        campo_codigo.send_keys(CODIGO_RELATORIO)
        time.sleep(1)
        
        db.logar_progresso(apartamento_id,"Passo 4: Pesquisando com Ctrl+Enter...")
        actions.key_down(Keys.CONTROL).send_keys(Keys.ENTER).key_up(Keys.CONTROL).perform()
        time.sleep(1)
        
        db.logar_progresso(apartamento_id,f"Passo 5: Procurando o link do relatório com código '{CODIGO_RELATORIO}'...")
        seletor_link_relatorio = f"//tr[contains(., '{CODIGO_RELATORIO}')]//a"
        link_relatorio = wait.until(EC.element_to_be_clickable((By.XPATH, seletor_link_relatorio)))
        link_relatorio.click()
        time.sleep(1)
        
        db.logar_progresso(apartamento_id,"Passo 6: Clicando em 'Exportar Dados' para abrir a nova aba...")
        aba_original = driver.current_window_handle
        wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Exportar Dados"))).click()
        
        db.logar_progresso(apartamento_id,"Aguardando a nova aba ser aberta...")
        time.sleep(5)

        todas_as_abas = driver.window_handles
        if len(todas_as_abas) > 1:
            driver.switch_to.window(todas_as_abas[-1])
            db.logar_progresso(apartamento_id," -> Foco mudado para a nova aba do formulário.")
        else:
            db.logar_progresso(apartamento_id," -> Nenhuma nova aba detectada. Procurando por um iframe...")
            wait.until(EC.frame_to_be_available_and_switch_to_it(0))

        db.logar_progresso(apartamento_id,"Passo 7: Procurando e clicando no link de exportação...")
        SELECTOR_LINK_EXPORTACAO = "a[onclick*=\"formCad:j_idt7\"]"
        link_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, SELECTOR_LINK_EXPORTACAO)))
        onclick_script = link_element.get_attribute("onclick")
        
        db.logar_progresso(apartamento_id," -> Link encontrado. Executando o script do link...")
        driver.execute_script(onclick_script)

        db.logar_progresso(apartamento_id,"Aguardando a próxima tela carregar...")
        time.sleep(1)
        
        db.logar_progresso(apartamento_id,"-> Tela do formulário final alcançada! Um screenshot foi salvo.")

        db.logar_progresso(apartamento_id,"Passo 8: Preenchendo o formulário")
        # Preenche as datas
        wait.until(EC.visibility_of_element_located((By.ID, 'formrelFilAcertoMot:RelFilAcertoMot_dataIniInputDate'))).clear()
        driver.find_element(By.ID, 'formrelFilAcertoMot:RelFilAcertoMot_dataIniInputDate').send_keys(DATA_INICIAL)
        driver.find_element(By.ID, 'formrelFilAcertoMot:RelFilAcertoMot_dataFimInputDate').clear()
        driver.find_element(By.ID, 'formrelFilAcertoMot:RelFilAcertoMot_dataFimInputDate').send_keys(DATA_FINAL)
        
        # Seleciona as opções nos dropdowns
        Select(driver.find_element(By.ID, 'formrelFilAcertoMot:RelFilAcertoMot_tipoData')).select_by_value('1')
        Select(driver.find_element(By.ID, 'formrelFilAcertoMot:RelFilAcertoMot_tipoFrete')).select_by_value('T')
        Select(driver.find_element(By.ID, 'formrelFilAcertoMot:RelFilAcertoMot_somenteAcertados')).select_by_value('T')
        Select(driver.find_element(By.ID, 'formrelFilAcertoMot:RelFilAcertoMot_resumido')).select_by_value('N')
        Select(driver.find_element(By.ID, 'formrelFilAcertoMot:RelFilAcertoMot_statusCTe')).select_by_value('99')
        Select(driver.find_element(By.ID, 'formrelFilAcertoMot:RelFilAcertoMot_mostraRelAcertoMotAdiant')).select_by_value('S')
        Select(driver.find_element(By.ID, 'formrelFilAcertoMot:RelFilAcertoMot_mostraRelAcertoMotDesp')).select_by_value('S')
        Select(driver.find_element(By.ID, 'formrelFilAcertoMot:RelFilAcertoMot_mostraObsDesp')).select_by_value('S')
        
        time.sleep(1)
        db.logar_progresso(apartamento_id,"Passo 9: Pressionando Ctrl + Enter para gerar o link de download...")
        actions.key_down(Keys.CONTROL).send_keys(Keys.ENTER).key_up(Keys.CONTROL).perform()
        
        db.logar_progresso(apartamento_id,"Passo 10: Clicando no link final para baixar...")
        link_final = wait.until(EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, "Clique aqui para visualizar")))
        link_final.click()
        
        nome_do_arquivo_esperado = "relFilAcertoMot.xls" # Confirme se este é o nome correto
        caminho_do_arquivo = os.path.join(pasta_downloads, nome_do_arquivo_esperado)
        
        db.logar_progresso(apartamento_id, f"Download do arquivo '{nome_do_arquivo_esperado}' iniciado!")
        
        # Lógica de espera pelo download
        tempo_max_espera_segundos = 300
        tempo_inicio = time.time()
        download_completo = False
        
        while time.time() - tempo_inicio < tempo_max_espera_segundos:
            arquivo_temporario_existe = any(fname.endswith('.crdownload') for fname in os.listdir(pasta_downloads))
            if os.path.exists(caminho_do_arquivo) and not arquivo_temporario_existe:
                db.logar_progresso(apartamento_id,"-> Download concluído com sucesso!")
                download_completo = True
                break
            time.sleep(5)
            
        if not download_completo:
            raise Exception(f"O download do arquivo não foi concluído em {tempo_max_espera_segundos} segundos.")

        db.logar_progresso(apartamento_id,"ROTEIRO DE COLETA CONCLUÍDO.")
             
    except Exception as e:
        db.logar_progresso(apartamento_id,f"Ocorreu um erro durante a coleta: {e}")
    finally:
        db.logar_progresso(apartamento_id,"Fechando o navegador.")
        driver.quit()