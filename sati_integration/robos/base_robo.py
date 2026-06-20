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
from app.data import database as db


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
    Servidor Linux sem DISPLAY: headless automático (evita session not created).
    Dev Windows: visível, salvo ROBO_HEADLESS=true no .env.
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
    if sys.platform.startswith("linux") and not os.getenv("DISPLAY", "").strip():
        return True
    return False


def _resolver_chrome_binario_e_driver():
    """Chrome/Chromium no Linux (Render, Debian, Google Chrome instalado)."""
    candidatos_bin = (
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/opt/google/chrome/chrome",
    )
    candidatos_drv = (
        "/usr/bin/chromedriver",
        "/usr/lib/chromium/chromedriver",
        "/usr/lib/chromium-browser/chromedriver",
    )
    binary = next((p for p in candidatos_bin if os.path.isfile(p)), None)
    driver_path = next((p for p in candidatos_drv if os.path.isfile(p)), None)
    return binary, driver_path


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
    chrome_options.page_load_strategy = "eager"
    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )
    chrome_options.add_argument(f"user-agent={user_agent}")
    if headless:
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--remote-debugging-port=0")

    chrome_bin, caminho_driver = _resolver_chrome_binario_e_driver()
    if chrome_bin:
        chrome_options.binary_location = chrome_bin

    try:
        from app.utils.paths import downloads_dir

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

    try:
        if caminho_driver:
            servico = Service(caminho_driver)
            driver = webdriver.Chrome(service=servico, options=chrome_options)
        else:
            driver = webdriver.Chrome(options=chrome_options)
    except Exception as e:
        raise RuntimeError(
            f"Falha ao iniciar Chrome (bin={chrome_bin or 'auto'}, "
            f"driver={caminho_driver or 'selenium-manager'}, headless={headless}): {e}"
        ) from e

    driver.set_page_load_timeout(180)
    driver.set_script_timeout(90)
    try:
        driver.command_executor.set_timeout(300)
    except Exception:
        pass
    _configurar_pasta_download_chrome(driver, pasta_downloads)
    return driver, pasta_downloads


def _configurar_pasta_download_chrome(driver, pasta_downloads: str) -> None:
    """CDP: força downloads na pasta do apartamento."""
    pasta = os.path.abspath(pasta_downloads)
    try:
        driver.execute_cdp_cmd(
            "Page.setDownloadBehavior",
            {"behavior": "allow", "downloadPath": pasta},
        )
    except Exception:
        try:
            driver.execute_cdp_cmd(
                "Browser.setDownloadBehavior",
                {"behavior": "allow", "downloadPath": pasta, "eventsEnabled": True},
            )
        except Exception:
            pass


def _tela_principal_sati_visivel(driver) -> bool:
    for by, sel in (
        (By.ID, "formMenu"),
        (By.CSS_SELECTOR, "[id^='formMenu']"),
        (By.XPATH, "//div[contains(@class,'rf-ddm-lbl-dec')]"),
        (By.XPATH, "//td[contains(@id,'formMenu:')]"),
    ):
        try:
            if any(e.is_displayed() for e in driver.find_elements(by, sel)):
                return True
        except Exception:
            pass
    return False


def _tentar_clicar_continuar_login_sitesat(driver, apartamento_id: int) -> bool:
    """Uma tentativa de clicar no popup 'Continuar Login no SiteSAT'."""
    seletores = [
        (By.ID, "formCad:continuarpopup"),
        (By.CSS_SELECTOR, "input[id='formCad:continuarpopup']"),
        (By.NAME, "formCad:continuarpopup"),
        (
            By.XPATH,
            "//input[@type='submit' and contains(@value, 'Continuar Login no SiteSAT')]",
        ),
    ]
    for by, sel in seletores:
        try:
            for el in driver.find_elements(by, sel):
                if el.is_displayed() and el.is_enabled():
                    db.logar_progresso(
                        apartamento_id,
                        "Clicando em 'Continuar Login no SiteSAT'…",
                    )
                    el.click()
                    time.sleep(1)
                    return True
        except Exception:
            pass
    return False


def _clicar_continuar_login_sitesat(driver, apartamento_id: int, timeout: int = 15) -> bool:
    """SATI pode exibir popup intermediário após clicar em Entrar."""
    fim = time.time() + timeout
    while time.time() < fim:
        if _tela_principal_sati_visivel(driver):
            return False
        if _tentar_clicar_continuar_login_sitesat(driver, apartamento_id):
            return True
        time.sleep(0.4)
    return False


def _aguardar_tela_principal_pos_login(driver, apartamento_id: int, timeout: int = 75) -> None:
    """Evita travar no urllib sem feedback após clicar em Entrar."""
    db.logar_progresso(apartamento_id, "Aguardando tela principal do SATI após login…")
    fim = time.time() + timeout
    while time.time() < fim:
        if _tela_principal_sati_visivel(driver):
            db.logar_progresso(apartamento_id, "Tela principal SATI detectada.")
            time.sleep(1)
            return
        _tentar_clicar_continuar_login_sitesat(driver, apartamento_id)
        time.sleep(0.8)
    raise TimeoutError(
        f"SATI não exibiu o menu principal em {timeout}s após o login. "
        "Verifique usuário/senha ou lentidão do site."
    )


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

    apt_id = configs["apartamento_id"]
    db.logar_progresso(apt_id, "Preenchendo credenciais...")
    login_wait = WebDriverWait(driver, 45)
    login_wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "input[id='formCad:nome']"))
    ).send_keys(USUARIO)
    driver.find_element(By.CSS_SELECTOR, "input[id='formCad:senha']").send_keys(SENHA)
    db.logar_progresso(apt_id, "Enviando login…")
    login_wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[id='formCad:entrar']"))).click()
    _clicar_continuar_login_sitesat(driver, apt_id)
    _aguardar_tela_principal_pos_login(driver, apt_id)
    db.logar_progresso(apt_id, "Login realizado com sucesso.")


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


