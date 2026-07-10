# -*- coding: utf-8 -*-
"""
Robô: Painéis → Painel de Documentos no SATI.

Fluxo (consPainelDocumento.jsf):
  1. Apaga data início/fim (não digita período)
  2. Opcional: formCad:filtroChaveTabela = número interno do CT-e (conhecimento.numero)
  3. Atualizar Painel
  4. Links 2026/COMPROVANTEDEDESCARGA/2COMPROVANT_{numero}.pdf → nova aba

Grava cache em downloads/{apartamento_id}/comprovantes_painel.json
para o fluxo de viagem marcar comprovante sem depender só do dump SQL.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.data import database as db
from app.core import logic
from sati_integration.robos import base_robo
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait

try:
    from sati_integration.db.sati_documento import COD_TIPO_DOC_COMPROVANTE_DESCARGA
except ImportError:
    COD_TIPO_DOC_COMPROVANTE_DESCARGA = 69


def _caminho_cache(apartamento_id: int) -> str:
    try:
        from app.utils.paths import downloads_dir

        pasta = os.path.abspath(str(downloads_dir(apartamento_id)))
    except Exception:
        pasta = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "downloads",
            str(apartamento_id),
        )
    os.makedirs(pasta, exist_ok=True)
    return os.path.join(pasta, "comprovantes_painel.json")


def carregar_cache_comprovantes(apartamento_id: int) -> dict:
    path = _caminho_cache(apartamento_id)
    if not os.path.isfile(path):
        return {"atualizado_em": None, "itens": []}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"atualizado_em": None, "itens": []}


def numeros_com_comprovante_cache(apartamento_id: int) -> set[int]:
    nums = set()
    for item in carregar_cache_comprovantes(apartamento_id).get("itens") or []:
        n = item.get("numero_conhecimento")
        if n is not None:
            try:
                nums.add(int(n))
            except (TypeError, ValueError):
                pass
    return nums


def salvar_cache_comprovantes(apartamento_id: int, itens: list[dict]) -> str:
    path = _caminho_cache(apartamento_id)
    serializaveis = []
    for row in itens:
        serializaveis.append({k: v for k, v in row.items() if k != "elemento"})
    payload = {
        "atualizado_em": datetime.now().isoformat(timespec="seconds"),
        "codtipodoc": COD_TIPO_DOC_COMPROVANTE_DESCARGA,
        "nometabela": "CONHECIMENTO",
        "itens": serializaveis,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def _coletar_bloco(
    driver,
    wait,
    apartamento_id,
    pasta_downloads: str,
    data_ini: str | None,
    data_fim: str | None,
    numero_interno: int | None,
    baixar_pdfs: bool,
) -> list[dict]:
    base_robo.preencher_filtros_painel_documentos(
        driver,
        apartamento_id,
        data_ini=data_ini,
        data_fim=data_fim,
        chave_tabela=numero_interno,
    )
    base_robo.clicar_atualizar_painel_documentos(driver, wait, apartamento_id)
    links = base_robo.listar_links_comprovantes_painel(driver, apartamento_id)
    pasta_pdf = os.path.join(pasta_downloads, "comprovantes_descarga")
    os.makedirs(pasta_pdf, exist_ok=True)
    itens = []

    if numero_interno is not None:
        links_filtrados = [
            ln
            for ln in links
            if ln.get("numero_conhecimento") == int(numero_interno)
        ]
        if not links_filtrados and links:
            db.logar_progresso(
                apartamento_id,
                f"Aviso: nenhum link 2COMPROVANT_{numero_interno}; usando primeiro da grade.",
            )
            links_filtrados = links[:1]
        links = links_filtrados or links

    for idx, info in enumerate(links):
        nomearq = info["nomearq"]
        numero = info.get("numero_conhecimento")
        arquivo_local = None

        if baixar_pdfs and numero:
            links_atual = base_robo.listar_links_comprovantes_painel(driver, apartamento_id)
            elemento = None
            for ln in links_atual:
                if ln.get("numero_conhecimento") == numero or ln.get("nomearq") == nomearq:
                    elemento = ln.get("elemento")
                    nomearq = ln.get("nomearq") or nomearq
                    break
            if elemento is None and links_atual:
                elemento = links_atual[min(idx, len(links_atual) - 1)].get("elemento")

            if elemento is not None:
                try:
                    nome_arq = f"2COMPROVANT_{numero}.pdf"
                    db.logar_progresso(
                        apartamento_id,
                        f"Baixando PDF CT-e interno {numero} ({nomearq})…",
                    )
                    dest = base_robo.baixar_comprovante_via_aba_visualizador(
                        driver,
                        wait,
                        elemento,
                        pasta_downloads,
                        nome_arq,
                        apartamento_id,
                    )
                    if dest and os.path.isfile(dest):
                        arquivo_local = dest
                        dest_final = os.path.join(pasta_pdf, nome_arq)
                        if os.path.abspath(dest) != os.path.abspath(dest_final):
                            import shutil
                            if os.path.isfile(dest_final):
                                os.remove(dest_final)
                            shutil.move(dest, dest_final)
                        arquivo_local = dest_final
                    else:
                        db.logar_progresso(
                            apartamento_id,
                            f"PDF não baixado para CT-e {numero}; tentará de novo antes do próximo.",
                        )
                except Exception as e:
                    db.logar_progresso(apartamento_id, f"Erro ao baixar {nomearq}: {e}")
                    try:
                        base_robo.preencher_filtros_painel_documentos(
                            driver,
                            apartamento_id,
                            data_ini=data_ini,
                            data_fim=data_fim,
                            chave_tabela=numero_interno,
                        )
                        base_robo.clicar_atualizar_painel_documentos(
                            driver, wait, apartamento_id
                        )
                    except Exception:
                        pass
            else:
                db.logar_progresso(
                    apartamento_id,
                    f"Link do comprovante não encontrado na grade para {numero}.",
                )
        elif not baixar_pdfs:
            db.logar_progresso(
                apartamento_id,
                "Modo sem download (baixar_pdfs=false); só metadados.",
            )

        texto_extraido = ""
        if arquivo_local:
            try:
                from sati_integration.robos.comprovante_descarga import extrair_texto_arquivo

                texto_extraido = extrair_texto_arquivo(arquivo_local)
            except Exception:
                pass

        itens.append({
            "nomearq": nomearq,
            "numero_conhecimento": numero,
            "numero_interno_filtro": numero_interno,
            "arquivo_local": arquivo_local,
            "texto_extraido": texto_extraido,
            "indice_tabela": idx,
        })

        if baixar_pdfs and numero_interno is not None:
            break
    return itens


def _caminho_lock_robo_painel(apartamento_id: int) -> str:
    return os.path.join(os.path.dirname(_caminho_cache(apartamento_id)), "painel_documentos_robo.lock")


def _processo_ativo(pid: int) -> bool:
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x00100000, False, pid)
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _ler_lock_robo_painel(apartamento_id: int) -> dict:
    path = _caminho_lock_robo_painel(apartamento_id)
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            raw = (f.read() or "").strip()
        if raw.startswith("{"):
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        if raw.isdigit():
            return {
                "pid": int(raw),
                "started": datetime.fromtimestamp(os.path.getmtime(path)).isoformat(
                    timespec="seconds"
                ),
            }
    except (json.JSONDecodeError, OSError, ValueError):
        pass
    return {}


def _idade_lock_segundos(lock: dict, path: str) -> float:
    raw = lock.get("started")
    if raw:
        try:
            started = datetime.fromisoformat(str(raw))
            return max(0.0, (datetime.now() - started).total_seconds())
        except ValueError:
            pass
    try:
        return max(0.0, time.time() - os.path.getmtime(path))
    except OSError:
        return 0.0


def _limpar_lock_robo_obsoleto(apartamento_id: int) -> None:
    """Remove lock travado (worker RQ long-lived ou processo morto)."""
    path = _caminho_lock_robo_painel(apartamento_id)
    if not os.path.isfile(path):
        return
    try:
        lock = _ler_lock_robo_painel(apartamento_id)
        pid = int(lock.get("pid") or 0)
        idade = _idade_lock_segundos(lock, path)
        try:
            max_min = max(30, int(os.getenv("ROBO_PAINEL_LOCK_MAX_MIN", "120")))
        except ValueError:
            max_min = 120
        max_seg = max_min * 60
        if idade > max_seg:
            os.remove(path)
            db.logar_progresso(apartamento_id, "Lock obsoleto do robô removido (tempo máximo).")
            return
        if pid and not _processo_ativo(pid) and idade > 120:
            os.remove(path)
            db.logar_progresso(apartamento_id, "Lock obsoleto do robô removido (processo encerrado).")
    except OSError:
        try:
            os.remove(path)
        except OSError:
            pass


def lock_painel_em_execucao(apartamento_id: int) -> bool:
    _limpar_lock_robo_obsoleto(apartamento_id)
    return os.path.isfile(_caminho_lock_robo_painel(apartamento_id))


def _adquirir_lock_robo_painel(apartamento_id: int) -> bool:
    """Evita duas instâncias Chrome do Painel de Documentos ao mesmo tempo."""
    _limpar_lock_robo_obsoleto(apartamento_id)
    path = _caminho_lock_robo_painel(apartamento_id)
    if os.path.isfile(path):
        return False
    try:
        payload = {
            "pid": os.getpid(),
            "started": datetime.now().isoformat(timespec="seconds"),
            "robot": "painel_documentos",
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        return True
    except OSError:
        return False


def _liberar_lock_robo_painel(apartamento_id: int) -> None:
    path = _caminho_lock_robo_painel(apartamento_id)
    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass


def executar_painel_documentos_sati(
    apartamento_id: int,
    *,
    data_ini: str | None = None,
    data_fim: str | None = None,
    numeros_internos: list[int] | None = None,
    baixar_pdfs: bool = True,
) -> bool:
    """Login SATI → Painel de Documentos → lista comprovantes → cache JSON."""
    db.logar_progresso(apartamento_id, "\n--- INICIANDO ROBÔ: PAINEL DE DOCUMENTOS ---")

    if not _adquirir_lock_robo_painel(apartamento_id):
        db.logar_progresso(
            apartamento_id,
            "Robô Painel de Documentos já em execução; ignorando nova chamada.",
        )
        return False

    driver = None
    try:
        configs = logic.ler_configuracoes_robo(apartamento_id)
        configs["apartamento_id"] = apartamento_id

        from app.data import data_manager as dm

        if not dm.robo_credenciais_configuradas(configs):
            db.logar_progresso(
                apartamento_id,
                "ERRO: URL, usuário ou senha do robô não configurados.",
            )
            return False

        modo = "oculto (headless)" if base_robo.robo_usar_headless() else "visível"
        db.logar_progresso(apartamento_id, f"Navegador Chrome: modo {modo}")
        driver, pasta_downloads = base_robo.configurar_driver(apartamento_id)
        wait = WebDriverWait(driver, 45)
        actions = ActionChains(driver)

        alvos = [int(n) for n in (numeros_internos or []) if n is not None]

        base_robo.fazer_login(driver, wait, configs)
        base_robo.navegar_painel_documentos(driver, wait, actions, apartamento_id)

        todos: list[dict] = []
        if not alvos:
            db.logar_progresso(
                apartamento_id,
                "ERRO: informe pelo menos um número interno do CT-e "
                "(ex.: 7801). Uso: python robos/coletor_painel_documentos.py <apt> 7801 7965",
            )
            return False

        for numero in alvos:
            bloco: list[dict] = []
            for tentativa in range(1, 4):
                if tentativa > 1:
                    db.logar_progresso(
                        apartamento_id,
                        f"Nova tentativa ({tentativa}/3) download CT-e {numero}…",
                    )
                    time.sleep(3)
                bloco = _coletar_bloco(
                    driver,
                    wait,
                    apartamento_id,
                    pasta_downloads,
                    data_ini,
                    data_fim,
                    numero,
                    baixar_pdfs,
                )
                if not baixar_pdfs:
                    break
                tem_arquivo = any(
                    b.get("arquivo_local") and os.path.isfile(b["arquivo_local"])
                    for b in bloco
                )
                if tem_arquivo:
                    break
            todos.extend(bloco)

        unicos: dict[str, dict] = {}
        for row in todos:
            chave = row.get("nomearq") or str(row.get("numero_conhecimento"))
            unicos[chave] = row
        lista_final = list(unicos.values())

        # Preserva PDF já baixado se nova tentativa falhou
        antigo = carregar_cache_comprovantes(apartamento_id).get("itens") or []
        por_numero = {
            int(x["numero_conhecimento"]): x
            for x in antigo
            if x.get("numero_conhecimento") is not None
        }
        for row in lista_final:
            n = row.get("numero_conhecimento")
            if n is None:
                continue
            try:
                chave_n = int(n)
            except (TypeError, ValueError):
                continue
            prev = por_numero.get(chave_n) or {}
            if prev.get("arquivo_local") and not row.get("arquivo_local"):
                row["arquivo_local"] = prev["arquivo_local"]
                row["texto_extraido"] = prev.get("texto_extraido") or row.get("texto_extraido")

        path = salvar_cache_comprovantes(apartamento_id, lista_final)
        baixados = sum(
            1
            for row in lista_final
            if row.get("arquivo_local") and os.path.isfile(row["arquivo_local"])
        )
        db.logar_progresso(
            apartamento_id,
            f"PAINEL DE DOCUMENTOS CONCLUÍDO: {len(lista_final)} item(ns), "
            f"{baixados} arquivo(s) baixado(s). Cache: {path}",
        )
        if baixar_pdfs and alvos and baixados == 0:
            db.logar_progresso(
                apartamento_id,
                "ERRO: documento(s) listado(s) no painel, mas nenhum PDF foi salvo.",
            )
            return False
        try:
            from app.data import data_manager as dm

            dm.clear_data_cache(apartamento_id)
        except Exception:
            pass
        return True

    except Exception as e:
        db.logar_progresso(apartamento_id, f"ERRO no Painel de Documentos: {e}")
        try:
            from sati_integration.robos.comprovante_descarga import liberar_coleta_da_fila

            liberar_coleta_da_fila(
                apartamento_id,
                [int(n) for n in (numeros_internos or []) if n is not None],
            )
        except Exception:
            pass
        return False
    finally:
        _liberar_lock_robo_painel(apartamento_id)
        if driver:
            from sati_integration.robos.chrome_cleanup import encerrar_driver_chrome

            encerrar_driver_chrome(driver, apartamento_id)


if __name__ == "__main__":
    apt = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    nums = [int(x) for x in sys.argv[2:]] if len(sys.argv) > 2 else None
    ok = executar_painel_documentos_sati(apt, numeros_internos=nums, baixar_pdfs=False)
    sys.exit(0 if ok else 1)
