# Forçando a atualização para o deploy
import data_manager as dm
import database as db
import os
import config
import psycopg2
from sqlalchemy import text




def get_dashboard_summary(apartamento_id: int, start_date=None, end_date=None, placa_filter="Todos", filial_filter="Todos"):
    print(f">>> [LOGIC] Chamando get_dashboard_summary para o apartamento ID: {apartamento_id}")
    summary_data = dm.get_dashboard_summary(apartamento_id, start_date, end_date, placa_filter, filial_filter)
    print(f"<<< [LOGIC] Retornando dados do summary: {'Dados calculados' if summary_data else 'Vazio'}")
    return summary_data

def get_monthly_summary(apartamento_id: int, start_date=None, end_date=None, placa_filter="Todos", filial_filter="Todos"):
    print(f">>> [LOGIC] Chamando get_monthly_summary para o apartamento ID: {apartamento_id}")
    monthly_data = dm.get_monthly_summary(apartamento_id, start_date, end_date, placa_filter, filial_filter)
    print(f"<<< [LOGIC] Retornando dados mensais: {'DataFrame com dados' if not monthly_data.empty else 'DataFrame vazio'}")
    return monthly_data

def get_unique_plates_with_types(apartamento_id: int):
    print(f">>> [LOGIC] Chamando get_unique_plates_with_types para o apartamento ID: {apartamento_id}")
    return dm.get_unique_plates_with_types(apartamento_id)

def get_unique_filiais(apartamento_id: int):
    print(f">>> [LOGIC] Chamando get_unique_filiais para o apartamento ID: {apartamento_id}")
    return dm.get_unique_filiais(apartamento_id)

# --- Funções de Gerenciamento de Grupo ---
def sync_expense_groups(apartamento_id: int):
    print(f">>> [LOGIC] Chamando sync_expense_groups para o apartamento ID: {apartamento_id}")
    return dm.sync_expense_groups(apartamento_id)

def get_all_expense_groups(apartamento_id: int):
    print(f">>> [LOGIC] Chamando get_all_expense_groups para o apartamento ID: {apartamento_id}")
    return dm.get_all_expense_groups(apartamento_id)

def get_all_group_flags(apartamento_id: int):
    print(f">>> [LOGIC] Chamando get_all_group_flags para o apartamento ID: {apartamento_id}")
    return dm.get_all_group_flags(apartamento_id)

def update_all_group_flags(apartamento_id: int, form_data):
    print(f">>> [LOGIC] Chamando update_all_group_flags para o apartamento ID: {apartamento_id}")
    return dm.update_all_group_flags(apartamento_id, form_data)

# --- Funções de Importação ---
def import_single_excel_to_db(excel_source, file_key, apartamento_id: int):
    print(f">>> [LOGIC] Chamando import_single_excel_to_db para o apartamento ID: {apartamento_id}")
    return db.import_single_excel_to_db(excel_source, file_key, apartamento_id)

def _import_all_data(apartamento_id: int):
    """Função auxiliar para importar um conjunto de arquivos do repositório para um apartamento específico."""
    print(f">>> [LOGIC] Chamando _import_all_data para o apartamento ID: {apartamento_id}")
    base_path = os.path.dirname(os.path.abspath(__file__))
    print(f"--- INICIANDO IMPORTAÇÃO DE DADOS PARA O APARTAMENTO ID: {apartamento_id} ---")
    
    for file_info in config.EXCEL_FILES_CONFIG.values():
        excel_path = os.path.join(base_path, file_info["path"])
        if os.path.exists(excel_path):
            print(f"-> Importando '{excel_path}'...")
            db.import_excel_to_db(excel_path, file_info["sheet_name"], file_info["table_name"], apartamento_id=apartamento_id)
        else:
            render_path = os.path.join("/app", file_info["path"])
            if os.path.exists(render_path):
                print(f"-> Importando '{render_path}' (ambiente Render)...")
                db.import_excel_to_db(render_path, file_info["sheet_name"], file_info["table_name"], apartamento_id=apartamento_id)
            else:
                print(f"-> AVISO: Arquivo '{file_info['path']}' não encontrado, importação ignorada.")
    print("--- IMPORTAÇÃO DE DADOS (DO REPOSITÓRIO) CONCLUÍDA. ---")