def nome_zip_da_url(url: str) -> str:
    """Nome do arquivo .zip na URL do SATI (ex.: SATI-c2910-atual.zip)."""
    if not url:
        return ""
    m = re.search(r"(SATI-c\d+-atual\.zip)", url, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r"/([^/?#]+\.zip)(?:\?|$)", url, re.IGNORECASE)
    return m.group(1) if m else ""


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


def _wait_curto(driver, segundos: int = 12):
    return WebDriverWait(driver, segundos)


def _scroll_para_elemento(driver, el) -> None:
    try:
        driver.execute_script(
            "arguments[0].scrollIntoView({block:'center', inline:'nearest'});", el
        )
    except Exception:
        pass


def _celula_menu_hover(driver, elemento):
    """Célula TD do menu RichFaces (id terminando em _itm) — alvo correto do mouse."""
    try:
        td = driver.execute_script(
            """
            var el = arguments[0];
            var cur = el;
            while (cur) {
                if (cur.tagName === 'TD' && cur.id && cur.id.indexOf('_itm') >= 0) return cur;
                cur = cur.parentElement;
            }
            cur = el;
            while (cur) {
                if (cur.tagName === 'TD') return cur;
                cur = cur.parentElement;
            }
            return el;
            """,
            elemento,
        )
        return td or elemento
    except Exception:
        return elemento


def _mover_mouse_para_elemento(driver, actions, elemento, apartamento_id, descricao: str = ""):
    """Hover real + eventos JS — RichFaces só abre submenu com mouse sobre o TD."""
    alvo = _celula_menu_hover(driver, elemento)
    _scroll_para_elemento(driver, alvo)
    if descricao:
        db.logar_progresso(apartamento_id, f"Mouse sobre {descricao}…")
    try:
        ActionChains(driver).move_to_element(alvo).pause(0.5).perform()
    except Exception:
        try:
            actions.move_to_element(alvo).pause(0.5).perform()
        except Exception:
            pass
    try:
        driver.execute_script(
            """
            var el = arguments[0];
            function fire(node) {
                if (!node) return;
                var r = node.getBoundingClientRect();
                var x = r.left + r.width / 2, y = r.top + r.height / 2;
                ['mouseover', 'mouseenter', 'mousemove'].forEach(function (t) {
                    node.dispatchEvent(new MouseEvent(t, {
                        bubbles: true, cancelable: true, view: window,
                        clientX: x, clientY: y
                    }));
                });
            }
            fire(el);
            var lbl = el.querySelector('.rf-ddm-lbl-dec') || el.querySelector('.rf-ddm-lbl');
            if (lbl) fire(lbl);
            """,
            alvo,
        )
    except Exception:
        pass
    time.sleep(0.4)
    return alvo


def _tentar_abrir_submenu_richfaces(driver, menu_base_id: str) -> bool:
    """Tenta abrir dropdown via API RichFaces (fallback se hover falhar)."""
    try:
        return bool(
            driver.execute_script(
                """
                var base = arguments[0];
                var ids = [base, base + '_itm', base + '_label'];
                if (typeof RichFaces !== 'undefined' && RichFaces.component) {
                    for (var i = 0; i < ids.length; i++) {
                        var el = document.getElementById(ids[i]);
                        if (!el) continue;
                        var c = RichFaces.component(el);
                        if (!c) continue;
                        if (typeof c.show === 'function') { c.show(); return true; }
                        if (typeof c.expand === 'function') { c.expand(); return true; }
                    }
                }
                return false;
                """,
                menu_base_id,
            )
        )
    except Exception:
        return False


def _abrir_submenu_dropdown(
    driver, wait, actions, hover_alvo, lista_id: str, menu_base_id: str, apartamento_id
) -> bool:
    """Hover/clique até o submenu RichFaces (formMenu:xxx_list) ficar visível."""
    _mover_mouse_para_elemento(driver, actions, hover_alvo, apartamento_id)
    _tentar_abrir_submenu_richfaces(driver, menu_base_id)
    _aguardar_menu_lista(driver, wait, lista_id, timeout=8)
    if _menu_lista_visivel(driver, lista_id):
        return True

    db.logar_progresso(apartamento_id, "Hover não abriu submenu — tentando clique…")
    try:
        hover_alvo.click()
    except Exception:
        driver.execute_script("arguments[0].click();", hover_alvo)
    time.sleep(0.5)
    _tentar_abrir_submenu_richfaces(driver, menu_base_id)
    _aguardar_menu_lista(driver, wait, lista_id, timeout=8)
    return _menu_lista_visivel(driver, lista_id)


def _listar_menus_topo_sati(driver, apartamento_id, contexto: str = "") -> None:
    """Diagnóstico: rótulos da barra superior quando um menu não é encontrado."""
    try:
        labels = []
        for el in driver.find_elements(By.CSS_SELECTOR, "div.rf-ddm-lbl-dec"):
            txt = (el.text or "").strip()
            if txt:
                labels.append(txt)
        if labels:
            sufixo = f" ({contexto})" if contexto else ""
            db.logar_progresso(
                apartamento_id,
                f"Menus visíveis no SATI{sufixo}: {', '.join(labels)}",
            )
    except Exception:
        pass


def _listar_itens_submenu(driver, lista_id: str, apartamento_id, contexto: str) -> None:
    try:
        lista = driver.find_element(By.ID, lista_id)
        labels = []
        for el in lista.find_elements(By.CSS_SELECTOR, "span.rf-ddm-itm-lbl"):
            txt = (el.text or "").strip()
            if txt:
                labels.append(txt)
        if labels:
            db.logar_progresso(
                apartamento_id,
                f"Itens em {contexto}: {', '.join(labels)}",
            )
    except Exception:
        pass


def _buscar_elemento_visivel(driver, selectors, usar_iframes: bool = False):
    """Primeiro elemento visível entre seletores (página principal e, opcionalmente, iframes)."""
    driver.switch_to.default_content()
    for by, sel in selectors:
        try:
            for el in driver.find_elements(by, sel):
                if el.is_displayed():
                    return el
        except Exception:
            pass
    if not usar_iframes:
        return None
    for iframe in driver.find_elements(By.TAG_NAME, "iframe"):
        try:
            driver.switch_to.default_content()
            driver.switch_to.frame(iframe)
            for by, sel in selectors:
                try:
                    for el in driver.find_elements(by, sel):
                        if el.is_displayed():
                            return el
                except Exception:
                    pass
        except Exception:
            pass
    driver.switch_to.default_content()
    return None


