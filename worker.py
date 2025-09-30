# worker.py (VERSÃO COM ATUALIZAÇÃO DIÁRIA COMPLETA)
import os
import redis
from rq import Worker, Queue, Connection
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from sqlalchemy import text
import calendar

# --- Importações necessárias ---
import app as main_app 
import database as db
import coletor_principal

from dotenv import load_dotenv
load_dotenv()

listen = ['high', 'default', 'low']
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
conn = redis.from_url(redis_url)

# --- TAREFA 1: Verificação da coleta em tempo real (lógica existente) ---
def check_and_run_live_robots():
    print(f"[{datetime.now()}] Worker (Live): Verificando robôs em tempo real...")
    with main_app.app.app_context():
        # ... (sua lógica existente para coleta em tempo real permanece aqui) ...
        pass

def schedule_robot_check():
    q = Queue(connection=conn)
    q.enqueue(check_and_run_live_robots, job_timeout=1800)

# --- TAREFA 2: Nova rotina de sincronização diária completa ---
def run_daily_full_sync():
    """
    Busca apartamentos elegíveis e dispara a coleta mensal para o ano corrente.
    """
    print(f"[{datetime.now()}] Worker (Diário): INICIANDO ROTINA DE SINCRONIZAÇÃO COMPLETA.")
    with main_app.app.app_context():
        try:
            with db.engine.connect() as connection:
                # Query para encontrar apartamentos com a coleta ativada e intervalo definido
                query = text("""
                    SELECT a.id FROM apartamentos a
                    JOIN configuracoes_robo cr_live ON a.id = cr_live.apartamento_id AND cr_live.chave = 'live_monitoring_enabled'
                    JOIN configuracoes_robo cr_interval ON a.id = cr_interval.apartamento_id AND cr_interval.chave = 'live_monitoring_interval_minutes'
                    WHERE cr_live.valor = 'True' AND cr_interval.valor != '' AND cr_interval.valor IS NOT NULL;
                """)
                apartamentos_elegiveis = connection.execute(query).mappings().all()

                if not apartamentos_elegiveis:
                    print(f"[{datetime.now()}] Worker (Diário): Nenhum apartamento elegível encontrado para a sincronização completa.")
                    return

                hoje = datetime.now()
                ano_corrente = hoje.year
                mes_corrente = hoje.month

                for apt in apartamentos_elegiveis:
                    apartamento_id = apt['id']
                    print(f"--> Worker (Diário): Iniciando sincronização para o Apartamento ID: {apartamento_id}")
                    
                    # Loop de Janeiro até o mês atual
                    for mes in range(1, mes_corrente + 1):
                        # Calcula o primeiro e o último dia do mês
                        primeiro_dia = datetime(ano_corrente, mes, 1)
                        ultimo_dia_num = calendar.monthrange(ano_corrente, mes)[1]
                        ultimo_dia = datetime(ano_corrente, mes, ultimo_dia_num)

                        start_date_str = primeiro_dia.strftime('%d/%m/%Y')
                        end_date_str = ultimo_dia.strftime('%d/%m/%Y')
                        
                        print(f"    -> Enfileirando coleta para o mês {mes}/{ano_corrente} (Período: {start_date_str} a {end_date_str})")
                        
                        # Enfileira a tarefa no Redis para o worker executar
                        q = Queue(connection=conn)
                        q.enqueue(
                            coletor_principal.executar_todas_as_coletas,
                            apartamento_id,
                            start_date_str=start_date_str,
                            end_date_str=end_date_str,
                            job_timeout=3600 # Timeout maior para tarefas mais longas
                        )

        except Exception as e:
            print(f"ERRO CRÍTICO no worker (Diário) ao verificar apartamentos: {e}")

def schedule_daily_sync():
    """Função que o agendador chama para colocar a tarefa diária na fila."""
    print(f"[{datetime.now()}] Agendador: Colocando tarefa de sincronização diária na fila...")
    q = Queue(connection=conn)
    q.enqueue(run_daily_full_sync, job_timeout=3600)

# --- BLOCO PRINCIPAL DE EXECUÇÃO DO WORKER ---
if __name__ == '__main__':
    scheduler = BackgroundScheduler(daemon=True)
    
    # Agendador 1: Roda a verificação em tempo real a cada 1 minuto (existente)
    scheduler.add_job(schedule_robot_check, 'interval', minutes=1)
    
    # Agendador 2: Roda a sincronização completa todos os dias às 18:00 (NOVO)
    scheduler.add_job(schedule_daily_sync, 'cron', hour=18, minute=0)
    
    scheduler.start()
    print("Agendador de tarefas (APScheduler) iniciado com duas rotinas: 'Live' e 'Diária'.")

    with Connection(conn):
        worker = Worker(map(Queue, listen))
        print("Worker (RQ) iniciado e escutando a fila...")
        worker.work()