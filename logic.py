# Forçando a atualização para o deploy
import database as db
import data_manager as dm
import psycopg2
from sqlalchemy import text
import database as db_module
import pandas as pd
import numpy as np
import datetime
import json
import calendar
from dateutil.relativedelta import relativedelta
from collections import defaultdict
import os
import psycopg2


def get_dashboard_summary(apartamento_id: int, start_date=None, end_date=None, placa_filter="Todos", filial_filter=None, tipo_negocio_filter="Todos"):
    print(f">>> [LOGIC] Chamando get_dashboard_summary para o apartamento ID: {apartamento_id}")
    summary_data = dm.get_dashboard_summary(apartamento_id, start_date, end_date, placa_filter, filial_filter, tipo_negocio_filter)
    print(f"<<< [LOGIC] Retornando dados do summary: {'Dados calculados' if summary_data else 'Vazio'}")
    return summary_data

def get_monthly_summary(apartamento_id: int, start_date=None, end_date=None, placa_filter="Todos", filial_filter=None, tipo_negocio_filter="Todos"):
    print(f">>> [LOGIC] Chamando get_monthly_summary para o apartamento ID: {apartamento_id}")
    monthly_data = dm.get_monthly_summary(apartamento_id, start_date, end_date, placa_filter, filial_filter, tipo_negocio_filter)
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

def get_faturamento_details_dashboard_data(apartamento_id: int, start_date, end_date, placa_filter, filial_filter, tipo_negocio_filter):
    print(f">>> [LOGIC] Chamando get_faturamento_details_dashboard_data para o apartamento ID: {apartamento_id}")
    return dm.get_faturamento_details_dashboard_data(apartamento_id, start_date, end_date, placa_filter, filial_filter, tipo_negocio_filter)

def get_despesas_details_dashboard_data(apartamento_id: int, start_date, end_date, placa_filter, filial_filter, tipo_negocio_filter):
    print(f">>> [LOGIC] Chamando get_despesas_details_dashboard_data para o apartamento ID: {apartamento_id}")
    return dm.get_despesas_details_dashboard_data(apartamento_id, start_date, end_date, placa_filter, filial_filter, tipo_negocio_filter)

def get_fluxo_viagem_data(apartamento_id: int, start_date, end_date, placa_filter, filial_filter=None):
    print(f">>> [LOGIC] Chamando get_fluxo_viagem_data para o apartamento ID: {apartamento_id}")
    return dm.get_fluxo_viagem_data(apartamento_id, start_date, end_date, placa_filter, filial_filter)

def get_fluxo_veiculos_resumo(apartamento_id: int, start_date, end_date, filial_filter=None):
    print(f">>> [LOGIC] Chamando get_fluxo_veiculos_resumo para o apartamento ID: {apartamento_id}")
    return dm.get_fluxo_veiculos_resumo(apartamento_id, start_date, end_date, filial_filter)

def get_fluxo_viagem_historico(apartamento_id: int, start_date, end_date, placa: str, filial_filter=None):
    print(f">>> [LOGIC] Chamando get_fluxo_viagem_historico placa={placa} apt={apartamento_id}")
    return dm.get_fluxo_viagem_historico(apartamento_id, start_date, end_date, placa, filial_filter)

def get_expense_audit_data(apartamento_id: int, start_date, end_date, placa_filter, filial_filter, tipo_negocio_filter):
    print(f">>> [LOGIC] Chamando get_expense_audit_data para o apartamento ID: {apartamento_id}")
    return dm.get_expense_audit_data(apartamento_id, start_date, end_date, placa_filter, filial_filter, tipo_negocio_filter)

def ler_configuracoes_robo(apartamento_id: int):
    print(f">>> [LOGIC] Chamando ler_configuracoes_robo para o apartamento ID: {apartamento_id}")
    return dm.ler_configuracoes_robo(apartamento_id)

def executar_atualizacao_bd_sati(apartamento_id: int) -> bool:
    """Robô: envio BI no SATI + download zip + restore PostgreSQL."""
    from robos.coletor_atualizacao_bd import executar_atualizacao_bd_sati

    print(f">>> [LOGIC] Atualização banco SATI apt={apartamento_id}")
    return bool(executar_atualizacao_bd_sati(apartamento_id))


def get_comprovante_descarga_payload(apartamento_id: int, numeros: list[int]) -> dict:
    from comprovante_descarga import itens_para_numeros

    itens = itens_para_numeros(apartamento_id, numeros)
    return {"itens": itens, "numeros": numeros}