def _extrair_percentual_barra(style: str | None) -> int | None:
    if not style:
        return None
    m = re.search(r"width\s*:\s*([\d.]+)\s*%", style, re.I)
    if not m:
        return None
    return int(float(m.group(1)))


def _ler_percentual_progresso_envio_bd(driver) -> int | None:
    """Lê formCad:pb.prgs (barra RichFaces) — ex.: style='width: 11%;'."""
    el = _buscar_elemento_visivel(
        driver,
        [
            (By.ID, "formCad:pb.prgs"),
            (By.CSS_SELECTOR, "div.rf-pb-prgs[id='formCad:pb.prgs']"),
            (By.CSS_SELECTOR, ".rf-pb-prgs"),
        ],
        usar_iframes=True,
    )
    if el is None:
        return None
    return _extrair_percentual_barra(el.get_attribute("style"))


def _aguardar_tela_envio_bd(driver, apartamento_id: int, timeout: int = 150):
    """Aguarda formCad:enviarDadosBI na página principal ou em iframe."""
    selectors = [
        (By.ID, "formCad:enviarDadosBI"),
        (By.CSS_SELECTOR, "select[id='formCad:enviarDadosBI']"),
        (By.XPATH, "//select[contains(@id,'enviarDadosBI')]"),
        (By.XPATH, "//*[contains(@id,'enviarDadosBI')]"),
    ]
    inicio = time.time()
    ultimo_log = 0.0
    while time.time() - inicio < timeout:
        if time.time() - ultimo_log >= 15:
            db.logar_progresso(
                apartamento_id,
                "Aguardando formulário Envio de Banco de Dados…",
            )
            ultimo_log = time.time()

        driver.switch_to.default_content()
        for by, sel in selectors:
            try:
                el = driver.find_element(by, sel)
                if el.is_displayed():
                    return el
            except Exception:
                pass

        for idx, iframe in enumerate(driver.find_elements(By.TAG_NAME, "iframe")):
            try:
                driver.switch_to.default_content()
                driver.switch_to.frame(iframe)
                for by, sel in selectors:
                    try:
                        el = driver.find_element(by, sel)
                        if el.is_displayed():
                            db.logar_progresso(
                                apartamento_id,
                                f"Formulário envio BI detectado no iframe {idx}.",
                            )
                            return el
                    except Exception:
                        pass
            except Exception:
                pass
        time.sleep(2)

    driver.switch_to.default_content()
    raise TimeoutError(
        f"Tela 'Envio de Banco de Dados' (formCad:enviarDadosBI) não carregou em {timeout}s."
    )


def _abrir_menu_configuracoes(driver, wait, actions, apartamento_id):
    """Menu superior SATI: Configurações (formMenu:j_idt711)."""
    db.logar_progresso(apartamento_id, "Abrindo menu Configurações…")
    time.sleep(0.5)

    menu = None
    for el in driver.find_elements(
        By.XPATH,
        "//div[contains(@class,'rf-ddm-lbl-dec') and normalize-space()='Configurações']",
    ):
        if el.is_displayed():
            menu = el
            break
    if menu is None:
        for el in driver.find_elements(By.ID, "formMenu:j_idt711_itm"):
            if el.is_displayed():
                menu = el
                break

    candidatos = [
        (By.ID, "formMenu:j_idt711_itm"),
        (By.XPATH, "//td[@id='formMenu:j_idt711_itm']"),
        (By.ID, "formMenu:j_idt711_label"),
        (
            By.XPATH,
            "//div[contains(@class,'rf-ddm-lbl-dec') and normalize-space()='Configurações']",
        ),
        (
            By.XPATH,
            "//div[contains(@class,'rf-ddm-lbl')][contains(normalize-space(),'Configurações')]",
        ),
    ]
    if menu is None:
        for by, sel in candidatos:
            try:
                menu = _wait_curto(driver, 6).until(
                    EC.visibility_of_element_located((by, sel))
                )
                break
            except Exception:
                continue

    if menu is None:
        _listar_menus_topo_sati(driver, apartamento_id, "menu Configurações não encontrado")
        raise RuntimeError("Menu 'Configurações' não encontrado na barra do SATI.")

    db.logar_progresso(apartamento_id, "Menu Configurações localizado — posicionando mouse…")
    hover_alvo = _celula_menu_hover(driver, menu)

    if not _abrir_submenu_dropdown(
        driver,
        wait,
        actions,
        hover_alvo,
        "formMenu:j_idt711_list",
        "formMenu:j_idt711",
        apartamento_id,
    ):
        _listar_menus_topo_sati(driver, apartamento_id, "submenu Configurações não abriu")
        raise RuntimeError(
            "Submenu 'Configurações' não abriu (formMenu:j_idt711_list invisível)."
        )

    _listar_itens_submenu(driver, "formMenu:j_idt711_list", apartamento_id, "Configurações")
    return hover_alvo


