# worker.py (VERSÃO COM ATUALIZAÇÃO DIÁRIA COMPLETA)
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import redis
from rq import Worker, Queue, Connection
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from sqlalchemy import text

from app import app as main_app
from app.data import database as db
from app.core import logic
from app.data.tenant import ensure_transportadora

from dotenv import load_dotenv

load_dotenv()

listen = ['high', 'default', 'low']
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
conn = redis.from_url(redis_url)


def check_and_run_live_robots():
    print(f"[{datetime.now()}] Worker (Live): Verificando ociosidade / fluxo salvo...")
    with main_app.app_context():
        try:
            from infra.cloud.fluxo_monitor import verificar_e_executar_tarefas_ociosas

            resultado = verificar_e_executar_tarefas_ociosas()
            if resultado and resultado.get("status") not in ("ignorado",):
                print(f"[{datetime.now()}] Tarefas ociosas: {resultado}")
        except Exception as e:
            print(f"[{datetime.now()}] ERRO tarefas ociosas: {e}")


def schedule_robot_check():
    q = Queue(connection=conn)
    q.enqueue(check_and_run_live_robots, job_timeout=1800)


def cleanup_zombie_chrome():
    with main_app.app_context():
        try:
            from sati_integration.robos.chrome_cleanup import (
                limpar_chrome_orfaos,
                limpar_perfis_antigos,
            )

            limpar_chrome_orfaos()
            limpar_perfis_antigos()
        except Exception as e:
            print(f"[{datetime.now()}] ERRO chrome-cleanup: {e}")


def schedule_chrome_cleanup():
    q = Queue(connection=conn)
    q.enqueue(cleanup_zombie_chrome, job_timeout=120)


def _monitoramento_ativo(tid: int) -> bool:
    with db.engine.connect() as connection:
        row = connection.execute(
            text("""
                SELECT valor FROM configuracoes_robo
                WHERE apartamento_id = :tid AND chave = 'live_monitoring_enabled'
            """),
            {"tid": tid},
        ).first()
    return bool(row and str(row[0]).lower() in ("true", "1", "yes", "on"))


def run_daily_full_sync():
    """Atualização diária do banco SATI para cada tenant BI ativo (apt 1–3)."""
    print(f"[{datetime.now()}] Worker (Diário): INICIANDO ATUALIZAÇÃO SATI.")
    with main_app.app_context():
        try:
            from infra.tenant_licensing.bi_tenant_context import list_active_bi_tenants
            from infra.tenant_licensing.bi_tenant_runtime import (
                TENANTS_ROOT,
                prepare_robot_context,
            )
            from app.data.tenant import default_transportadora_id

            q = Queue(connection=conn)
            tenants = (
                list_active_bi_tenants(max_apartamento=3)
                if TENANTS_ROOT.is_dir()
                else []
            )

            if tenants:
                for item in tenants:
                    slug = item["slug"]
                    apt_painel = item.get("apartamento_id")
                    if not prepare_robot_context(
                        tenant_slug=slug, apartamento_id=apt_painel
                    ):
                        print(
                            f"[{datetime.now()}] Worker (Diário): tenant '{slug}' "
                            "sem contexto — ignorado."
                        )
                        continue
                    tid = int(default_transportadora_id())
                    if not _monitoramento_ativo(tid):
                        print(
                            f"[{datetime.now()}] Worker (Diário): monitoramento desativado "
                            f"(tenant {slug}, apt {tid})."
                        )
                        continue
                    print(
                        f"--> Worker (Diário): SATI tenant={slug} apt={tid}"
                    )
                    q.enqueue(
                        logic.executar_atualizacao_bd_sati,
                        tid,
                        tenant_slug=slug,
                        job_timeout=7200,
                    )
                return

            tid = ensure_transportadora()
            if not _monitoramento_ativo(tid):
                print(
                    f"[{datetime.now()}] Worker (Diário): Monitoramento desativado "
                    f"(transportadora ID {tid})."
                )
                return

            print(f"--> Worker (Diário): Atualizando banco SATI (transportadora ID {tid})")
            q.enqueue(logic.executar_atualizacao_bd_sati, tid, job_timeout=7200)

        except Exception as e:
            print(f"ERRO CRÍTICO no worker (Diário): {e}")


def schedule_daily_sync():
    print(f"[{datetime.now()}] Agendador: Colocando tarefa de sincronização diária na fila...")
    q = Queue(connection=conn)
    q.enqueue(run_daily_full_sync, job_timeout=3600)


if __name__ == '__main__':
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(schedule_robot_check, 'interval', minutes=1)
    try:
        chrome_min = max(5, int(os.getenv("BIWEB_CHROME_CLEANUP_MINUTES", "15")))
    except ValueError:
        chrome_min = 15
    if sys.platform.startswith("linux") and os.getenv(
        "BIWEB_CHROME_CLEANUP", "true"
    ).lower() not in ("0", "false", "no", "off"):
        scheduler.add_job(schedule_chrome_cleanup, "interval", minutes=chrome_min)
    scheduler.add_job(schedule_daily_sync, 'cron', hour=18, minute=0)
    scheduler.start()
    print("Agendador de tarefas (APScheduler) iniciado com duas rotinas: 'Live' e 'Diária'.")

    with Connection(conn):
        worker = Worker(map(Queue, listen))
        print("Worker (RQ) iniciado e escutando a fila...")
        worker.work()
