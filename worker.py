# worker.py
import os
import redis
from rq import Worker, Queue, Connection
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from sqlalchemy import text

# --- Atenção: Importe as funções e objetos necessários ---
# Importa a sua aplicação Flask para ter o contexto do banco de dados
import app as main_app 
import database as db
import coletor_principal

# Carrega as variáveis de ambiente do arquivo .env (importante para o REDIS_URL)
from dotenv import load_dotenv
load_dotenv()

# Lista de filas que o worker vai escutar
listen = ['high', 'default', 'low']

# Pega a URL do Redis a partir das variáveis de ambiente
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
conn = redis.from_url(redis_url)

# --- TAREFA QUE O AGENDADOR VAI COLOCAR NA FILA ---
def check_and_run_live_robots():
    """
    Esta é a tarefa que o worker vai executar a cada minuto.
    Ela verifica quais clientes estão ativos e dispara os robôs para eles.
    """
    print(f"[{datetime.now()}] Worker: Verificando robôs agendados para execução...")
    # 'with app.app_context()' é crucial para que o código dentro da função
    # tenha acesso ao banco de dados e outras configurações do Flask.
    with main_app.app.app_context():
        try:
            with db.engine.connect() as connection:
                # Query para encontrar clientes ativos com a coleta em tempo real ligada
                two_minutes_ago = datetime.now() - timedelta(minutes=2)
                query = text("""
                    SELECT a.id FROM apartamentos a
                    JOIN configuracoes_robo cr ON a.id = cr.apartamento_id
                    JOIN tb_user_activity ua ON a.id = ua.apartamento_id
                    WHERE cr.live_monitoring_enabled = TRUE AND ua.last_seen_timestamp >= :time_limit
                """)
                clientes_para_rodar = connection.execute(query, {"time_limit": two_minutes_ago}).mappings().all()

                # Para cada cliente encontrado, dispara o orquestrador de robôs
                for cliente in clientes_para_rodar:
                    apartamento_id = cliente['id']
                    print(f"--> Worker: Disparando coleta em tempo real para o apartamento ID: {apartamento_id}")
                    # A execução síncrona aqui está correta, pois o worker já é um processo de background
                    coletor_principal.executar_todas_as_coletas(apartamento_id)

        except Exception as e:
            print(f"ERRO no worker ao verificar robôs: {e}")

# --- FUNÇÃO QUE O AGENDADOR VAI EXECUTAR ---
def schedule_robot_check():
    """
    Esta função é chamada a cada minuto pelo APScheduler.
    Sua única responsabilidade é colocar a tarefa principal na fila do RQ.
    """
    print(f"[{datetime.now()}] Agendador: Colocando tarefa de verificação na fila...")
    q = Queue(connection=conn)
    # Coloca a função 'check_and_run_live_robots' na fila para ser executada pelo worker
     q.enqueue(check_and_run_live_robots, job_timeout=1800)


# --- BLOCO PRINCIPAL DE EXECUÇÃO DO WORKER ---
if __name__ == '__main__':
    # 1. Inicia o agendador em um processo de fundo (daemon)
    scheduler = BackgroundScheduler(daemon=True)
    # Roda a função 'schedule_robot_check' a cada 1 minuto
    scheduler.add_job(schedule_robot_check, 'interval', minutes=1)
    scheduler.start()
    print("Agendador de tarefas (APScheduler) iniciado.")

    # 2. Inicia o worker para escutar a fila do Redis
    with Connection(conn):
        worker = Worker(map(Queue, listen))
        print("Worker (RQ) iniciado e escutando a fila...")
        worker.work()