def navegar_envio_banco_dados(driver, wait, actions, apartamento_id):
    """Menu Configurações → Envio de Banco de Dados (formMenu:j_idt747 → formCad:enviarDadosBI)."""
    menu_cfg = _abrir_menu_configuracoes(driver, wait, actions, apartamento_id)

    envio_selectors = [
        (By.ID, "formMenu:j_idt747"),
        (By.CSS_SELECTOR, "[id='formMenu:j_idt747']"),
        (
            By.XPATH,
            "//div[@id='formMenu:j_idt711_list']"
            "//div[contains(@class,'rf-ddm-itm')][@id='formMenu:j_idt747']",
        ),
        (
            By.XPATH,
            "//div[@id='formMenu:j_idt711_list']"
            "//span[contains(@class,'rf-ddm-itm-lbl') and "
            "normalize-space()='Envio de Banco de Dados']"
            "/ancestor::div[contains(@class,'rf-ddm-itm')]",
        ),
        (
            By.XPATH,
            "//div[@id='formMenu:j_idt711_list']"
            "//span[contains(@class,'rf-ddm-itm-lbl') and contains(.,'Envio de Banco')]"
            "/ancestor::div[contains(@class,'rf-ddm-itm')]",
        ),
        (
            By.XPATH,
            "//span[contains(@class,'rf-ddm-itm-lbl') and "
            "normalize-space()='Envio de Banco de Dados']"
            "/ancestor::div[contains(@class,'rf-ddm-itm')]",
        ),
        (
            By.XPATH,
            "//span[contains(@class,'rf-ddm-itm-lbl') and contains(.,'Envio de Banco')]"
            "/ancestor::div[contains(@class,'rf-ddm-itm')]",
        ),
    ]

    envio = None
    for by, sel in envio_selectors:
        try:
            _mover_mouse_para_elemento(
                driver, actions, menu_cfg, apartamento_id, "Configurações (manter aberto)"
            )
            time.sleep(0.4)
            envio = _wait_curto(driver, 12).until(EC.element_to_be_clickable((by, sel)))
            db.logar_progresso(
                apartamento_id,
                f"Item 'Envio de Banco de Dados' localizado ({by}).",
            )
            break
        except Exception:
            continue

    if envio is None:
        _listar_itens_submenu(
            driver, "formMenu:j_idt711_list", apartamento_id, "Configurações (falha)"
        )
        raise RuntimeError(
            "Item 'Envio de Banco de Dados' não encontrado dentro de Configurações."
        )

    db.logar_progresso(apartamento_id, "Clicando em Envio de Banco de Dados…")
    try:
        _mover_mouse_para_elemento(driver, actions, envio, apartamento_id, "Envio de Banco de Dados")
        ActionChains(driver).move_to_element(envio).pause(0.2).click(envio).perform()
    except Exception:
        try:
            envio.click()
        except Exception:
            driver.execute_script("arguments[0].click();", envio)

    time.sleep(1)
    _aguardar_tela_envio_bd(driver, apartamento_id)
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
    ultimo_pct = -1
    ultimo_log_pct = 0.0
    while time.time() - tempo_ini < tempo_max_seg:
        try:
            fin = driver.find_element(By.ID, "formCad:pb.fin")
            if fin.is_displayed() and "conclu" in (fin.text or "").lower():
                db.logar_progresso(apartamento_id, "Processo concluído no SATI.")
                break
        except Exception:
            pass

        pct = _ler_percentual_progresso_envio_bd(driver)
        agora = time.time()
        if pct is not None and pct != ultimo_pct and (agora - ultimo_log_pct >= 3):
            db.logar_progresso(
                apartamento_id,
                f"Processamento SATI (formCad:pb.prgs): {pct}%",
            )
            ultimo_pct = pct
            ultimo_log_pct = agora

        time.sleep(2)
    else:
        raise TimeoutError(
            f"Tempo esgotado ({tempo_max_seg}s) aguardando conclusão do envio BI."
        )

    url = extrair_url_zip_da_pagina(driver)
    if not url:
        raise RuntimeError("URL do arquivo .zip do backup não encontrada na página.")
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
                pasta_downloads, nome_arquivo, apartamento_id, tempo_max_seg=120
            )
        except Exception as exc:
            if "não foi concluído" in str(exc):
                db.logar_progresso(
                    apartamento_id,
                    "Download pelo Chrome não concluiu — tentando HTTP direto…",
                )
                return False
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
    """Baixa o ZIP do SATI (HTTP no servidor Linux headless; clique no desktop)."""
    os.makedirs(pasta_destino, exist_ok=True)
    nome_url = nome_zip_da_url(url)
    if nome_url:
        nome_arquivo = nome_url
    destino = os.path.join(pasta_destino, nome_arquivo)

    usar_http = sys.platform.startswith("linux") and robo_usar_headless()
    if usar_http:
        db.logar_progresso(
            apartamento_id,
            f"Servidor Linux headless — baixando {nome_arquivo} via HTTP…",
        )
        baixado = baixar_arquivo_com_sessao(
            driver, url, pasta_destino, nome_arquivo, apartamento_id
        )
        if baixado:
            return baixado
        raise FileNotFoundError(
            f"Falha ao baixar {nome_arquivo} via HTTP. Verifique pasta {pasta_destino}."
        )

    if clicar_link_download_zip(driver, wait, apartamento_id, pasta_destino, nome_arquivo):
        return destino

    if os.path.isfile(destino):
        return destino

    baixado = baixar_arquivo_com_sessao(driver, url, pasta_destino, nome_arquivo, apartamento_id)
    if baixado:
        return baixado
    raise FileNotFoundError(
        f"Arquivo {nome_arquivo} não encontrado em {pasta_destino} após o download."
    )


