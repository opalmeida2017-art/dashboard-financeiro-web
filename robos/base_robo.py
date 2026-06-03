# robos/base_robo.py (VERSÃO REATORADA E CENTRALIZADA)

import os
import re
import sys
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import database as db


def normalizar_url_login(url: str | None) -> str:
    """Garante https:// — sem isso o Chrome/Selenium retorna 'invalid argument'."""
    u = (url or "").strip()
    if not u:
        return u
    if not re.match(r"^https?://", u, re.I):
        u = "https://" + u.lstrip("/")
    return u


def robo_usar_headless() -> bool:
    """
    .exe / BIWEB Desktop: navegador oculto (headless).
    python app.py (dev): visível, salvo se ROBO_HEADLESS=true no .env.
    """
    flag = os.getenv("ROBO_HEADLESS", "").strip().lower()
    if flag in ("1", "true", "yes", "on"):
        return True
    if flag in ("0", "false", "no", "off"):
        return False
    if getattr(sys, "frozen", False):
        return True
    if os.getenv("BIWEB_DESKTOP", "").strip():
        return True
    return False


def configurar_driver(apartamento_id: int):
    """
    Cria e retorna uma instância configurada do Chrome WebDriver e o caminho da pasta de downloads.
    """
    chrome_options = Options()
    headless = robo_usar_headless()
    if headless:
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-images")
    chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    chrome_options.add_argument("--start-maximized")
    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )
    chrome_options.add_argument(f"user-agent={user_agent}")

    if os.path.exists("/usr/bin/chromium"):
        chrome_options.binary_location = "/usr/bin/chromium"
        caminho_driver = "/usr/bin/chromedriver"
    else:
        caminho_driver = None

    try:
        from biweb_paths import downloads_dir

        pasta_downloads = os.path.abspath(str(downloads_dir(apartamento_id)))
    except Exception:
        pasta_principal = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        pasta_downloads = os.path.abspath(
            os.path.join(pasta_principal, "downloads", str(apartamento_id))
        )
        os.makedirs(pasta_downloads, exist_ok=True)

    prefs = {
        "download.default_directory": pasta_downloads,
        "download.prompt_for_download": False,
    }
    chrome_options.add_experimental_option("prefs", prefs)

    if caminho_driver:
        servico = Service(caminho_driver)
        driver = webdriver.Chrome(service=servico, options=chrome_options)
    else:
        driver = webdriver.Chrome(options=chrome_options)

    driver.set_page_load_timeout(300)
    return driver, pasta_downloads


def fazer_login(driver, wait, configs):
    """Executa a etapa de login no site."""
    URL_LOGIN = normalizar_url_login(configs.get("URL_LOGIN"))
    USUARIO = configs.get("USUARIO_ROBO")
    SENHA = configs.get("SENHA_ROBO")

    if not URL_LOGIN:
        raise ValueError("URL_LOGIN vazia. Salve o link completo em Configurações do Robô.")

    db.logar_progresso(configs["apartamento_id"], f"Acessando: {URL_LOGIN}")
    driver.get(URL_LOGIN)
    time.sleep(1)

    try:
        WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(text(), 'Limpar Cache e Continuar')]")
            )
        ).click()
        time.sleep(1)
    except Exception:
        pass
    try:
        WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//button[text()='Fechar']"))
        ).click()
        time.sleep(1)
    except Exception:
        pass

    db.logar_progresso(configs["apartamento_id"], "Preenchendo credenciais...")
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[id='formCad:nome']"))).send_keys(
        USUARIO
    )
    driver.find_element(By.CSS_SELECTOR, "input[id='formCad:senha']").send_keys(SENHA)
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[id='formCad:entrar']"))).click()
    db.logar_progresso(configs["apartamento_id"], "Login realizado com sucesso.")
    time.sleep(2)


