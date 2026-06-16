# robos/coletor_atualizacao_bd.py — gera backup BI no SATI e restaura PostgreSQL

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logic
import database as db
import data_manager as dm
import sati_db_restore as sati_restore
import robos.base_robo as base_robo
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains


def executar_atualizacao_bd_sati(apartamento_id: int):
    """Login SATI → Envio banco dados BI → download zip → pg_restore."""
    db.logar_progresso(apartamento_id, "\n--- INICIANDO ROBÔ: ATUALIZAÇÃO BANCO SATI ---")

    driver = None
    try:
        configs = logic.ler_configuracoes_robo(apartamento_id)
        configs["apartamento_id"] = apartamento_id  # ID transportadora (legado)

        if not dm.robo_credenciais_configuradas(configs):
            db.logar_progresso(
                apartamento_id,
                "ERRO: URL, usuário ou senha do robô não configurados. "
                "Salve em Robô → Conexão SAT ou use URL_LOGIN / USUARIO_ROBO / SENHA_ROBO no .env.",
            )
            return False

        if not os.getenv("SATI_DATABASE_URL", "").strip():
            db.logar_progresso(
                apartamento_id,
                "ERRO: SATI_DATABASE_URL não definida no .env.",
            )
            return False

        modo = "oculto (headless)" if base_robo.robo_usar_headless() else "visível"
        db.logar_progresso(apartamento_id, f"Navegador Chrome: modo {modo}")
        driver, pasta_downloads = base_robo.configurar_driver(apartamento_id)
        wait = WebDriverWait(driver, 90)
        actions = ActionChains(driver)

        base_robo.fazer_login(driver, wait, configs)
        try:
            base_robo.navegar_envio_banco_dados(driver, wait, actions, apartamento_id)
        except Exception as e:
            raise RuntimeError(f"Falha ao abrir Envio de Banco de Dados: {e}") from e

        try:
            url_zip = base_robo.executar_envio_banco_bi(driver, wait, apartamento_id)
        except Exception as e:
            raise RuntimeError(f"Falha no processamento do envio BI: {e}") from e
        nome_zip = os.getenv("SATI_ZIP_FILENAME", "SATI-c3332-atual.zip")

        base_robo.baixar_zip_sati(
            driver, wait, url_zip, pasta_downloads, nome_zip, apartamento_id
        )

        zip_path = sati_restore.localizar_zip_baixado(pasta_downloads)
        if not zip_path:
            zip_path = os.path.join(pasta_downloads, nome_zip)
        if not os.path.isfile(zip_path):
            raise FileNotFoundError(
                f"Arquivo {nome_zip} não encontrado em {pasta_downloads} após o download."
            )

        dm.clear_data_cache(apartamento_id)
        sati_restore.processar_arquivo_zip_sati(zip_path, apartamento_id=apartamento_id)
        dm.clear_data_cache(apartamento_id)

        db.logar_progresso(apartamento_id, "ATUALIZAÇÃO DO BANCO SATI CONCLUÍDA.")
        return True

    except Exception as e:
        db.logar_progresso(apartamento_id, f"ERRO CRÍTICO na atualização do banco SATI: {e}")
        return False
    finally:
        if driver:
            db.logar_progresso(apartamento_id, "Fechando o navegador.")
            driver.quit()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        executar_atualizacao_bd_sati(int(sys.argv[1]))
    else:
        print("Uso: python robos/coletor_atualizacao_bd.py <apartamento_id>")