def baixar_arquivo_com_sessao(driver, url: str, pasta_destino: str, nome_arquivo: str, apartamento_id):
    """Baixa arquivo usando cookies e headers da sessão Selenium."""
    os.makedirs(pasta_destino, exist_ok=True)
    destino = os.path.join(pasta_destino, nome_arquivo)

    sess = requests.Session()
    for ck in driver.get_cookies():
        sess.cookies.set(
            ck["name"],
            ck["value"],
            domain=ck.get("domain"),
            path=ck.get("path") or "/",
        )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": (driver.current_url or url or "").split("?")[0],
        "Accept": "application/pdf,image/*,*/*",
    }

    urls_tentar = [url]
    base = (url or "").split("?")[0]
    if base and base not in urls_tentar:
        urls_tentar.append(base)

    for tentativa_url in urls_tentar:
        if not tentativa_url:
            continue
        db.logar_progresso(apartamento_id, f"Baixando {nome_arquivo}…")
        try:
            resp = sess.get(tentativa_url, stream=True, timeout=600, headers=headers)
            if resp.status_code == 404:
                db.logar_progresso(
                    apartamento_id,
                    f"Arquivo não encontrado no servidor (404): {nome_arquivo}",
                )
                return None
            resp.raise_for_status()
            if os.path.isfile(destino):
                os.remove(destino)
            with open(destino, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        f.write(chunk)
            if _arquivo_baixado_valido(destino):
                db.logar_progresso(apartamento_id, f"Download salvo em {destino}")
                return destino
            db.logar_progresso(
                apartamento_id,
                f"Resposta inválida (não é PDF/imagem) em {tentativa_url[:80]}",
            )
            if os.path.isfile(destino):
                os.remove(destino)
        except requests.HTTPError as e:
            db.logar_progresso(apartamento_id, f"Falha HTTP ({tentativa_url[:80]}): {e}")
        except Exception as e:
            db.logar_progresso(apartamento_id, f"Falha HTTP ({tentativa_url[:80]}): {e}")
    return None


def _menu_lista_visivel(driver, lista_id: str) -> bool:
    try:
        el = driver.find_element(By.ID, lista_id)
    except Exception:
        return False
    style = (el.get_attribute("style") or "").replace(" ", "").lower()
    if "display:none" in style:
        return False
    return el.is_displayed()


def _aguardar_menu_lista(driver, wait, lista_id: str, timeout=20):
    try:
        WebDriverWait(driver, timeout).until(lambda d: _menu_lista_visivel(d, lista_id))
    except Exception:
        time.sleep(1)


def navegar_painel_documentos(driver, wait, actions, apartamento_id):
    """
    Painéis (hover em formMenu:j_idt299) → Diversos → Painel de Documentos (j_idt365).
    O mouse precisa permanecer sobre o menu até abrir o submenu.
    """
    db.logar_progresso(
        apartamento_id,
        "Menu Painéis: mouse sobre o item, depois Diversos → Painel de Documentos…",
    )
    time.sleep(1)

    candidatos_paineis = [
        (By.ID, "formMenu:j_idt299_itm"),
        (By.ID, "formMenu:j_idt299"),
        (By.ID, "formMenu:j_idt299_label"),
        (By.XPATH, "//td[@id='formMenu:j_idt299_itm']"),
    ]
    menu_paineis = None
    for by, sel in candidatos_paineis:
        try:
            menu_paineis = wait.until(EC.visibility_of_element_located((by, sel)))
            break
        except Exception:
            continue
    if menu_paineis is None:
        raise RuntimeError("Menu 'Painéis' (formMenu:j_idt299) não encontrado.")

    actions.move_to_element(menu_paineis).perform()
    time.sleep(0.6)
    _aguardar_menu_lista(driver, wait, "formMenu:j_idt299_list")

    candidatos_diversos = [
        (By.ID, "formMenu:j_idt357"),
        (
            By.XPATH,
            "//div[@id='formMenu:j_idt299_list']"
            "//span[contains(@class,'rf-ddm-itm-lbl') and normalize-space()='Diversos']/ancestor::div[contains(@class,'rf-ddm-itm')]",
        ),
    ]
    diversos = None
    for by, sel in candidatos_diversos:
        try:
            diversos = wait.until(EC.visibility_of_element_located((by, sel)))
            break
        except Exception:
            continue
    if diversos is None:
        raise RuntimeError("Submenu 'Diversos' não encontrado em Painéis.")

    actions.move_to_element(diversos).perform()
    time.sleep(0.6)
    _aguardar_menu_lista(driver, wait, "formMenu:j_idt357_list")

    candidatos_painel_doc = [
        (By.ID, "formMenu:j_idt365"),
        (
            By.XPATH,
            "//div[@id='formMenu:j_idt357_list']"
            "//span[contains(@class,'rf-ddm-itm-lbl') and normalize-space()='Painel de Documentos']"
            "/ancestor::div[contains(@class,'rf-ddm-itm')]",
        ),
        (
            By.XPATH,
            "//div[@id='formMenu:j_idt299_list']"
            "//span[normalize-space()='Painel de Documentos']/ancestor::div[contains(@class,'rf-ddm-itm')]",
        ),
    ]
    painel_doc = None
    for by, sel in candidatos_painel_doc:
        try:
            painel_doc = wait.until(EC.element_to_be_clickable((by, sel)))
            break
        except Exception:
            continue
    if painel_doc is None:
        raise RuntimeError("'Painel de Documentos' não encontrado no submenu Diversos.")

    actions.move_to_element(painel_doc).pause(0.3).click(painel_doc).perform()
    time.sleep(2)
    _aguardar_form_painel_documentos(driver, wait, apartamento_id)


def _aguardar_form_painel_documentos(driver, wait, apartamento_id, timeout=45):
    fim = time.time() + timeout
    while time.time() < fim:
        for sel in (
            (By.ID, "formCad:buttonAtualizar"),
            (By.ID, "formCad:filtroChaveTabela"),
        ):
            try:
                el = driver.find_element(*sel)
                if el.is_displayed():
                    db.logar_progresso(apartamento_id, "Formulário Painel de Documentos carregado.")
                    return
            except Exception:
                pass
        time.sleep(0.5)
    db.logar_progresso(apartamento_id, "Aviso: formulário do painel pode não ter carregado.")


def _limpar_campo_data_painel(driver, campo_id: str):
    """Apaga data inicial/final — no SATI não é preciso informar período."""
    try:
        inp = driver.find_element(By.ID, campo_id)
    except Exception:
        inp = driver.find_element(By.NAME, campo_id)
    inp.click()
    time.sleep(0.1)
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys(Keys.DELETE)
    inp.clear()
    driver.execute_script(
        "arguments[0].value='';"
        "arguments[0].dispatchEvent(new Event('input', {bubbles:true}));"
        "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));"
        "arguments[0].dispatchEvent(new Event('blur', {bubbles:true}));",
        inp,
    )


def preencher_filtros_painel_documentos(
    driver,
    apartamento_id,
    data_ini: str | None = None,
    data_fim: str | None = None,
    chave_tabela: str | int | None = None,
):
    """
    Painel de Documentos: datas vazias (só apagar). Opcional chave interna do CT-e.
    Se data_ini/data_fim forem passadas explicitamente, preenche (uso avançado).
    """
    campos_data = (
        "formCad:filtroDataIni:filtroDataIniInputDate",
        "formCad:filtroDataFim:filtroDataFimInputDate",
    )
    if data_ini and data_fim:
        db.logar_progresso(apartamento_id, f"Filtros painel: {data_ini} até {data_fim}")
        for campo_id, valor in zip(campos_data, (data_ini, data_fim)):
            try:
                inp = driver.find_element(By.ID, campo_id)
            except Exception:
                inp = driver.find_element(By.NAME, campo_id)
            inp.clear()
            inp.send_keys(valor)
    else:
        db.logar_progresso(apartamento_id, "Limpando datas inicial e final (sem digitar período).")
        for campo_id in campos_data:
            _limpar_campo_data_painel(driver, campo_id)

    if chave_tabela is None:
        raise ValueError(
            "Número interno do CT-e obrigatório (formCad:filtroChaveTabela) após limpar as datas."
        )
    chave = str(chave_tabela).strip()
    if not chave:
        raise ValueError("filtroChaveTabela vazio.")
    db.logar_progresso(apartamento_id, f"Digitando número interno: {chave}")
    try:
        ch = driver.find_element(By.ID, "formCad:filtroChaveTabela")
    except Exception:
        ch = driver.find_element(By.NAME, "formCad:filtroChaveTabela")
    ch.clear()
    ch.send_keys(chave)
    time.sleep(0.3)


def aguardar_overlay_sati(driver, apartamento_id, tempo_max_seg=120):
    """Aguarda overlay 'aguarde' do SATI sumir após submit."""
    tempo_ini = time.time()
    while time.time() - tempo_ini < tempo_max_seg:
        visivel = False
        for sel in (
            "[id*='aguarde']",
            ".rf-pp-cnt",
            ".rf-pp-shade",
        ):
            try:
                for el in driver.find_elements(By.CSS_SELECTOR, sel):
                    if el.is_displayed():
                        style = (el.get_attribute("style") or "").lower()
                        if "display: none" in style or "visibility: hidden" in style:
                            continue
                        visivel = True
                        break
            except Exception:
                pass
            if visivel:
                break
        if not visivel:
            time.sleep(1)
            return
        time.sleep(1)
    db.logar_progresso(apartamento_id, "Overlay de espera ainda visível; seguindo mesmo assim.")


def clicar_atualizar_painel_documentos(driver, wait, apartamento_id):
    db.logar_progresso(apartamento_id, "Clicando em Atualizar Painel…")
    try:
        btn = driver.find_element(By.ID, "formCad:buttonAtualizar")
    except Exception:
        btn = driver.find_element(By.NAME, "formCad:buttonAtualizar")
    btn.click()
    time.sleep(1)
    aguardar_overlay_sati(driver, apartamento_id)
    time.sleep(1)


def listar_links_comprovantes_painel(driver, apartamento_id) -> list[dict]:
    """Links da grade (nomearq + número interno parseado do arquivo)."""
    from sati_integration.db.sati_documento import extrair_numero_conhecimento

    xpaths = [
        "//form[@id='formCad']//a[contains(@onclick,'mojarra.jsfcljs') "
        "and (contains(.,'COMPROVANT') or contains(.,'.pdf') or contains(.,'.PDF'))]",
        "//a[contains(@onclick,'mojarra.jsfcljs') and contains(@onclick,'formCad:table')]",
    ]
    links = []
    for xpath in xpaths:
        links = driver.find_elements(By.XPATH, xpath)
        if links:
            break

    resultado = []
    vistos = set()
    for el in links:
        texto = (el.text or "").strip()
        if not texto or texto in vistos:
            continue
        vistos.add(texto)
        resultado.append({
            "nomearq": texto,
            "numero_conhecimento": extrair_numero_conhecimento(texto),
            "elemento": el,
        })
    db.logar_progresso(apartamento_id, f"Comprovantes listados no painel: {len(resultado)}")
    return resultado


def abrir_comprovante_nova_aba(driver, link_element, apartamento_id) -> str | None:
    """Clica no link (_blank), captura URL e fecha a aba extra."""
    handles_antes = set(driver.window_handles)
    driver.execute_script("arguments[0].click();", link_element)
    time.sleep(2)
    novos = [h for h in driver.window_handles if h not in handles_antes]
    if not novos:
        return driver.current_url
    driver.switch_to.window(novos[-1])
    time.sleep(2)
    url = driver.current_url
    db.logar_progresso(apartamento_id, f"Nova aba comprovante: {(url or '')[:100]}")
    driver.close()
    driver.switch_to.window(driver.window_handles[0])
    return url


def _aguardar_nova_aba_documento(
    driver,
    handles_antes: set[str],
    apartamento_id: int,
    timeout: int = 45,
) -> str | None:
    """Aguarda nova aba abrir após clicar no link do comprovante."""
    db.logar_progresso(apartamento_id, "Aguardando nova aba do documento…")
    fim = time.time() + timeout
    while time.time() < fim:
        novos = [h for h in driver.window_handles if h not in handles_antes]
        if novos:
            aba = novos[-1]
            driver.switch_to.window(aba)
            db.logar_progresso(apartamento_id, "Nova aba do documento detectada.")
            return aba
        time.sleep(0.5)
    db.logar_progresso(apartamento_id, "Nova aba não abriu dentro do tempo.")
    return None


def _aguardar_visualizador_documento(
    driver,
    nome_arquivo: str,
    apartamento_id: int,
    timeout: int = 75,
) -> str:
    """
    Espera a URL final (com extensão) e o visualizador do Chrome terminar de carregar
    antes de tentar Baixar ou HTTP.
    """
    stem = (nome_arquivo or "").rsplit(".", 1)[0].lower()
    db.logar_progresso(
        apartamento_id,
        f"Aguardando arquivo abrir no visualizador ({nome_arquivo})…",
    )
    fim = time.time() + timeout
    ultima_url = ""
    estavel = 0
    while time.time() < fim:
        try:
            ready = driver.execute_script("return document.readyState") == "complete"
        except Exception:
            ready = False
        url = (driver.current_url or "").strip()
        if not url or url.startswith("about:"):
            time.sleep(0.8)
            continue

        url_parece_completa = bool(
            re.search(r"2COMPROVANT_\d+\.(pdf|jpe?g|png)", url, re.I)
            or (stem and stem in url.lower() and re.search(r"\.(pdf|jpe?g|png)", url, re.I))
        )
        viewer_pronto = False
        try:
            viewer_pronto = bool(
                driver.execute_script(
                    """
                    var embed = document.querySelector('embed[type="application/pdf"]');
                    if (embed) return true;
                    if (document.querySelector('pdf-viewer, #viewer')) return true;
                    function hasSave(root) {
                      if (!root) return false;
                      if (root.querySelector('cr-icon-button#save, #save')) return true;
                      var nodes = root.querySelectorAll('*');
                      for (var i = 0; i < nodes.length; i++) {
                        if (nodes[i].shadowRoot && hasSave(nodes[i].shadowRoot)) return true;
                      }
                      return false;
                    }
                    return hasSave(document);
                    """
                )
            )
        except Exception:
            viewer_pronto = False

        if url_parece_completa and (ready or viewer_pronto):
            if url == ultima_url:
                estavel += 1
            else:
                estavel = 0
                ultima_url = url
            if estavel >= 2:
                db.logar_progresso(
                    apartamento_id,
                    f"Visualizador pronto: {url[:120]}",
                )
                time.sleep(1.5)
                return url
        elif url != ultima_url:
            ultima_url = url
            estavel = 0
        time.sleep(0.8)

    db.logar_progresso(
        apartamento_id,
        f"Visualizador: tempo esgotado; URL atual: {(ultima_url or driver.current_url or '')[:120]}",
    )
    return ultima_url or (driver.current_url or "")


def _arquivo_baixado_valido(caminho: str, min_bytes: int = 50) -> bool:
    if not caminho or not os.path.isfile(caminho):
        return False
    if os.path.getsize(caminho) < min_bytes:
        return False
    try:
        with open(caminho, "rb") as f:
            head = f.read(512).lstrip()
    except OSError:
        return False
    if head.startswith(b"<!") or head.lower().startswith(b"<html") or head.startswith(b"{"):
        return False
    if head.startswith(b"PK\x03\x04") or head.startswith(b"PK\x05\x06"):
        return True
    if (
        head.startswith(b"%PDF")
        or head.startswith(b"\xff\xd8\xff")
        or head.startswith(b"\x89PNG")
    ):
        return True
    return len(head) >= min_bytes


def _clicar_botao_baixar_visualizador_chrome(driver, apartamento_id) -> bool:
    """Botão Baixar do visualizador PDF do Chrome (cr-icon-button#save, shadow DOM)."""
    script_shadow = """
    function clickInShadow(root) {
      if (!root) return false;
      var save = root.querySelector('cr-icon-button#save, #save, [id="save"]');
      if (save) { save.click(); return true; }
      var byLabel = root.querySelector('[aria-label="Baixar"],[title="Baixar"]');
      if (byLabel) { byLabel.click(); return true; }
      var all = root.querySelectorAll('*');
      for (var i = 0; i < all.length; i++) {
        if (all[i].shadowRoot && clickInShadow(all[i].shadowRoot)) return true;
      }
      return false;
    }
    return clickInShadow(document);
    """
    scripts = (
        script_shadow,
        "var b=document.querySelector('cr-icon-button#save');if(b){b.click();return true;}",
        "var b=document.getElementById('save');if(b){b.click();return true;}",
        (
            "var b=document.querySelector('[aria-label=\"Baixar\"],"
            "[title=\"Baixar\"][role=\"button\"]');if(b){b.click();return true;}"
        ),
    )
    for script in scripts:
        try:
            if driver.execute_script(script):
                db.logar_progresso(apartamento_id, "Clicou em Baixar no visualizador do Chrome.")
                return True
        except Exception:
            pass

    seletores = (
        (By.ID, "save"),
        (By.CSS_SELECTOR, "cr-icon-button#save"),
        (By.CSS_SELECTOR, "[aria-label='Baixar']"),
        (By.XPATH, "//*[@id='save' or @aria-label='Baixar']"),
    )
    for by, sel in seletores:
        try:
            el = driver.find_element(by, sel)
            driver.execute_script("arguments[0].click();", el)
            db.logar_progresso(apartamento_id, "Clicou em Baixar (seletor Selenium).")
            return True
        except Exception:
            continue
    return False


def _fechar_aba_documento(driver, janela_principal: str, apartamento_id: int) -> None:
    """Garante fechamento da aba do PDF e volta à janela principal."""
    try:
        if len(driver.window_handles) > 1:
            atual = driver.current_window_handle
            if atual != janela_principal:
                driver.close()
    except Exception:
        pass
    try:
        if janela_principal in driver.window_handles:
            driver.switch_to.window(janela_principal)
        elif driver.window_handles:
            driver.switch_to.window(driver.window_handles[0])
    except Exception:
        pass
    db.logar_progresso(apartamento_id, "Aba do documento fechada.")


def _aguardar_e_acionar_baixar_pdf(driver, apartamento_id, tempo_max_seg: int = 25) -> bool:
    """Espera o botão Baixar aparecer e clica (shadow DOM + Ctrl+S)."""
    db.logar_progresso(apartamento_id, "Aguardando botão Baixar do PDF…")
    fim = time.time() + tempo_max_seg
    clicou = False
    while time.time() < fim:
        if _clicar_botao_baixar_visualizador_chrome(driver, apartamento_id):
            clicou = True
            time.sleep(2)
            break
        time.sleep(0.8)
    if clicou:
        return True
    try:
        body = driver.find_element(By.TAG_NAME, "body")
        ActionChains(driver).click(body).key_down(Keys.CONTROL).send_keys("s").key_up(Keys.CONTROL).perform()
        db.logar_progresso(apartamento_id, "Enviado Ctrl+S para salvar o PDF.")
        time.sleep(1)
        return True
    except Exception as e:
        db.logar_progresso(apartamento_id, f"Ctrl+S falhou: {e}")
    return False


def _esperar_novo_arquivo_em_pasta(
    pasta: str,
    arquivos_antes: set[str],
    apartamento_id: int,
    tempo_max_seg: int = 120,
    extensoes: tuple[str, ...] = (".pdf", ".png", ".jpg", ".jpeg"),
) -> str | None:
    """Aguarda novo arquivo na pasta de download do Chrome (após botão Baixar)."""
    fim = time.time() + tempo_max_seg
    while time.time() < fim:
        try:
            nomes = os.listdir(pasta)
        except OSError:
            time.sleep(1)
            continue
        if any(n.endswith(".crdownload") for n in nomes):
            time.sleep(1)
            continue
        for nome in nomes:
            if nome in arquivos_antes:
                continue
            low = nome.lower()
            if low.endswith((".htm", ".html", ".crdownload")):
                continue
            if any(low.endswith(ext) for ext in extensoes):
                caminho = os.path.join(pasta, nome)
                if _arquivo_baixado_valido(caminho):
                    db.logar_progresso(apartamento_id, f"Download detectado: {nome}")
                    return caminho
        time.sleep(1)
    db.logar_progresso(apartamento_id, "Tempo esgotado aguardando arquivo baixado.")
    return None


def baixar_comprovante_via_aba_visualizador(
    driver,
    wait,
    link_element,
    pasta_downloads: str,
    nome_arquivo: str,
    apartamento_id: int,
) -> str | None:
    """
    Abre o link em nova aba, clica em Baixar, aguarda o arquivo e só então fecha a aba.
    """
    import shutil

    handles_antes = set(driver.window_handles)
    janela_principal = driver.current_window_handle
    try:
        arquivos_antes = set(os.listdir(pasta_downloads))
    except OSError:
        arquivos_antes = set()

    db.logar_progresso(apartamento_id, f"Abrindo comprovante para baixar: {nome_arquivo}")
    baixado = None
    url = ""
    try:
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", link_element)
            time.sleep(0.3)
            driver.execute_script("arguments[0].click();", link_element)
        except Exception:
            link_element.click()

        aba_pdf = _aguardar_nova_aba_documento(driver, handles_antes, apartamento_id, timeout=45)
        if not aba_pdf:
            db.logar_progresso(apartamento_id, "Nova aba não abriu; tentando mesma janela / HTTP.")
            url = driver.current_url or ""
            if url and not url.startswith("about:") and re.search(r"\.(pdf|jpe?g|png)", url, re.I):
                baixado = baixar_arquivo_com_sessao(
                    driver, url, pasta_downloads, nome_arquivo, apartamento_id
                )
            return _finalizar_destino_comprovante(baixado, pasta_downloads, nome_arquivo, apartamento_id)

        _configurar_pasta_download_chrome(driver, pasta_downloads)
        url = _aguardar_visualizador_documento(
            driver, nome_arquivo, apartamento_id, timeout=60
        )
        db.logar_progresso(apartamento_id, f"Documento aberto: {(url or '')[:120]}")

        url_completa = bool(
            url and re.search(r"2COMPROVANT_\d+\.(pdf|jpe?g|png)", url, re.I)
        )
        http_404 = False
        if url_completa:
            db.logar_progresso(apartamento_id, "Download HTTP direto (URL completa)…")
            baixado = baixar_arquivo_com_sessao(
                driver, url, pasta_downloads, nome_arquivo, apartamento_id
            )
            if not baixado and url:
                try:
                    import requests as _req

                    probe = _req.head(url.split("?")[0], timeout=15, allow_redirects=True)
                    http_404 = probe.status_code == 404
                except Exception:
                    pass

        if not baixado and not http_404:
            for tentativa in range(1, 3):
                db.logar_progresso(
                    apartamento_id,
                    f"Tentativa {tentativa}/2: botão Baixar no visualizador…",
                )
                _aguardar_e_acionar_baixar_pdf(driver, apartamento_id, tempo_max_seg=25)
                baixado = _esperar_novo_arquivo_em_pasta(
                    pasta_downloads, arquivos_antes, apartamento_id, tempo_max_seg=45
                )
                if baixado and _arquivo_baixado_valido(baixado):
                    break
                baixado = None
                time.sleep(1)

        if not baixado and url and url_completa and not http_404:
            db.logar_progresso(apartamento_id, "Repetindo download HTTP…")
            baixado = baixar_arquivo_com_sessao(
                driver, url, pasta_downloads, nome_arquivo, apartamento_id
            )

        if not baixado:
            if http_404:
                db.logar_progresso(
                    apartamento_id,
                    f"Comprovante listado no painel, mas arquivo ausente no servidor ({nome_arquivo}).",
                )
            else:
                db.logar_progresso(apartamento_id, f"FALHA: PDF não salvo ({nome_arquivo}).")
            return None

        return _finalizar_destino_comprovante(baixado, pasta_downloads, nome_arquivo, apartamento_id)
    finally:
        _fechar_aba_documento(driver, janela_principal, apartamento_id)


def _finalizar_destino_comprovante(
    baixado: str | None,
    pasta_downloads: str,
    nome_arquivo: str,
    apartamento_id: int,
) -> str | None:
    import shutil

    if not baixado or not _arquivo_baixado_valido(baixado):
        return None
    os.makedirs(pasta_downloads, exist_ok=True)
    destino = os.path.join(pasta_downloads, nome_arquivo)
    if os.path.abspath(baixado) != os.path.abspath(destino):
        if os.path.isfile(destino):
            os.remove(destino)
        shutil.move(baixado, destino)
    db.logar_progresso(apartamento_id, f"PDF salvo: {destino}")
    return destino


def baixar_comprovante_painel(
    driver,
    url: str,
    pasta_destino: str,
    nome_arquivo: str,
    apartamento_id: int,
) -> str | None:
    """Fallback: baixa por HTTP com cookies da sessão."""
    if not url or url.startswith("about:"):
        return None
    return baixar_arquivo_com_sessao(driver, url, pasta_destino, nome_arquivo, apartamento_id)
