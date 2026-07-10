"""Encerramento seguro do Chrome headless e limpeza de processos zumbi (Linux/Debian)."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

_SESSOES_DIR = Path(os.getenv("BIWEB_CHROME_SESSIONS_DIR", "/tmp/biweb-chrome-sessions"))


def _max_idade_segundos() -> int:
    try:
        minutos = int(os.getenv("BIWEB_CHROME_ZOMBIE_MAX_MINUTES", "45"))
    except ValueError:
        minutos = 45
    return max(10, minutos) * 60


def _user_data_dir_robo() -> str:
    base = Path(os.getenv("BIWEB_CHROME_PROFILE_DIR", "/tmp/biweb-chrome-profiles"))
    base.mkdir(parents=True, exist_ok=True)
    pasta = base / uuid.uuid4().hex[:12]
    pasta.mkdir(parents=True, exist_ok=True)
    return str(pasta)


def preparar_opcoes_chrome(chrome_options) -> str | None:
    """Perfil temporário isolado — evita acúmulo em /tmp do Chromium."""
    if not robo_cleanup_habilitado():
        return None
    pasta = _user_data_dir_robo()
    chrome_options.add_argument(f"--user-data-dir={pasta}")
    return pasta


def robo_cleanup_habilitado() -> bool:
    flag = os.getenv("BIWEB_CHROME_CLEANUP", "true").strip().lower()
    return flag not in ("0", "false", "no", "off")


def registrar_sessao_chrome(chromedriver_pid: int) -> Path:
    _SESSOES_DIR.mkdir(parents=True, exist_ok=True)
    lock = _SESSOES_DIR / f"{int(chromedriver_pid)}.lock"
    lock.write_text(str(time.time()), encoding="utf-8")
    return lock


def _chromedriver_pid(driver) -> int | None:
    try:
        svc = getattr(driver, "service", None)
        proc = getattr(svc, "process", None) if svc else None
        if proc and proc.pid:
            return int(proc.pid)
    except Exception:
        pass
    return getattr(driver, "_bi_chromedriver_pid", None)


def _matar_arvore(pid: int) -> bool:
    if pid <= 1:
        return False
    try:
        out = subprocess.check_output(
            ["pgrep", "-P", str(pid)],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        for linha in out.split():
            linha = linha.strip()
            if linha.isdigit():
                _matar_arvore(int(linha))
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        pass
    except Exception:
        pass
    try:
        os.kill(int(pid), signal.SIGKILL)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


def _remover_perfil(driver) -> None:
    pasta = getattr(driver, "_bi_user_data_dir", None)
    if not pasta:
        return
    try:
        shutil.rmtree(pasta, ignore_errors=True)
    except OSError:
        pass


def _remover_lock(driver) -> None:
    lock = getattr(driver, "_bi_chrome_lock", None)
    if lock:
        try:
            Path(lock).unlink(missing_ok=True)
        except OSError:
            pass
    pid = _chromedriver_pid(driver)
    if pid:
        try:
            (_SESSOES_DIR / f"{pid}.lock").unlink(missing_ok=True)
        except OSError:
            pass


def encerrar_driver_chrome(driver, apartamento_id: int | None = None) -> None:
    """Fecha o WebDriver e mata chromedriver/chrome filhos que sobrarem."""
    if driver is None:
        return
    pid = _chromedriver_pid(driver)
    try:
        driver.quit()
    except Exception:
        pass
    try:
        svc = getattr(driver, "service", None)
        if svc:
            svc.stop()
    except Exception:
        pass
    if sys.platform.startswith("linux") and pid:
        _matar_arvore(int(pid))
    _remover_lock(driver)
    _remover_perfil(driver)
    if apartamento_id is not None:
        try:
            from app.data import database as db

            db.logar_progresso(apartamento_id, "Navegador Chrome encerrado.")
        except Exception:
            pass


def _listar_chromedriver_pids() -> list[int]:
    if not sys.platform.startswith("linux"):
        return []
    try:
        out = subprocess.check_output(
            ["pgrep", "-f", r"chromedriver"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=8,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return []
    pids: list[int] = []
    for linha in out.split():
        linha = linha.strip()
        if linha.isdigit():
            pids.append(int(linha))
    return pids


def _ppid(pid: int) -> int | None:
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="replace")
        # comm pode conter espaços entre parênteses; ppid é o 4º campo após ')'
        after = stat.rsplit(")", 1)[-1].strip().split()
        return int(after[1])
    except (OSError, IndexError, ValueError):
        return None


def _idade_segundos(pid: int) -> float:
    try:
        return max(0.0, time.time() - Path(f"/proc/{pid}").stat().st_mtime)
    except OSError:
        return 0.0


def _lock_ativo(pid: int, max_idade: float) -> bool:
    lock = _SESSOES_DIR / f"{pid}.lock"
    if not lock.is_file():
        return False
    try:
        return (time.time() - lock.stat().st_mtime) < max_idade
    except OSError:
        return False


def limpar_chrome_orfaos(max_idade_seg: int | None = None) -> dict:
    """
    Remove chromedriver/chrome headless órfãos ou com sessão expirada.
    Seguro: não mata processos com lock de sessão recente.
    """
    if not sys.platform.startswith("linux") or not robo_cleanup_habilitado():
        return {"removidos": 0, "pids": []}

    max_idade = float(max_idade_seg if max_idade_seg is not None else _max_idade_segundos())
    removidos: list[int] = []

    _SESSOES_DIR.mkdir(parents=True, exist_ok=True)
    for lock in list(_SESSOES_DIR.glob("*.lock")):
        try:
            pid = int(lock.stem)
        except ValueError:
            lock.unlink(missing_ok=True)
            continue
        if _lock_ativo(pid, max_idade):
            continue
        if _matar_arvore(pid):
            removidos.append(pid)
        lock.unlink(missing_ok=True)

    meu_pid = os.getpid()
    for pid in _listar_chromedriver_pids():
        if pid == meu_pid:
            continue
        if _lock_ativo(pid, max_idade):
            continue
        ppid = _ppid(pid)
        idade = _idade_segundos(pid)
        if idade < max_idade and ppid not in (None, 1):
            continue
        if _matar_arvore(pid):
            removidos.append(pid)
            (_SESSOES_DIR / f"{pid}.lock").unlink(missing_ok=True)

    # Chrome headless sem chromedriver pai (zumbi)
    try:
        out = subprocess.check_output(
            ["pgrep", "-f", r"chrome.*--headless"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=8,
        )
        for linha in out.split():
            if not linha.strip().isdigit():
                continue
            pid = int(linha.strip())
            if pid == meu_pid:
                continue
            if _idade_segundos(pid) >= max_idade or _ppid(pid) in (None, 1):
                if _matar_arvore(pid):
                    removidos.append(pid)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        pass

    removidos = sorted(set(removidos))
    if removidos:
        print(f"[chrome-cleanup] encerrados {len(removidos)} processo(s): {removidos}")
    return {"removidos": len(removidos), "pids": removidos}


def limpar_perfis_antigos(max_idade_seg: int | None = None) -> int:
    """Remove pastas de perfil Chrome antigas em /tmp/biweb-chrome-profiles."""
    base = Path(os.getenv("BIWEB_CHROME_PROFILE_DIR", "/tmp/biweb-chrome-profiles"))
    if not base.is_dir():
        return 0
    max_idade = float(max_idade_seg if max_idade_seg is not None else _max_idade_segundos())
    removidos = 0
    agora = time.time()
    for child in base.iterdir():
        if not child.is_dir():
            continue
        try:
            if agora - child.stat().st_mtime > max_idade:
                shutil.rmtree(child, ignore_errors=True)
                removidos += 1
        except OSError:
            pass
    return removidos