def navegar_para_relatorio(driver, wait, actions, codigo_relatorio, apartamento_id):
    """Navega no menu até a tela do relatório especificado."""
    db.logar_progresso(apartamento_id, "Navegando até 'Cadastro de Exportações'...")
    menu_exp_imp = wait.until(
        EC.visibility_of_element_located(
            (By.XPATH, "//div[contains(@id, '_label') and contains(text(), 'Exp./Imp.')]")
        )
    )
    actions.move_to_element(menu_exp_imp).perform()
    time.sleep(1)

    submenu_cadastro = wait.until(
        EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Cadastro de Exportações')]"))
    )
    submenu_cadastro.click()
    time.sleep(1)

    db.logar_progresso(apartamento_id, f"Pesquisando pelo código de relatório '{codigo_relatorio}'...")
    campo_codigo = wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "input[id='formexpFil:ExpFil_codExp']"))
    )
    campo_codigo.clear()
    campo_codigo.send_keys(codigo_relatorio)
    time.sleep(1)

    actions.key_down(Keys.CONTROL).send_keys(Keys.ENTER).key_up(Keys.CONTROL).perform()
    time.sleep(1)

    link_relatorio = wait.until(
        EC.element_to_be_clickable((By.XPATH, f"//tr[contains(., '{codigo_relatorio}')]//a"))
    )
    link_relatorio.click()
    time.sleep(1)

    db.logar_progresso(apartamento_id, "Acessando a área de exportação de dados...")
    wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Exportar Dados"))).click()
    time.sleep(5)

    todas_as_abas = driver.window_handles
    if len(todas_as_abas) > 1:
        driver.switch_to.window(todas_as_abas[-1])
        db.logar_progresso(apartamento_id, "Foco alterado para a nova aba.")
    else:
        db.logar_progresso(apartamento_id, "Nenhuma nova aba detectada. Procurando por iframe...")
        wait.until(EC.frame_to_be_available_and_switch_to_it(0))
        db.logar_progresso(apartamento_id, "Foco alterado para o iframe.")

    link_element = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "a[onclick*=\"formCad:j_idt7\"]"))
    )
    onclick_script = link_element.get_attribute("onclick")
    driver.execute_script(onclick_script)
    time.sleep(1)
    db.logar_progresso(apartamento_id, "Tela de preenchimento do formulário alcançada.")


def esperar_download_concluir(pasta_downloads, nome_arquivo_esperado, apartamento_id, tempo_max_seg=300):
    """Monitora a pasta de downloads e aguarda a conclusão do arquivo."""
    caminho_do_arquivo = os.path.join(pasta_downloads, nome_arquivo_esperado)
    tempo_inicial = time.time()

    db.logar_progresso(
        apartamento_id, f"Aguardando download do arquivo '{nome_arquivo_esperado}'..."
    )

    while time.time() - tempo_inicial < tempo_max_seg:
        arquivo_temporario_existe = any(
            f.endswith(".crdownload") for f in os.listdir(pasta_downloads)
        )
        if os.path.exists(caminho_do_arquivo) and not arquivo_temporario_existe:
            db.logar_progresso(apartamento_id, "-> Download concluído com sucesso!")
            return True

        time.sleep(5)

    mensagem_erro = (
        f"O download do arquivo '{nome_arquivo_esperado}' não foi concluído em {tempo_max_seg} segundos."
    )
    db.logar_progresso(apartamento_id, mensagem_erro)
    raise Exception(mensagem_erro)


def abrir_menu_exp_imp(driver, wait, actions, apartamento_id):
    """Abre o menu superior Exp./Imp."""
    db.logar_progresso(apartamento_id, "Abrindo menu Exp./Imp....")
    menu_exp = wait.until(
        EC.visibility_of_element_located(
            (By.XPATH, "//div[contains(@id, '_label') and contains(normalize-space(), 'Exp./Imp.')]")
        )
    )
    actions.move_to_element(menu_exp).perform()
    time.sleep(0.8)
    return menu_exp