def disparar_coleta_comprovantes_fluxo(
    apartamento_id: int,
    numeros_internos: list[int] | None = None,
    *,
    baixar_pdfs: bool = True,
) -> dict:
    """
    Enfileira (ou executa) o robô Painel de Documentos para CT-es pendentes no fluxo.
    """
    import data_manager as dm
    from comprovante_descarga import (
        filtrar_numeros_para_coleta_automatica,
        liberar_coleta_da_fila,
        registrar_coleta_em_fila,
    )

    if numeros_internos is None:
        numeros_internos = []
    pendentes = filtrar_numeros_para_coleta_automatica(apartamento_id, numeros_internos)
    if not pendentes:
        return {
            "status": "ignorado",
            "mensagem": "Nenhum CT-e pendente de coleta (já na fila ou já com arquivo).",
            "numeros": [],
        }

    configs = ler_configuracoes_robo(apartamento_id)
    if not dm.robo_credenciais_configuradas(configs):
        return {
            "status": "erro",
            "mensagem": "Credenciais do robô SATI não configuradas.",
            "numeros": pendentes,
        }

    registrar_coleta_em_fila(apartamento_id, pendentes)

    import os

    execution_mode = os.getenv("EXECUTION_MODE", "async")
    redis_url = os.getenv("REDIS_URL", "").strip()

    if execution_mode == "sync" or not redis_url:
        ok = executar_painel_documentos_sati(
            apartamento_id,
            numeros_internos=pendentes,
            baixar_pdfs=baixar_pdfs,
        )
        dm.clear_data_cache(apartamento_id)
        if not ok:
            liberar_coleta_da_fila(apartamento_id, pendentes)
        return {
            "status": "sucesso" if ok else "erro",
            "mensagem": "Coleta concluída." if ok else "Falha na coleta. Veja os logs.",
            "numeros": pendentes,
            "modo": "sync",
        }

    try:
        import redis
        from rq import Queue

        conn = redis.Redis.from_url(redis_url)
        q = Queue(connection=conn)
        q.enqueue(
            executar_painel_documentos_sati,
            apartamento_id,
            numeros_internos=pendentes,
            baixar_pdfs=baixar_pdfs,
            job_timeout=3600,
        )
        return {
            "status": "sucesso",
            "mensagem": f"Robô iniciado para {len(pendentes)} CT-e(s).",
            "numeros": pendentes,
            "modo": "async",
        }
    except Exception as e:
        return {
            "status": "erro",
            "mensagem": f"Fila indisponível: {e}",
            "numeros": pendentes,
        }


def resolver_arquivo_comprovante_descarga(apartamento_id: int, numero: int) -> str | None:
    from comprovante_descarga import resolver_caminho_arquivo

    return resolver_caminho_arquivo(apartamento_id, numero)


def executar_painel_documentos_sati(
    apartamento_id: int,
    *,
    data_ini: str | None = None,
    data_fim: str | None = None,
    numeros_internos: list[int] | None = None,
    baixar_pdfs: bool = True,
) -> bool:
    """Robô: Painéis → Painel de Documentos (comprovantes de descarga)."""
    from robos.coletor_painel_documentos import executar_painel_documentos_sati

    print(f">>> [LOGIC] Painel de Documentos SATI apt={apartamento_id}")
    return bool(
        executar_painel_documentos_sati(
            apartamento_id,
            data_ini=data_ini,
            data_fim=data_fim,
            numeros_internos=numeros_internos,
            baixar_pdfs=baixar_pdfs,
        )
    )


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
    conn = None
    user = None
    try:
        conn = db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, nome, email, role FROM usuarios WHERE id = %s AND apartamento_id = %s", (user_id, apartamento_id))
        user = cursor.fetchone()
        cursor.close()
    except psycopg2.Error as e:
        print(f"Erro ao obter dados do usuário: {e}")
    finally:
        if conn:
            conn.close()
    
    if user:
        return {"id": user[0], "nome": user[1], "email": user[2], "role": user[3]}
    return None

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

def get_despesas_por_filial_e_grupo(apartamento_id: int, start_date, end_date, filial_filter):
    print(f">>> [LOGIC] Chamando get_despesas_por_filial_e_grupo para o apartamento ID: {apartamento_id}")
    return dm.get_despesas_por_filial_e_grupo(apartamento_id, start_date, end_date, filial_filter)

def resolve_date_filters(apartamento_id: int, start_date=None, end_date=None):
    """Quando o usuário não informa datas, usa o intervalo das viagens (não vencimentos futuros)."""
    return dm.resolver_intervalo_consulta(apartamento_id, start_date, end_date)


def get_unique_negocios(apartamento_id: int):
    """Tipos de negócio: FROTA (próprio) e FRETE/AGENCIAMENTO (terceiro/agenciamento)."""
    print(f">>> [LOGIC] Chamando get_unique_negocios para o apartamento ID: {apartamento_id}")
    return dm.get_unique_negocios(apartamento_id)


def get_relatorio_viagem_data(apartamento_id: int, numero: int, dias_janela: int): # ALTERADO AQUI
    """
    Função de ponte para buscar os dados do relatório de viagem.
    """
    print(f">>> [LOGIC] Chamando get_relatorio_viagem_data para o CT-e: {numero} com janela de {dias_janela} dias")
    return dm.get_relatorio_viagem_data(apartamento_id, numero, dias_janela=dias_janela) # ALTERADO AQUI

def update_apartment_logo(apartment_id, logo_filename):
    conn = None
    try:
        conn = db.get_db_connection()
        cursor = conn.cursor()
        # Corrigido: Usar "apartamentos" em minúsculas e no plural
        cursor.execute("UPDATE apartamentos SET logo_filename = %s WHERE id = %s", (logo_filename, apartment_id))
        conn.commit()
        cursor.close()
    except psycopg2.Error as e:
        print(f"Erro ao atualizar logo do apartamento: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def get_apartment_logo(apartment_id):
    conn = None
    logo_filename = None
    try:
        conn = db.get_db_connection()
        cursor = conn.cursor()
        # Corrigido: Usar "apartamentos" em minúsculas e no plural
        cursor.execute("SELECT logo_filename FROM apartamentos WHERE id = %s", (apartment_id,))
        result = cursor.fetchone()
        if result:
            logo_filename = result[0]
        cursor.close()
    except psycopg2.Error as e:
        print(f"Erro ao obter logo do apartamento: {e}")
    finally:
        if conn:
            conn.close()
    return logo_filename


        