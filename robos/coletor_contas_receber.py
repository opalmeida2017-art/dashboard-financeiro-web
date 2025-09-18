# robos/coletor_contas_receber.py

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import logic
import config
import database as db 
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select

# CORREÇÃO: Removido o aninhamento de funções. Esta é agora a função principal.
def executar_coleta_contas_receber(apartamento_id: int):
    db.logar_progresso(apartamento_id,f"\n--- INICIANDO ROBÔ: CONTAS A RECEBER PENDENTES PARA TRANSPORTADORA ID: {apartamento_id} ---")
    
    # --- Configuração Inicial ---
    print("Lendo configurações do banco de dados...")
    configs = logic.ler_configuracoes_robo(apartamento_id)
    USUARIO = configs.get('USUARIO_ROBO')
    SENHA = configs.get('SENHA_ROBO')
    URL_LOGIN = configs.get('URL_LOGIN')
    CODIGO_RELATORIO = configs.get('CODIGO_CONTAS_RECEBER', '6') 
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
    chrome_options.add_argument("--headless") 
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

    # 2. Inicializar o Driver (O Selenium Manager cuida do resto)
    # Não precisamos mais do 'service' ou do 'binary_location'
    driver = webdriver.Chrome(options=chrome_options)

    # 3. Definir os tempos de espera
    wait = WebDriverWait(driver, 300)
    driver.set_page_load_timeout(300)
    actions = ActionChains(driver)

# --- FIM DA CORREÇÃO ---

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
            wait.until(EC.frame_to_be_available_and_switch_to_it(2))

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
        wait.until(EC.visibility_of_element_located((By.ID, 'formrelFilContasReceber:RelFilContasReceber_dataIniInputDate'))).clear()
        driver.find_element(By.ID, 'formrelFilContasReceber:RelFilContasReceber_dataIniInputDate').send_keys(DATA_INICIAL)
        driver.find_element(By.ID, 'formrelFilContasReceber:RelFilContasReceber_dataFimInputDate').clear()
        driver.find_element(By.ID, 'formrelFilContasReceber:RelFilContasReceber_dataFimInputDate').send_keys(DATA_FINAL)
        
        # Preenche os dropdowns (seletores)
        Select(driver.find_element(By.ID, 'formrelFilContasReceber:RelFilContasReceber_dupLiberadas')).select_by_value('T')
        Select(driver.find_element(By.ID, 'formrelFilContasReceber:RelFilContasReceber_imprimirCte')).select_by_value('S')
        Select(driver.find_element(By.ID, 'formrelFilContasReceber:RelFilContasReceber_tipoContaCorr')).select_by_value('9')
        Select(driver.find_element(By.ID, 'formrelFilContasReceber:RelFilContasReceber_imprimirTipoFrete')).select_by_value('S')
        Select(driver.find_element(By.ID, 'formrelFilContasReceber:RelFilContasReceber_descontadasFomento')).select_by_value('T')

        time.sleep(1)
        db.logar_progresso(apartamento_id,"Passo 9: Pressionando Ctrl + Enter para gerar o link de download...")
        actions.key_down(Keys.CONTROL).send_keys(Keys.ENTER).key_up(Keys.CONTROL).perform()
        time.sleep(1)
        
        db.logar_progresso(apartamento_id,"Passo 10: Clicando no link final para baixar...")
        link_final = wait.until(EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, "Clique aqui para visualizar")))
        link_final.click()
        
        # ATENÇÃO: Verifique se este é o nome correto do arquivo para este robô!
        nome_do_arquivo_esperado = "relFilContasReceber.xls"
        caminho_do_arquivo = os.path.join(pasta_downloads, nome_do_arquivo_esperado)
        
        db.logar_progresso(apartamento_id,f"Download do arquivo '{nome_do_arquivo_esperado}' iniciado!")
        db.logar_progresso(apartamento_id,"Monitorando a pasta para o arquivo completo (espera máxima de 5 minutos)...")
        
        tempo_max_espera_segundos = 300
        tempo_inicial = time.time()
        download_completo = False
        
               
        while time.time() - tempo_inicial < tempo_max_espera_segundos:
                # Verifica se ainda existe um arquivo de download temporário do Chrome
            arquivo_temporario_existe = any(fname.endswith('.crdownload') for fname in os.listdir(pasta_downloads))
            
            # A condição de sucesso agora é: o arquivo final existe E o arquivo temporário NÃO existe mais.
            if os.path.exists(caminho_do_arquivo) and not arquivo_temporario_existe:
                db.logar_progresso(apartamento_id,"-> Download concluído com sucesso!")
                download_completo = True
                break # O 'break' agora está DENTRO do 'if'
        
            # A pausa agora está DENTRO do 'while'
            db.logar_progresso(apartamento_id," -> Aguardando download...")
            time.sleep(5) # Espera 5 segundos antes de verificar novamente
            
        if not download_completo:
            # A lógica de erro continua a mesma, mas agora só será chamada se o tempo realmente esgotar.
            mensagem_erro = f"O download do arquivo '{nome_do_arquivo_esperado}' não foi concluído em {tempo_max_espera_segundos} segundos."
            db.logar_progresso(apartamento_id, mensagem_erro)
            raise Exception(mensagem_erro)

        
        db.logar_progresso(apartamento_id,"ROTEIRO DE COLETA CONCLUÍDO.")
             
    except Exception as e:
        db.logar_progresso(apartamento_id,f"Ocorreu um erro durante a coleta: {e}")
        db.logar_progresso(apartamento_id,"Um screenshot do erro foi salvo como 'screenshot_erro.png'")
    finally:
        db.logar_progresso(apartamento_id,"Fechando o navegador.")
        driver.quit() 
                  
        
# --- BLOCO PARA TESTE MANUAL ---
if __name__ == '__main__':
    if len(sys.argv) > 1:
        apartamento_id_teste = int(sys.argv[1])
        # CORREÇÃO ESTRUTURAL: Chamando a função correta
        # --- ALTERADO ---
        executar_coleta_contas_receber(apartamento_id_teste)
    else:
        # --- ALTERADO ---
        print("Para testar, forneça um ID de apartamento. Ex: python robos/coletor_contas_receber.py 1")