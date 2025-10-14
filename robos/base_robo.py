# robos/base_robo.py (VERSÃO REATORADA E CENTRALIZADA)

import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import database as db

def configurar_driver(apartamento_id: int):
    """
    Cria e retorna uma instância configurada do Chrome WebDriver e o caminho da pasta de downloads.
    """
    chrome_options = Options()
    # Descomente a linha abaixo para rodar em modo "visível" durante o desenvolvimento
    #chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-images")
    chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    chrome_options.add_argument("--start-maximized")
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    chrome_options.add_argument(f'user-agent={user_agent}')
    
    # Define o caminho absoluto para a pasta de downloads
    pasta_principal = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pasta_downloads = os.path.join(pasta_principal, 'downloads', str(apartamento_id))
    os.makedirs(pasta_downloads, exist_ok=True)
    
    prefs = {'download.default_directory': pasta_downloads}
    chrome_options.add_experimental_option('prefs', prefs)
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_page_load_timeout(300)
    return driver, pasta_downloads

def fazer_login(driver, wait, configs):
    """Executa a etapa de login no site."""
    URL_LOGIN = configs.get('URL_LOGIN')
    USUARIO = configs.get('USUARIO_ROBO')
    SENHA = configs.get('SENHA_ROBO')
    
    db.logar_progresso(configs['apartamento_id'], f"Acessando: {URL_LOGIN}")
    driver.get(URL_LOGIN)
    time.sleep(1)
    
    # Lida com pop-ups comuns
    try:
        WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Limpar Cache e Continuar')]"))).click()
        time.sleep(1)
    except: pass
    try:
        WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, "//button[text()='Fechar']"))).click()
        time.sleep(1)
    except: pass
        
    db.logar_progresso(configs['apartamento_id'], "Preenchendo credenciais...")
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[id='formCad:nome']"))).send_keys(USUARIO)
    driver.find_element(By.CSS_SELECTOR, "input[id='formCad:senha']").send_keys(SENHA)
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[id='formCad:entrar']"))).click()
    db.logar_progresso(configs['apartamento_id'], "Login realizado com sucesso.")
    time.sleep(2)

def navegar_para_relatorio(driver, wait, actions, codigo_relatorio, apartamento_id):
    """Navega no menu até a tela do relatório especificado."""
    db.logar_progresso(apartamento_id, "Navegando até 'Cadastro de Exportações'...")
    menu_exp_imp = wait.until(EC.visibility_of_element_located((By.XPATH, "//div[contains(@id, '_label') and contains(text(), 'Exp./Imp.')]")))
    actions.move_to_element(menu_exp_imp).perform()
    time.sleep(1)
    
    submenu_cadastro = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Cadastro de Exportações')]")))
    submenu_cadastro.click()
    time.sleep(1)
    
    db.logar_progresso(apartamento_id, f"Pesquisando pelo código de relatório '{codigo_relatorio}'...")
    campo_codigo = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[id='formexpFil:ExpFil_codExp']")))
    campo_codigo.clear()
    campo_codigo.send_keys(codigo_relatorio)
    time.sleep(1)
    
    actions.key_down(Keys.CONTROL).send_keys(Keys.ENTER).key_up(Keys.CONTROL).perform()
    time.sleep(1)
    
    link_relatorio = wait.until(EC.element_to_be_clickable((By.XPATH, f"//tr[contains(., '{codigo_relatorio}')]//a")))
    link_relatorio.click()
    time.sleep(1)
    
    db.logar_progresso(apartamento_id, "Acessando a área de exportação de dados...")
    wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Exportar Dados"))).click()
    time.sleep(5)

    # Lógica para mudar para nova aba ou iframe
    todas_as_abas = driver.window_handles
    if len(todas_as_abas) > 1:
        driver.switch_to.window(todas_as_abas[-1])
        db.logar_progresso(apartamento_id, "Foco alterado para a nova aba.")
    else:
        db.logar_progresso(apartamento_id, "Nenhuma nova aba detectada. Procurando por iframe...")
        wait.until(EC.frame_to_be_available_and_switch_to_it(0))
        db.logar_progresso(apartamento_id, "Foco alterado para o iframe.")
        
    link_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[onclick*=\"formCad:j_idt7\"]")))
    onclick_script = link_element.get_attribute("onclick")
    driver.execute_script(onclick_script)
    time.sleep(1)
    db.logar_progresso(apartamento_id, "Tela de preenchimento do formulário alcançada.")

def esperar_download_concluir(pasta_downloads, nome_arquivo_esperado, apartamento_id, tempo_max_seg=300):
    """Monitora a pasta de downloads e aguarda a conclusão do arquivo."""
    caminho_do_arquivo = os.path.join(pasta_downloads, nome_arquivo_esperado)
    tempo_inicial = time.time()
    
    db.logar_progresso(apartamento_id, f"Aguardando download do arquivo '{nome_arquivo_esperado}'...")
    
    while time.time() - tempo_inicial < tempo_max_seg:
        arquivo_temporario_existe = any(f.endswith('.crdownload') for f in os.listdir(pasta_downloads))
        if os.path.exists(caminho_do_arquivo) and not arquivo_temporario_existe:
            db.logar_progresso(apartamento_id, "-> Download concluído com sucesso!")
            return True
        
        time.sleep(5)
        
    mensagem_erro = f"O download do arquivo '{nome_arquivo_esperado}' não foi concluído em {tempo_max_seg} segundos."
    db.logar_progresso(apartamento_id, mensagem_erro)
    raise Exception(mensagem_erro)