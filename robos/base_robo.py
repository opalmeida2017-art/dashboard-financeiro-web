# robos/base_robo.py

import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def fazer_login(driver, wait, configs):
    """
    Executa a etapa de login no site, usando as configurações lidas.
    """
    URL_LOGIN = configs.get('URL_LOGIN')
    USUARIO = configs.get('USUARIO_ROBO')
    SENHA = configs.get('SENHA_ROBO')
    
    SELECTOR_CAMPO_USUARIO = "input[id='formCad:nome']"
    SELECTOR_CAMPO_SENHA = "input[id='formCad:senha']"
    SELECTOR_BOTAO_ENTRAR = "input[id='formCad:entrar']"

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
    driver.save_screenshot('screenshot_apos_login.png')
    print("Login realizado com sucesso.")