def _abrir_menu_configuracoes(driver, wait, actions, apartamento_id):
    """Menu superior SATI: Configurações (formMenu:j_idt711)."""
    db.logar_progresso(apartamento_id, "Abrindo menu Configurações…")
    candidatos = [
        (By.ID, "formMenu:j_idt711_label"),
        (By.ID, "formMenu:j_idt711"),
        (
            By.XPATH,
            "//div[contains(@class,'rf-ddm-lbl')][.//div[normalize-space()='Configurações']]",
        ),
        (
            By.XPATH,
            "//div[contains(@class,'rf-ddm-lbl-dec') and normalize-space()='Configurações']",
        ),
    ]
    menu = None
    for by, sel in candidatos:
        try:
            menu = wait.until(EC.visibility_of_element_located((by, sel)))
            break
        except Exception:
            continue
    if menu is None:
        raise RuntimeError("Menu 'Configurações' não encontrado na barra do SATI.")

    actions.move_to_element(menu).perform()
    time.sleep(1)
    try:
        wait.until(EC.visibility_of_element_located((By.ID, "formMenu:j_idt711_list")))
    except Exception:
        menu.click()
        time.sleep(1)
    return menu


def navegar_envio_banco_dados(driver, wait, actions, apartamento_id):
    """Menu Configurações → Envio de Banco de Dados (formMenu:j_idt747 → formCad:enviarDadosBI)."""
    _abrir_menu_configuracoes(driver, wait, actions, apartamento_id)

    envio_selectors = [
        (By.ID, "formMenu:j_idt747"),
        (By.CSS_SELECTOR, "[id='formMenu:j_idt747']"),
        (By.XPATH, "//div[contains(@class,'rf-ddm-itm')][@id='formMenu:j_idt747']"),
        (
            By.XPATH,
            "//span[contains(@class,'rf-ddm-itm-lbl') and "
            "contains(normalize-space(),'Envio de Banco de Dados')]",
        ),
        (
            By.XPATH,
            "//span[contains(@class,'rf-ddm-itm-lbl') and contains(.,'Envio de Banco')]",
        ),
    ]

    envio = None
    for by, sel in envio_selectors:
        try:
            envio = WebDriverWait(driver, 8).until(EC.element_to_be_clickable((by, sel)))
            break
        except Exception:
            continue

    if envio is None:
        raise RuntimeError(
            "Item 'Envio de Banco de Dados' não encontrado dentro de Configurações."
        )

    db.logar_progresso(apartamento_id, "Clicando em Envio de Banco de Dados…")
    try:
        envio.click()
    except Exception:
        driver.execute_script("arguments[0].click();", envio)

    time.sleep(2)
    wait.until(EC.presence_of_element_located((By.ID, "formCad:enviarDadosBI")))
    db.logar_progresso(apartamento_id, "Tela 'Envio de Banco de Dados' aberta.")


def executar_envio_banco_bi(driver, wait, apartamento_id, tempo_max_seg=3600):
    """Seleciona Sim, envia e aguarda 'Processo concluído'. Retorna URL do .zip."""
    from selenium.webdriver.support.ui import Select

    db.logar_progresso(apartamento_id, "Configurando envio de dados para BI = Sim…")
    Select(driver.find_element(By.ID, "formCad:enviarDadosBI")).select_by_value("S")

    btn_enviar = wait.until(EC.element_to_be_clickable((By.ID, "formCad:enviar")))
    btn_enviar.click()
    db.logar_progresso(apartamento_id, "Envio iniciado. Aguardando processamento…")

    tempo_ini = time.time()
    while time.time() - tempo_ini < tempo_max_seg:
        try:
            fin = driver.find_element(By.ID, "formCad:pb.fin")
            if fin.is_displayed() and "conclu" in (fin.text or "").lower():
                db.logar_progresso(apartamento_id, "Processo concluído no SATI.")
                break
        except Exception:
            pass
        time.sleep(3)
    else:
        raise TimeoutError(
            f"Tempo esgotado ({tempo_max_seg}s) aguardando conclusão do envio BI."
        )

    url = extrair_url_zip_da_pagina(driver)
    if not url:
        raise RuntimeError("URL do arquivo SATI-c3332-atual.zip não encontrada na página.")
    db.logar_progresso(apartamento_id, f"Link do backup: {url}")
    return url


