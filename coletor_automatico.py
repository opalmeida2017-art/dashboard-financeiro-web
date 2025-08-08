# coletor_automatico.py (versão final, limpa e organizada)

import os
import time
import logic
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select

def executar_coleta():
    """
    Função principal que executa todo o processo de coleta de dados.
    """
    print("Iniciando a função de coleta...")
    
    # --- AJUSTE CIRÚRGICO NAS VARIÁVEIS DE CONFIGURAÇÃO ---
    print("Lendo configurações do banco de dados...")
    configs = logic.ler_configuracoes_robo()
    USUARIO = configs.get('USUARIO_ROBO')
    SENHA = configs.get('SENHA_ROBO')
    URL_LOGIN = configs.get('URL_LOGIN')
    
    # CORRIGIDO: Adiciona valores padrão para garantir que o robô não quebre se estiverem vazios
    CODIGO_VIAGEM_CLIENTE = configs.get('CODIGO_VIAGENS_CLIENTE', '2') # Usa '2' como padrão
    DATA_INICIAL = configs.get('DATA_INICIAL_ROBO', '01/01/2000')
    DATA_FINAL = configs.get('DATA_FINAL_ROBO', '31/12/2999')
    
    if not all([USUARIO, SENHA, URL_LOGIN]):
        print("ERRO: As configurações de URL, Usuário ou Senha não foram definidas na tela de Configuração.")
        return 
    # --- FIM DO AJUSTE ---

    SELECTOR_CAMPO_USUARIO = "input[id='formCad:nome']"
    SELECTOR_CAMPO_SENHA = "input[id='formCad:senha']"
    SELECTOR_BOTAO_ENTRAR = "input[id='formCad:entrar']"
    
    chrome_options = Options()
    # Para ver o robô em ação, esta linha DEVE estar comentada
    # chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--start-maximized")
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    chrome_options.add_argument(f'user-agent={user_agent}')
    
    pasta_downloads = os.getcwd()
    print(f"Arquivos serão salvos em: {pasta_downloads}")
    prefs = {
        "download.default_directory": pasta_downloads,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
    }
    chrome_options.add_experimental_option('prefs', prefs)
    
    service = Service()
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    wait = WebDriverWait(driver, 30)
    actions = ActionChains(driver)

    try:
        # ... (O resto do seu roteiro de login e cliques, que já está correto) ...
        print(f"Acessando: {URL_LOGIN}")
        driver.get(URL_LOGIN)
        time.sleep(1)

        try:
            limpar_cache_button = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Limpar Cache e Continuar')]")))
            limpar_cache_button.click()
            time.sleep(1)
        except: pass

        try:
            botao_fechar_ajuda = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, "//button[text()='Fechar']")))
            botao_fechar_ajuda.click()
            time.sleep(1)
        except: pass
            
        print("Preenchendo credenciais...")
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, SELECTOR_CAMPO_USUARIO))).send_keys(USUARIO)
        driver.find_element(By.CSS_SELECTOR, SELECTOR_CAMPO_SENHA).send_keys(SENHA)
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, SELECTOR_BOTAO_ENTRAR))).click()
        
        print("Aguardando o login ser processado...")
        time.sleep(1)
        driver.save_screenshot('screenshot_apos_login.png')
        print("Login realizado com sucesso.")
        
        #
        # --- SEU ROTEIRO DE CLIQUES E DOWNLOADS ---
        #
        
        print("Passo 1-2: Acessando 'Cadastro de Exportações'...")
        menu_exp_imp = wait.until(EC.visibility_of_element_located((By.ID, "formMenu:j_idt600")))
        actions.move_to_element(menu_exp_imp).perform()
        time.sleep(1)
        submenu_cadastro = wait.until(EC.element_to_be_clickable((By.ID, "formMenu:j_idt603")))
        submenu_cadastro.click()
        time.sleep(1)
        
        print("Passo 3: Preenchendo código")
        SELECTOR_CAMPO_CODIGO = "input[id='formexpFil:ExpFil_codExp']"
        campo_codigo = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, SELECTOR_CAMPO_CODIGO)))
        campo_codigo.clear()
        campo_codigo.send_keys(CODIGO_VIAGEM_CLIENTE) # Usa a variável lida da config
        time.sleep(1)
        
        print("Passo 4: Pesquisando com Ctrl+Enter...")
        actions.key_down(Keys.CONTROL).send_keys(Keys.ENTER).key_up(Keys.CONTROL).perform()
        time.sleep(1)
        
        print("Passo 5: Clicando em 'VIAGEM CLIENTE'...")
        wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "VIAGEM CLIENTE"))).click()
        time.sleep(1)
        
        # --- PASSO 6 CORRIGIDO: Clicar para abrir a nova aba ---
        print("Passo 6: Clicando em 'Exportar Dados' para abrir a nova aba...")
        
        # Guarda o identificador da aba original
        aba_original = driver.current_window_handle
        
        # Usa o seletor robusto baseado no onclick que você encontrou
        SELECTOR_EXPORTAR_DADOS = "a[onclick*=\"formexp:j_idt820\"]"
        botao_exportar = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, SELECTOR_EXPORTAR_DADOS)))
        botao_exportar.click()
        
        print("Aguardando a nova aba ser aberta...")
        time.sleep(1) # Espera a nova aba carregar

        # Pega a lista de todas as abas abertas
        todas_as_abas = driver.window_handles
        
        # Muda o foco do robô para a última aba da lista (a que acabou de abrir)
        if len(todas_as_abas) > 1:
            driver.switch_to.window(todas_as_abas[-1])
            print(" -> Foco mudado para a nova aba do formulário.")
        else:
            print(" -> AVISO: Nenhuma nova aba foi detectada. O robô continuará na mesma aba.")


        # --- PASSO 7 CORRIGIDO: Removida a lógica de iframe ---
        print("Passo 7: Procurando o link de exportação na página...")
        
        # Procura o link diretamente na página principal, sem entrar em iframes.
        # Usa a técnica mais robusta de executar o JavaScript do onclick.
        SELECTOR_LINK_EXPORTACAO = "a[onclick*=\"formCad:j_idt7\"]"
        
        # 1. Espera até que o link exista no código HTML.
        link_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, SELECTOR_LINK_EXPORTACAO)))
        
        # 2. Pega o conteúdo exato do atributo 'onclick'.
        onclick_script = link_element.get_attribute("onclick")
        
        # 3. Executa o script JavaScript diretamente.
        print(" -> Link encontrado. Executando o script do link...")
        driver.execute_script(onclick_script)
        # --- FIM DA CORREÇÃO ---

        print("Aguardando a próxima tela carregar (nova aba)...")
        time.sleep(1) # Espera a nova aba ser aberta
        
        # --- LÓGICA PARA MUDAR PARA A NOVA ABA ---
        print("Mundando o foco para a nova aba do formulário...")
        todas_as_abas = driver.window_handles
        if len(todas_as_abas) > 1:
            driver.switch_to.window(todas_as_abas[-1])
            print(" -> Foco mudado com sucesso.")
        else:
            print(" -> Aviso: Nenhuma nova aba foi detectada.")
        
    
        print("Passo 8: Preenchendo o formulário final com os valores padrão...")
        
        # Preenche as datas
        wait.until(EC.visibility_of_element_located((By.ID, 'formrelFilViagensCliente:RelFilViagensCliente_dataIniInputDate'))).clear()
        driver.find_element(By.ID, 'formrelFilViagensCliente:RelFilViagensCliente_dataIniInputDate').send_keys(DATA_INICIAL)
        driver.find_element(By.ID, 'formrelFilViagensCliente:RelFilViagensCliente_dataFimInputDate').clear()
        driver.find_element(By.ID, 'formrelFilViagensCliente:RelFilViagensCliente_dataFimInputDate').send_keys(DATA_FINAL)
        
        # Ajusta todos os dropdowns para o valor padrão
        Select(driver.find_element(By.ID, 'formrelFilViagensCliente:RelFilViagensCliente_tipoData')).select_by_value('1')
        Select(driver.find_element(By.ID, 'formrelFilViagensCliente:RelFilViagensCliente_tipoPesoChegada')).select_by_value('0')
        Select(driver.find_element(By.ID, 'formrelFilViagensCliente:RelFilViagensCliente_tipoFrete')).select_by_value('0')
        Select(driver.find_element(By.ID, 'formrelFilViagensCliente:RelFilViagensCliente_pagtoFrete')).select_by_value('T')
        Select(driver.find_element(By.ID, 'formrelFilViagensCliente:RelFilViagensCliente_tipoCte')).select_by_value('T')
        Select(driver.find_element(By.ID, 'formrelFilViagensCliente:RelFilViagensCliente_cteStatus')).select_by_value('0')
        Select(driver.find_element(By.ID, 'formrelFilViagensCliente:RelFilViagensCliente_usaICMSFinal')).select_by_value('S')
        Select(driver.find_element(By.ID, 'formrelFilViagensCliente:RelFilViagensCliente_cancelado')).select_by_value('99')
        Select(driver.find_element(By.ID, 'formrelFilViagensCliente:RelFilViagensCliente_viagemGrupo')).select_by_value('T')
        Select(driver.find_element(By.ID, 'formrelFilViagensCliente:RelFilViagensCliente_mostrarDocAnt')).select_by_value('S')
        Select(driver.find_element(By.ID, 'formrelFilViagensCliente:RelFilViagensCliente_averbado')).select_by_value('T')
        Select(driver.find_element(By.ID, 'formrelFilViagensCliente:RelFilViagensCliente_impPPTEmpMot')).select_by_value('1')
        Select(driver.find_element(By.ID, 'formrelFilViagensCliente:RelFilViagensCliente_impProp')).select_by_value('S')
        Select(driver.find_element(By.ID, 'formrelFilViagensCliente:RelFilViagensCliente_comComplementar')).select_by_value('N')
        Select(driver.find_element(By.ID, 'formrelFilViagensCliente:RelFilViagensCliente_possuiPesoChegada')).select_by_value('T')
        Select(driver.find_element(By.ID, 'formrelFilViagensCliente:RelFilViagensCliente_apenasFaturados')).select_by_value('T')
        Select(driver.find_element(By.ID, 'formrelFilViagensCliente:RelFilViagensCliente_possuiPedido')).select_by_value('T')
        Select(driver.find_element(By.ID, 'formrelFilViagensCliente:RelFilViagensCliente_resumido')).select_by_value('N')
        Select(driver.find_element(By.ID, 'formrelFilViagensCliente:RelFilViagensCliente_somenteQuebra')).select_by_value('T')
        Select(driver.find_element(By.ID, 'formrelFilViagensCliente:RelFilViagensCliente_mostrarMargemFreteConhec')).select_by_value('N')
        
        time.sleep(1)
      
        # --- NOVO PASSO 9 ---
        # Passo 9: Pressionar as teclas Ctrl + Enter para gerar o link
        print("Passo 9: Pressionando Ctrl + Enter para gerar o link de download...")
        actions.key_down(Keys.CONTROL).send_keys(Keys.ENTER).key_up(Keys.CONTROL).perform()
       
       
        print("Passo 10: Clicando no link final para baixar...")
        # A busca pelo link agora é mais paciente e direta
        link_final = wait.until(EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, "Clique aqui para visualizar")))
        link_final.click()
        # Define o nome do arquivo que estamos esperando.
        # Altere esta linha para cada relatório que o robô for baixar.
        nome_do_arquivo_esperado = "relFilViagensCliente.xls"
        
        
        print(f"Download do arquivo '{nome_do_arquivo_esperado}' iniciado!")
        print("Monitorando a pasta para o arquivo completo (espera máxima de 5 minutos)...")
        
        caminho_do_arquivo = os.path.join(pasta_downloads, nome_do_arquivo_esperado)
        tempo_max_espera_segundos = 300 # 5 minutos
        tempo_inicial = time.time()
        download_completo = False

        while time.time() - tempo_inicial < tempo_max_espera_segundos:
            # Verifica se o arquivo final já existe E se não há arquivos temporários do Chrome (.crdownload)
            arquivo_temporario_existe = any(fname.endswith('.crdownload') for fname in os.listdir(pasta_downloads))
            
            if os.path.exists(caminho_do_arquivo) and not arquivo_temporario_existe:
                print("-> Download concluído com sucesso!")
                download_completo = True
                break # Sai do loop de espera
            
            print(" -> Aguardando...")
            time.sleep(5) # Espera 5 segundos antes de verificar novamente

        if not download_completo:
            raise Exception(f"O download do arquivo '{nome_do_arquivo_esperado}' não foi concluído em {tempo_max_espera_segundos} segundos.")
        # --- FIM DA LÓGICA DE ESPERA ---
        
        print("ROTEIRO DE COLETA CONCLUÍDO.")

        # --- Processamento do arquivo ---
        print("\nIniciando o processamento dos arquivos baixados...")
        try:
            logic.processar_downloads_na_pasta() 
        except Exception as e:
            print(f"Ocorreu um erro crítico durante o processamento dos arquivos: {e}")

    except Exception as e:
        driver.save_screenshot('screenshot_erro.png')
        print(f"Ocorreu um erro durante a coleta: {e}")
        print("Um screenshot do erro foi salvo como 'screenshot_erro.png'")

    finally:
        print("Fechando o navegador.")
        driver.quit()

if __name__ == '__main__':
    executar_coleta()