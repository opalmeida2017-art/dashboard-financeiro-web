# -*- coding: utf-8 -*-
"""
Lista do fluxo de viagem persistida + robôs em ociosidade (anexos + BD SATI).
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

try:
    from app.utils.paths import downloads_dir
except ImportError:
    downloads_dir = None  # type: ignore


def _pasta_apartamento(apartamento_id: int) -> str:
    if downloads_dir is not None:
        return str(downloads_dir(apartamento_id))
    base = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "downloads",
        str(apartamento_id),
    )
    os.makedirs(base, exist_ok=True)
    return base


def _path_lista_fluxo(apartamento_id: int) -> str:
    return os.path.join(_pasta_apartamento(apartamento_id), "fluxo_lista_salva.json")


def _path_atividade(apartamento_id: int) -> str:
    return os.path.join(_pasta_apartamento(apartamento_id), "atividade_sistema.json")


def _path_estado_ocioso(apartamento_id: int) -> str:
    return os.path.join(_pasta_apartamento(apartamento_id), "idle_robo_estado.json")


def _path_lock_ocioso(apartamento_id: int) -> str:
    return os.path.join(_pasta_apartamento(apartamento_id), "idle_robo.lock")


def _ler_json(path: str, default: dict) -> dict:
    if not os.path.isfile(path):
        return dict(default)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else dict(default)
    except (json.JSONDecodeError, OSError):
        return dict(default)


def _gravar_json(path: str, payload: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def registrar_atividade(apartamento_id: int, *, origem: str = "http") -> None:
    """Marca que o usuário/sistema está em uso (não ocioso)."""
    path = _path_atividade(apartamento_id)
    payload = {
        "ultima_atividade": datetime.now().isoformat(timespec="seconds"),
        "origem": origem,
    }
    _gravar_json(path, payload)


def minutos_desde_ultima_atividade(apartamento_id: int) -> float | None:
    path = _path_atividade(apartamento_id)
    data = _ler_json(path, {})
    raw = data.get("ultima_atividade")
    if not raw:
        return None
    try:
        ts = datetime.fromisoformat(str(raw))
        return (datetime.now() - ts).total_seconds() / 60.0
    except ValueError:
        return None


def _serializar_row_fluxo(row: dict) -> dict:
    return {
        "placa": row.get("placa"),
        "numero": row.get("numero"),
        "numero_exibicao": row.get("numero_exibicao"),
        "motorista": row.get("motorista"),
        "data_dia": row.get("data_dia"),
        "linha_descarga": row.get("linha_descarga"),
        "precisa_coletar_comprovante": bool(row.get("precisa_coletar_comprovante")),
        "numeros_coleta_comprovante": list(row.get("numeros_coleta_comprovante") or []),
        "status_comprovante_descarga": row.get("status_comprovante_descarga"),
    }


def salvar_lista_fluxo(
    apartamento_id: int,
    rows: list[dict],
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    modo: str = "lista",
    numeros_pendentes: list[int] | None = None,
) -> str:
    """Persiste a lista exibida no fluxo de viagem para uso em ociosidade."""
    if numeros_pendentes is None:
        try:
            from app.data import data_manager as dm

            numeros_pendentes = dm.coletar_numeros_pendentes_comprovante(rows)
        except Exception:
            numeros_pendentes = []

    payload = {
        "salvo_em": datetime.now().isoformat(timespec="seconds"),
        "start_date": start_date or "",
        "end_date": end_date or "",
        "modo": modo,
        "numeros_pendentes_coleta": sorted(set(int(n) for n in numeros_pendentes)),
        "viagens": [_serializar_row_fluxo(r) for r in (rows or [])],
    }
    path = _path_lista_fluxo(apartamento_id)
    _gravar_json(path, payload)
    return path


def carregar_lista_fluxo(apartamento_id: int) -> dict:
    return _ler_json(_path_lista_fluxo(apartamento_id), {"viagens": [], "numeros_pendentes_coleta": []})


def atualizar_pendentes_da_lista_salva(apartamento_id: int) -> list[int]:
    """Recalcula CT-es pendentes com dados atuais do SATI (mesmo período salvo)."""
    from app.data import data_manager as dm

    salva = carregar_lista_fluxo(apartamento_id)
    start_s = (salva.get("start_date") or "").strip()
    end_s = (salva.get("end_date") or "").strip()
    if not start_s or not end_s:
        return list(salva.get("numeros_pendentes_coleta") or [])

    try:
        inicio = datetime.strptime(start_s, "%Y-%m-%d")
        fim = datetime.strptime(end_s, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    except ValueError:
        return list(salva.get("numeros_pendentes_coleta") or [])

    rows = dm.get_fluxo_veiculos_resumo(apartamento_id, inicio, fim, filial_filter=[])
    numeros = dm.coletar_numeros_pendentes_comprovante(rows)
    salvar_lista_fluxo(
        apartamento_id,
        rows,
        start_date=start_s,
        end_date=end_s,
        modo="lista",
        numeros_pendentes=numeros,
    )
    return numeros


def _lock_painel_ativo(apartamento_id: int) -> bool:
    try:
        from robos.coletor_painel_documentos import lock_painel_em_execucao

        return lock_painel_em_execucao(apartamento_id)
    except Exception:
        path = os.path.join(_pasta_apartamento(apartamento_id), "painel_documentos_robo.lock")
        return os.path.isfile(path)


def _restore_sati_em_andamento() -> bool:
    try:
        tenant_path = os.getenv("BI_TENANT_DIR", "").strip()
        if tenant_path:
            return Path(tenant_path, "sati_restore.lock").exists()
        from app.utils.paths import data_root

        return (data_root() / "sati_restore.lock").exists()
    except Exception:
        return os.path.isfile(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "sati_restore.lock")
        )


def _adquirir_lock_ocioso(apartamento_id: int) -> bool:
    path = _path_lock_ocioso(apartamento_id)
    if os.path.isfile(path):
        try:
            idade = time.time() - os.path.getmtime(path)
            if idade < 3 * 3600:
                return False
            os.remove(path)
        except OSError:
            return False
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
        return True
    except OSError:
        return False


def _liberar_lock_ocioso(apartamento_id: int) -> None:
    try:
        os.remove(_path_lock_ocioso(apartamento_id))
    except OSError:
        pass


def _minutos_idle_necessarios() -> int:
    try:
        return max(2, int(os.getenv("BIWEB_IDLE_MINUTES", "5")))
    except ValueError:
        return 5


def _minutos_entre_execucoes_ociosas() -> int:
    try:
        return max(10, int(os.getenv("BIWEB_IDLE_COOLDOWN_MINUTES", "30")))
    except ValueError:
        return 30


def _monitor_ocioso_habilitado(apartamento_id: int) -> bool:
    """Ligado por padrão; desligue com BIWEB_IDLE_MONITOR=false no .env."""
    return os.getenv("BIWEB_IDLE_MONITOR", "true").lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _ultima_execucao_ociosa(apartamento_id: int) -> datetime | None:
    data = _ler_json(_path_estado_ocioso(apartamento_id), {})
    raw = data.get("ultima_execucao")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw))
    except ValueError:
        return None


def _registrar_execucao_ociosa(apartamento_id: int, resultado: dict) -> None:
    payload = {
        "ultima_execucao": datetime.now().isoformat(timespec="seconds"),
        "resultado": resultado,
    }
    _gravar_json(_path_estado_ocioso(apartamento_id), payload)


def sistema_ocioso(apartamento_id: int) -> bool:
    minutos = minutos_desde_ultima_atividade(apartamento_id)
    if minutos is None:
        return True
    return minutos >= _minutos_idle_necessarios()


def executar_tarefas_ociosas(
    apartamento_id: int, tenant_slug: str | None = None
) -> dict:
    """
    Em ociosidade: atualiza BD SATI e busca comprovantes pendentes da lista salva.
    """
    from app.data import database as db
    from app.core import logic
    from app.data import data_manager as dm

    resultado = {
        "status": "ignorado",
        "bd_sati": None,
        "comprovantes": None,
        "numeros": [],
        "mensagem": "",
    }

    if not _monitor_ocioso_habilitado(apartamento_id):
        resultado["mensagem"] = "Monitoramento ocioso desativado (live_monitoring_enabled)."
        return resultado

    if not sistema_ocioso(apartamento_id):
        resultado["mensagem"] = "Sistema em uso — aguardando ociosidade."
        return resultado

    ultima = _ultima_execucao_ociosa(apartamento_id)
    if ultima and datetime.now() - ultima < timedelta(minutes=_minutos_entre_execucoes_ociosas()):
        resultado["mensagem"] = "Cooldown entre execuções ociosas ainda ativo."
        return resultado

    if _lock_painel_ativo(apartamento_id) or _restore_sati_em_andamento():
        resultado["mensagem"] = "Outro robô já em execução (painel ou restore SATI)."
        return resultado

    if not _adquirir_lock_ocioso(apartamento_id):
        resultado["mensagem"] = "Tarefa ociosa já em andamento."
        return resultado

    try:
        if not dm.robo_credenciais_configuradas(logic.ler_configuracoes_robo(apartamento_id)):
            resultado["status"] = "erro"
            resultado["mensagem"] = "Credenciais do robô SATI não configuradas."
            return resultado

        db.logar_progresso(
            apartamento_id,
            "Sistema ocioso — iniciando atualização do banco SATI…",
        )
        ok_bd = logic.executar_atualizacao_bd_sati(
            apartamento_id, tenant_slug=tenant_slug
        )
        resultado["bd_sati"] = "ok" if ok_bd else "erro"
        dm.clear_data_cache(apartamento_id)

        pendentes = atualizar_pendentes_da_lista_salva(apartamento_id)
        resultado["numeros"] = pendentes

        from app.core.logic import coleta_comprovante_automatica_habilitada

        if pendentes and coleta_comprovante_automatica_habilitada(apartamento_id):
            db.logar_progresso(
                apartamento_id,
                f"Sistema ocioso — buscando {len(pendentes)} comprovante(s): {pendentes}",
            )
            disp = logic.disparar_coleta_comprovantes_fluxo(
                apartamento_id,
                pendentes,
                baixar_pdfs=True,
            )
            resultado["comprovantes"] = disp.get("status")
            resultado["status"] = "sucesso" if ok_bd else "parcial"
            resultado["mensagem"] = (
                f"BD SATI: {'OK' if ok_bd else 'falhou'}; "
                f"comprovantes: {disp.get('mensagem', disp.get('status'))}"
            )
        elif pendentes:
            resultado["comprovantes"] = "auto_desativada"
            resultado["status"] = "sucesso" if ok_bd else "parcial"
            resultado["mensagem"] = (
                f"BD SATI: {'OK' if ok_bd else 'falhou'}; "
                f"coleta automática de comprovantes desativada ({len(pendentes)} pendente(s))."
            )
        else:
            resultado["comprovantes"] = "nada_pendente"
            resultado["status"] = "sucesso" if ok_bd else "erro"
            resultado["mensagem"] = (
                "BD SATI atualizado." if ok_bd else "Falha na atualização do BD SATI."
            ) + " Nenhum comprovante pendente na lista salva."

        _registrar_execucao_ociosa(apartamento_id, resultado)
        return resultado

    except Exception as e:
        resultado["status"] = "erro"
        resultado["mensagem"] = str(e)
        db.logar_progresso(apartamento_id, f"ERRO tarefas ociosas: {e}")
        _registrar_execucao_ociosa(apartamento_id, resultado)
        return resultado
    finally:
        _liberar_lock_ocioso(apartamento_id)


def verificar_e_executar_tarefas_ociosas(apartamento_id: int | None = None) -> dict | None:
    """Ponto de entrada para worker / agendador do Flask."""
    try:
        from infra.tenant_licensing.bi_tenant_runtime import (
            TENANTS_ROOT,
            prepare_robot_context,
        )
        from app.data.tenant import default_transportadora_id, ensure_transportadora
        from infra.tenant_licensing.bi_tenant_context import list_active_bi_tenants

        def _executar_um(
            slug: str | None, apt_painel: int | None
        ) -> dict:
            if slug:
                if not prepare_robot_context(
                    tenant_slug=slug, apartamento_id=apt_painel
                ):
                    return {
                        "status": "erro",
                        "mensagem": f"Contexto tenant '{slug}' indisponível.",
                    }
                tid = int(default_transportadora_id())
            else:
                tid = int(apt_painel or ensure_transportadora())
            return executar_tarefas_ociosas(tid, tenant_slug=slug)

        if apartamento_id is not None and not TENANTS_ROOT.is_dir():
            return _executar_um(None, apartamento_id)

        tenants = list_active_bi_tenants(max_apartamento=3)
        if tenants:
            resultados: dict[str, dict] = {}
            for item in tenants:
                slug = item["slug"]
                try:
                    resultados[slug] = _executar_um(slug, item.get("apartamento_id"))
                except Exception as exc:
                    resultados[slug] = {
                        "status": "erro",
                        "mensagem": str(exc),
                    }
            return {"multi_tenant": True, "tenants": resultados}

        return _executar_um(None, apartamento_id)
    except Exception:
        return None