def _primeira_url_zip(texto: str) -> str | None:
    """Extrai uma única URL .zip (evita duplicar link colado duas vezes no HTML)."""
    m = re.search(
        r"(https?://[^\s\"'<>]+?\.zip)",
        texto or "",
        re.IGNORECASE,
    )
    return m.group(1) if m else None


def extrair_url_zip_da_pagina(driver) -> str | None:
    for el in driver.find_elements(
        By.XPATH,
        "//span[contains(@style,'#0000FF') and contains(.,'.zip')]"
        " | //span[contains(.,'SATI') and contains(.,'.zip')]"
        " | //a[contains(@href,'.zip')]",
    ):
        texto = (el.text or "") + (el.get_attribute("href") or "")
        url = _primeira_url_zip(texto)
        if url:
            return url
    for el in driver.find_elements(
        By.XPATH, "//*[contains(text(),'.zip') and contains(text(),'SATI')]"
    ):
        url = _primeira_url_zip(el.text or "")
        if url:
            return url
    return extrair_url_zip_do_html(driver.page_source)


def extrair_url_zip_do_html(html: str) -> str | None:
    return _primeira_url_zip(html)


def clicar_link_download_zip(
    driver, wait, apartamento_id: int, pasta_downloads: str, nome_arquivo: str
) -> bool:
    """Clica no link azul do .zip na tela de conclusão e aguarda o arquivo na pasta."""
    db.logar_progresso(apartamento_id, "Clicando no link de download do backup…")
    xpaths = [
        "//span[contains(@style,'#0000FF') and contains(.,'.zip')]",
        "//span[contains(.,'SATI-c3332') and contains(.,'.zip')]",
        "//span[contains(.,'SATI') and contains(.,'.zip')]",
        "//a[contains(@href,'.zip')]",
        "//*[contains(text(),'SATI') and contains(text(),'.zip')]",
    ]
    for xpath in xpaths:
        try:
            el = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, xpath)))
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
            time.sleep(0.5)
            try:
                el.click()
            except Exception:
                driver.execute_script("arguments[0].click();", el)
            time.sleep(1)
            return esperar_download_concluir(
                pasta_downloads, nome_arquivo, apartamento_id, tempo_max_seg=180
            )
        except Exception:
            continue
    db.logar_progresso(
        apartamento_id,
        "Link clicável não encontrado na página; tentando download por HTTP…",
    )
    return False


def baixar_zip_sati(
    driver,
    wait,
    url: str,
    pasta_destino: str,
    nome_arquivo: str,
    apartamento_id: int,
) -> str:
    """Tenta clique no link da página; se falhar, baixa via cookies HTTP."""
    os.makedirs(pasta_destino, exist_ok=True)
    destino = os.path.join(pasta_destino, nome_arquivo)

    if clicar_link_download_zip(driver, wait, apartamento_id, pasta_destino, nome_arquivo):
        return destino

    if os.path.isfile(destino):
        return destino

    return baixar_arquivo_com_sessao(driver, url, pasta_destino, nome_arquivo, apartamento_id)


def baixar_arquivo_com_sessao(driver, url: str, pasta_destino: str, nome_arquivo: str, apartamento_id):
    """Baixa o .zip usando os cookies da sessão Selenium."""
    os.makedirs(pasta_destino, exist_ok=True)
    destino = os.path.join(pasta_destino, nome_arquivo)

    sess = requests.Session()
    for ck in driver.get_cookies():
        sess.cookies.set(ck["name"], ck["value"], domain=ck.get("domain"))

    db.logar_progresso(apartamento_id, f"Baixando {nome_arquivo}…")
    resp = sess.get(url, stream=True, timeout=600)
    resp.raise_for_status()

    with open(destino, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 256):
            if chunk:
                f.write(chunk)

    db.logar_progresso(apartamento_id, f"Download salvo em {destino}")
    return destino
