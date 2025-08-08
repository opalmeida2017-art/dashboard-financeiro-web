# logic.py
import data_manager as dm
import database as db
import os
import config

# --- Funções do Dashboard ---
def get_dashboard_summary(start_date=None, end_date=None, placa_filter="Todos", filial_filter="Todos"):
    return dm.get_dashboard_summary(start_date, end_date, placa_filter, filial_filter)

def get_monthly_summary(start_date=None, end_date=None, placa_filter="Todos", filial_filter="Todos"):
    return dm.get_monthly_summary(start_date, end_date, placa_filter, filial_filter)

def get_unique_plates():
    return dm.get_unique_plates()

def get_unique_filiais():
    return dm.get_unique_filiais()

# --- Funções de Gerenciamento de Grupo ---
def sync_expense_groups():
    """Ponte para a função de sincronização de grupos."""
    return dm.sync_expense_groups()

def get_all_expense_groups():
    return dm.get_all_expense_groups()

def get_all_group_flags():
    return dm.get_all_group_flags()

def update_all_group_flags(form_data):
    return dm.update_all_group_flags(form_data)

# --- Funções de Importação ---
def import_single_excel_to_db(excel_source, file_key):
    """Ponte para a função de importação de arquivo único."""
    return db.import_single_excel_to_db(excel_source, file_key)

def _import_all_data():
    """Função auxiliar para a rota de importação antiga (lê do repositório)."""
    base_path = os.path.dirname(os.path.abspath(__file__))
    for file_info in config.EXCEL_FILES_CONFIG.values():
        excel_path = os.path.join(base_path, file_info["path"])
        if os.path.exists(excel_path):
            print(f"-> Importando '{excel_path}'...")
            db.import_excel_to_db(excel_path, file_info["sheet_name"], file_info["table_name"])
        else:
            render_path = os.path.join("/app", file_info["path"])
            if os.path.exists(render_path):
                print(f"-> Importando '{render_path}' (ambiente Render)...")
                db.import_excel_to_db(render_path, file_info["sheet_name"], file_info["table_name"])
            else:
                print(f"-> AVISO: Arquivo '{file_info['path']}' não encontrado, importação ignorada.")
    print("--- IMPORTAÇÃO DE DADOS (DO REPOSITÓRIO) CONCLUÍDA. ---")

# logic.py (adicione esta função)

def get_faturamento_details_dashboard_data(start_date, end_date, placa_filter, filial_filter):
    return dm.get_faturamento_details_dashboard_data(start_date, end_date, placa_filter, filial_filter)

# logic.py (adicione estas funções)

def ler_configuracoes_robo():
    return dm.ler_configuracoes_robo()

def salvar_configuracoes_robo(configs: dict):
    return dm.salvar_configuracoes_robo(configs)

def processar_downloads_na_pasta():
    return db.processar_downloads_na_pasta()