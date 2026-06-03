# worker.py (VERSÃO COM ATUALIZAÇÃO DIÁRIA COMPLETA)
import os
import redis
from rq import Worker, Queue, Connection
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from sqlalchemy import text

import app as main_app
import database as db
import logic
from tenant import ensure_transportadora

from dotenv import load_dotenv
load_dotenv()

listen = ['high', 'default', 'low']
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
conn = redis.from_url(redis_url)


def check_and_run_live_robots():
    print(f"[{datetime.now()}] Worker (Live): Verificando robôs em tempo real...")
    with main_app.app.app_context():
        pass


def schedule_robot_check():
    q = Queue(connection=conn)
    q.enqueue(check_and_run_live_robots, job_timeout=1800)


def run_daily_full_sync():
    """
    Atualização diária do banco SATI para a transportadora desta instalação.
    """
    print(f"[{datetime.now()}] Worker (Diário): INICIANDO ATUALIZAÇÃO SATI.")
    with main_app.app.app_context():
        try:
            tid = ensure_transportadora()
            with db.engine.connect() as connection:
                row = connection.execute(
                    text("""
                        SELECT valor FROM configuracoes_robo
                        WHERE apartamento_id = :tid AND chave = 'live_monitoring_enabled'
                    """),
                    {"tid": tid},
                ).first()
                if not row or str(row[0]).lower() not in ("true", "1", "yes", "on"):
                    print(
                        f"[{datetime.now()}] Worker (Diário): Monitoramento desativado "
                        f"(transportadora ID {tid})."
                    )
                    return

            print(f"--> Worker (Diário): Atualizando banco SATI (transportadora ID {tid})")
            q = Queue(connection=conn)
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
    scheduler.add_job(schedule_daily_sync, 'cron', hour=18, minute=0)
    scheduler.start()
    print("Agendador de tarefas (APScheduler) iniciado com duas rotinas: 'Live' e 'Diária'.")

    with Connection(conn):
        worker = Worker(map(Queue, listen))
        print("Worker (RQ) iniciado e escutando a fila...")
        worker.work()
