# robos/coletor_fat_viagens.py (Robô completo e independente)

# --- Adiciona a pasta principal ao caminho para encontrar os outros módulos ---
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# --- Fim da adição ---

import time
import logic
import config
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select


def executar_coleta_fat_viagens(apartamento_id: int):
    print(f"\n--- INICIANDO ROBÔ: FAT VIAGENS PARA APARTAMENTO ID: {apartamento_id} ---")
    
    # --- Configuração Inicial ---
    print("Lendo configurações do banco de dados...")
    # MODIFICADO: Lê as configurações para o apartamento específico
    configs = logic.ler_configuracoes_robo(apartamento_id)
    USUARIO = configs.get('USUARIO_ROBO')
    SENHA = configs.get('SENHA_ROBO')
    URL_LOGIN = configs.get('URL_LOGIN')
    # Usa o código para "Fat.Viagens por Cliente"
    CODIGO_RELATORIO = configs.get('CODIGO_VIAGENS_FAT_CLIENTE', '5') 
    DATA_INICIAL = configs.get('DATA_INICIAL_ROBO', '01/01/2000')
    DATA_FINAL = configs.get('DATA_FINAL_ROBO', '31/12/2999')
    
    if not all([USUARIO, SENHA, URL_LOGIN]):
        print("ERRO: As configurações de URL, Usuário ou Senha não foram definidas.")
        return 
        
    SELECTOR_CAMPO_USUARIO = "input[id='formCad:nome']"
    SELECTOR_CAMPO_SENHA = "input[id='formCad:senha']"
    SELECTOR_BOTAO_ENTRAR = "input[id='formCad:entrar']"
    
    chrome_options = Options()
    # Para ver o robô em ação, esta linha DEVE estar comentada
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--start-maximized")
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    chrome_options.add_argument(f'user-agent={user_agent}')
    
    pasta_principal = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    prefs = {'download.default_directory': pasta_principal}
    chrome_options.add_experimental_option('prefs', prefs)
    
    service = Service()
    driver = webdriver.Chrome(service=service, options=chrome_options)
    wait = WebDriverWait(driver, 30)
    actions = ActionChains(driver)

    try:
        # --- ETAPA DE LOGIN ---
        print(f"Acessando: {URL_LOGIN}")
        driver.get(URL_LOGIN)
        time.sleep(2)
        try:
            WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Limpar Cache e Continuar')]"))).click()
            time.sleep(3)
        except: pass
        try:
            WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, "//button[text()='Fechar']"))).click()
            time.sleep(2)
        except: pass
        
        print("Preenchendo credenciais...")
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, SELECTOR_CAMPO_USUARIO))).send_keys(USUARIO)
        driver.find_element(By.CSS_SELECTOR, SELECTOR_CAMPO_SENHA).send_keys(SENHA)
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, SELECTOR_BOTAO_ENTRAR))).click()
        print("Aguardando login...")
        time.sleep(7)
        
        # --- ROTEIRO DE CLIQUES E DOWNLOADS ---
        print("Passo 1-2: Acessando 'Cadastro de Exportações'...")
        menu_exp_imp = wait.until(EC.visibility_of_element_located((By.ID, "formMenu:j_idt600")))
        actions.move_to_element(menu_exp_imp).perform()
        time.sleep(1)
        submenu_cadastro = wait.until(EC.element_to_be_clickable((By.ID, "formMenu:j_idt603")))
        submenu_cadastro.click()
        time.sleep(3)
        
        print(f"Passo 3: Preenchendo código '{CODIGO_RELATORIO}'...")
        SELECTOR_CAMPO_CODIGO = "input[id='formexpFil:ExpFil_codExp']"
        campo_codigo = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, SELECTOR_CAMPO_CODIGO)))
        campo_codigo.clear()
        campo_codigo.send_keys(CODIGO_RELATORIO)
        time.sleep(1)
        
        print("Passo 4: Pesquisando com Ctrl+Enter...")
        actions.key_down(Keys.CONTROL).send_keys(Keys.ENTER).key_up(Keys.CONTROL).perform()
        time.sleep(5)
        
         # --- PASSO 5 CORRIGIDO: Clicando pelo Código ---
        print(f"Passo 5: Procurando o link do relatório com código '{CODIGO_RELATORIO}'...")
        # Este seletor XPath encontra a linha (tr) que contém uma célula (td) com o código exato
        # e depois encontra o link (a) dentro dessa mesma linha.
        seletor_link_relatorio = f"//tr[contains(., '{CODIGO_RELATORIO}')]//a"
        link_relatorio = wait.until(EC.element_to_be_clickable((By.XPATH, seletor_link_relatorio)))
        link_relatorio.click()
        # --- FIM DA CORREÇÃO ---
        time.sleep(1)
         # --- PASSO 6 CORRIGIDO: Clicar para abrir a nova aba ---
        print("Passo 6: Clicando em 'Exportar Dados' para abrir a nova aba...")
        
        # Guarda o identificador da aba original para podermos voltar depois
        aba_original = driver.current_window_handle
        
        # Clica no botão "Exportar Dados"
        wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Exportar Dados"))).click()
        
        print("Aguardando a nova aba ser aberta...")
        time.sleep(1) # Espera a nova aba carregar

        # Pega a lista de todas as abas abertas
        todas_as_abas = driver.window_handles
        
        # Muda o foco do robô para a última aba da lista (a que acabou de abrir)
        if len(todas_as_abas) > 1:
            driver.switch_to.window(todas_as_abas[-1])
            print(" -> Foco mudado para a nova aba do formulário.")
        else:
            # Se não abrir uma nova aba, o pop-up deve ser um iframe
            print(" -> Nenhuma nova aba detectada. Procurando por um iframe...")
            wait.until(EC.frame_to_be_available_and_switch_to_it(0))

        # --- PASSO 7 CORRIGIDO: Clicar no link dentro da nova aba/iframe ---
        print("Passo 7: Procurando e clicando no link de exportação...")
        
        # Usa a técnica mais robusta de executar o JavaScript do onclick
        SELECTOR_LINK_EXPORTACAO = "a[onclick*=\"formCad:j_idt7\"]"
        
        link_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, SELECTOR_LINK_EXPORTACAO)))
        onclick_script = link_element.get_attribute("onclick")
        
        print(" -> Link encontrado. Executando o script do link...")
        driver.execute_script(onclick_script)
        # --- FIM DA CORREÇÃO ---

        print("Aguardando a próxima tela carregar...")
        time.sleep(1)
        
        # A lógica para mudar para a SEGUNDA nova aba (se houver) iria aqui
        
        driver.save_screenshot('screenshot_formulario_final.png')
        print("-> Tela do formulário final alcançada! Um screenshot foi salvo.")

        #
        # --- O PRÓXIMO PASSO SERÁ PREENCHER O FORMULÁRIO FINAL ---
            
        print("Passo 8: Preenchendo o formulário de Faturamento de Viagens...")
        
        # Preenche as datas
        wait.until(EC.visibility_of_element_located((By.ID, 'formrelFilViagensFatCliente:RelFilViagensFatCliente_dataIniInputDate'))).clear()
        driver.find_element(By.ID, 'formrelFilViagensFatCliente:RelFilViagensFatCliente_dataIniInputDate').send_keys(DATA_INICIAL)
        driver.find_element(By.ID, 'formrelFilViagensFatCliente:RelFilViagensFatCliente_dataFimInputDate').clear()
        driver.find_element(By.ID, 'formrelFilViagensFatCliente:RelFilViagensFatCliente_dataFimInputDate').send_keys(DATA_FINAL)
        
        # Preenche os dropdowns e campos com os valores padrão
        Select(driver.find_element(By.ID, 'formrelFilViagensFatCliente:RelFilViagensFatCliente_tipoData')).select_by_value('1')
        Select(driver.find_element(By.ID, 'formrelFilViagensFatCliente:RelFilViagensFatCliente_faturamento')).select_by_value('0')
        driver.find_element(By.ID, 'formrelFilViagensFatCliente:RelFilViagensFatCliente_tipoCte2').clear()
        driver.find_element(By.ID, 'formrelFilViagensFatCliente:RelFilViagensFatCliente_tipoCte2').send_keys('T')
        Select(driver.find_element(By.ID, 'formrelFilViagensFatCliente:RelFilViagensFatCliente_cteStatus')).select_by_value('0')
        Select(driver.find_element(By.ID, 'formrelFilViagensFatCliente:RelFilViagensFatCliente_tipoFilial')).select_by_value('0')
        Select(driver.find_element(By.ID, 'formrelFilViagensFatCliente:RelFilViagensFatCliente_tipoFrete')).select_by_value('0')
        Select(driver.find_element(By.ID, 'formrelFilViagensFatCliente:RelFilViagensFatCliente_fretePago')).select_by_value('T')
        Select(driver.find_element(By.ID, 'formrelFilViagensFatCliente:RelFilViagensFatCliente_temAcertoProprietario')).select_by_value('T')
        Select(driver.find_element(By.ID, 'formrelFilViagensFatCliente:RelFilViagensFatCliente_pesoChegada')).select_by_value('0')
        Select(driver.find_element(By.ID, 'formrelFilViagensFatCliente:RelFilViagensFatCliente_apenasFaturados')).select_by_value('N')
        Select(driver.find_element(By.ID, 'formrelFilViagensFatCliente:RelFilViagensFatCliente_somentePedidosNaoFinalizados')).select_by_value('0')
        
        time.sleep(1)
        # --- PASSO 9 CORRIGIDO: Gerar o link de download ---
        print("Passo 9: Pressionando Ctrl + Enter para gerar o link de download...")
        actions.key_down(Keys.CONTROL).send_keys(Keys.ENTER).key_up(Keys.CONTROL).perform()
        time.sleep(5) # Espera o link aparecer na tela
        
        print("Passo 10: Clicando no link final para baixar...")
        # ... (código do clique final de download) ...
        link_final = wait.until(EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, "Clique aqui para visualizar")))
        link_final.click()
        
        # --- LÓGICA DE ESPERA INTELIGENTE PELO ARQUIVO ---
        nome_do_arquivo_esperado = "relFilViagensFatCliente.xls"
        pasta_downloads = pasta_principal  # Define pasta_downloads corretamente
        caminho_do_arquivo = os.path.join(pasta_downloads, nome_do_arquivo_esperado)
        
        print(f"Download do arquivo '{nome_do_arquivo_esperado}' iniciado!")
        print("Monitorando a pasta para o arquivo completo (espera máxima de 5 minutos)...")
        
        tempo_max_espera_segundos = 300 # 5 minutos
        tempo_inicial = time.time()
        download_completo = False
        
        while time.time() - tempo_inicial < tempo_max_espera_segundos:
            # Verifica se o arquivo final já existe E se não há mais arquivos temporários do Chrome
            arquivo_temporario_existe = any(fname.endswith('.crdownload') for fname in os.listdir(pasta_downloads))
            
            if os.path.exists(caminho_do_arquivo) and not arquivo_temporario_existe:
                print("-> Download concluído com sucesso!")
                download_completo = True
                break # Sai do loop de espera
            
            print(" -> Aguardando download...")
            time.sleep(1) # Espera 5 segundos antes de verificar novamente
        
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

# Bloco para permitir que este arquivo seja executado sozinho para testes
if __name__ == '__main__':
    if len(sys.argv) > 1:
        apartamento_id_arg = int(sys.argv[1])
        executar_coleta_fat_viagens(apartamento_id_arg)
    else:
        print("Erro: ID do apartamento não fornecido.")