def get_faturamento_details_dashboard_data(apartamento_id: int, start_date, end_date, placa_filter, filial_filter):
    print(f">>> [LOGIC] Chamando get_faturamento_details_dashboard_data para o apartamento ID: {apartamento_id}")
    return dm.get_faturamento_details_dashboard_data(apartamento_id, start_date, end_date, placa_filter, filial_filter)

def get_despesas_details_dashboard_data(apartamento_id: int, start_date, end_date, placa_filter, filial_filter):
    print(f">>> [LOGIC] Chamando get_despesas_details_dashboard_data para o apartamento ID: {apartamento_id}")
    return dm.get_despesas_details_dashboard_data(apartamento_id, start_date, end_date, placa_filter, filial_filter)

# --- Funções de Configuração do Robô ---
def ler_configuracoes_robo(apartamento_id: int):
    print(f">>> [LOGIC] Chamando ler_configuracoes_robo para o apartamento ID: {apartamento_id}")
    return dm.ler_configuracoes_robo(apartamento_id)

def salvar_configuracoes_robo(apartamento_id: int, configs: dict):
    print(f">>> [LOGIC] Chamando salvar_configuracoes_robo para o apartamento ID: {apartamento_id}")
    return dm.salvar_configuracoes_robo(apartamento_id, configs)

def processar_downloads_na_pasta(apartamento_id: int):
    print(f">>> [LOGIC] Chamando processar_downloads_na_pasta para o apartamento ID: {apartamento_id}")
    return db.processar_downloads_na_pasta(apartamento_id)

# --- Função de Log de Atualizações (se mantida) ---
def get_last_updates():
    print(">>> [LOGIC] Chamando get_last_updates (função global)")
    return dm.get_last_updates()

def get_users_for_apartment(apartamento_id: int):
    return dm.get_users_for_apartment(apartamento_id)

def add_user_to_apartment(apartamento_id: int, nome: str, email: str, password_hash: str, role: str):
    return dm.add_user_to_apartment(apartamento_id, nome, email, password_hash, role)

def update_user_in_apartment(user_id: int, apartamento_id: int, nome: str, email: str, role: str, new_password_hash: str = None):
    return dm.update_user_in_apartment(user_id, apartamento_id, nome, email, role, new_password_hash)

def delete_user_from_apartment(user_id: int, apartamento_id: int):
    return dm.delete_user_from_apartment(user_id, apartamento_id)

def get_user_by_id(user_id: int, apartamento_id: int):
    return dm.get_user_by_id(user_id, apartamento_id)

def create_apartment_and_admin(nome_empresa: str, admin_nome: str, admin_email: str, password_hash: str):
    return dm.create_apartment_and_admin(nome_empresa, admin_nome, admin_email, password_hash)

def get_apartment_details(apartamento_id: int):
    return dm.get_apartment_details(apartamento_id)

def update_apartment_details(apartamento_id: int, nome_empresa: str, status: str, data_vencimento: str, notas: str):
    return dm.update_apartment_details(apartamento_id, nome_empresa, status, data_vencimento, notas)

def get_apartments_with_usage_stats():
    """Função de ponte para buscar apartamentos com estatísticas de uso."""
    print(">>> [LOGIC] Chamando get_apartments_with_usage_stats")
    return dm.get_apartments_with_usage_stats()

def get_apartment_by_slug(slug: str):
    """Função de ponte para buscar um apartamento pelo seu slug."""
    print(f">>> [LOGIC] Chamando get_apartment_by_slug para o slug: {slug}")
    # 'dm' é o alias para data_manager
    return dm.get_apartment_by_slug(slug)

def limpar_logs_antigos(apartamento_id):
    """Apaga os logs de uma execução anterior para um apartamento específico."""
    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                sql = "DELETE FROM tb_logs_robo WHERE apartamento_id = %s"
                cursor.execute(sql, (apartamento_id,))
        print(f"[LOG DB] Logs antigos para o apartamento {apartamento_id} foram limpos.")
    except Exception as e:
        print(f"ERRO ao limpar logs antigos: {e}")
        
def get_group_flags_with_tipo_d_status(apartamento_id: int):
    """Função de ponte para buscar flags de grupo com status de Tipo D."""
    print(f">>> [LOGIC] Chamando get_group_flags_with_tipo_d_status para o apartamento ID: {apartamento_id}")
    return dm.get_group_flags_with_tipo_d_status(apartamento_id)
        