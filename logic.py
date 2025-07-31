# logic.py
# Este arquivo serve como uma ponte entre o app.py (web) e o data_manager.py (dados).

import data_manager as dm

def get_dashboard_summary(start_date=None, end_date=None, placa_filter="Todos", filial_filter="Todos"):
    """Pega o resumo do dashboard do data_manager."""
    return dm.get_dashboard_summary(start_date, end_date, placa_filter, filial_filter)

def get_monthly_summary(start_date=None, end_date=None, placa_filter="Todos", filial_filter="Todos"):
    """Pega o resumo mensal do data_manager."""
    return dm.get_monthly_summary(start_date, end_date, placa_filter, filial_filter)

def get_unique_plates():
    """Pega a lista de placas únicas do data_manager."""
    return dm.get_unique_plates()

def get_unique_filiais():
    """Pega a lista de filiais únicas do data_manager."""
    return dm.get_unique_filiais()

# Adicione estas funções no final de logic.py

def get_all_expense_groups():
    """Pega a lista de todos os grupos de despesa."""
    return dm.get_all_expense_groups()

def get_all_group_flags():
    """Pega as classificações (flags) de todos os grupos."""
    return dm.get_all_group_flags()

def update_all_group_flags(form_data):
    """Envia os dados do formulário para atualizar as flags."""
    return dm.update_all_group_flags(form_data)