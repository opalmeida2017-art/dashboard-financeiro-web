# app.py
import os
from flask import Flask, render_template, jsonify, request, redirect, url_for
from datetime import datetime
import logic  # Importa a nossa lógica de busca de dados
import database as db # Importa o database para a rota de importação
import config # Importa as configurações

# Cria a aplicação Flask
app = Flask(__name__)

# --- MANEIRA CORRETA DE CARREGAR A CONFIGURAÇÃO ---
# Carrega as variáveis do arquivo config.py para dentro da configuração do Flask
app.config.from_object(config)
# ---------------------------------------------------


# --- ROTA PRINCIPAL ---
@app.route('/')
def index():
    """
    Busca os dados do dashboard usando nossa função em logic.py
    e renderiza a página principal.
    """
    # Pega os filtros da URL
    placa = request.args.get('placa', 'Todos')
    filial = request.args.get('filial', 'Todos')
    start_date_str = request.args.get('start_date', '') # Pega a data inicial como texto
    end_date_str = request.args.get('end_date', '')   # Pega a data final como texto

    # Converte o texto das datas para objetos datetime do Python
    start_date_obj = None
    if start_date_str:
        start_date_obj = datetime.strptime(start_date_str, '%Y-%m-%d')

    end_date_obj = None
    if end_date_str:
        end_date_obj = datetime.strptime(end_date_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)

    # Busca o resumo dos dados já aplicando TODOS os filtros
    summary_data = logic.get_dashboard_summary(
        start_date=start_date_obj,
        end_date=end_date_obj,
        placa_filter=placa,
        filial_filter=filial
    )
    
    placas = logic.get_unique_plates()
    filiais = logic.get_unique_filiais()

    return render_template('index.html', 
                           summary=summary_data,
                           placas=placas,
                           filiais=filiais,
                           selected_placa=placa,
                           selected_filial=filial,
                           selected_start_date=start_date_str,
                           selected_end_date=end_date_str)


# --- ROTA DE GERENCIAMENTO DE GRUPOS ---
# Em app.py, substitua a rota gerenciar_grupos inteira
@app.route('/gerenciar-grupos', methods=['GET', 'POST'])
def gerenciar_grupos():
    """
    Página para visualizar e atualizar a classificação dos grupos de despesa.
    """
    if request.method == 'POST':
        all_groups = logic.get_all_expense_groups()
        update_data = {}
        for group in all_groups:
            # Verifica qual checkbox (ou nenhum) foi marcado para o grupo
            if f"{group}_custo" in request.form:
                update_data[group] = 'custo_viagem'
            elif f"{group}_despesa" in request.form:
                update_data[group] = 'despesa'
            else:
                update_data[group] = 'nenhum'
        
        logic.update_all_group_flags(update_data)
        return redirect(url_for('gerenciar_grupos'))

    # Para GET, a lógica continua a mesma
    flags = logic.get_all_group_flags()
    return render_template('gerenciar_grupos.html', flags=flags)


# --- API ENDPOINTS ---
@app.route('/api/monthly_summary')
def api_monthly_summary():
    """Endpoint de API que retorna o resumo mensal em JSON."""
    monthly_data = logic.get_monthly_summary(start_date=None, end_date=None, placa_filter="Todos", filial_filter="Todos")
    return jsonify(monthly_data.to_dict(orient='records'))


# --- ROTA SECRETA PARA IMPORTAÇÃO INICIAL DE DADOS ---
def _import_all_data():
    """Função auxiliar para importar dados de todos os arquivos Excel configurados."""
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
    print("--- IMPORTAÇÃO DE DADOS CONCLUÍDA. ---")


@app.route('/importar-dados-agora-12345')
def trigger_import():
    """Dispara a importação de dados para o banco de dados."""
    try:
        db.create_tables()
        _import_all_data()
        return "<h1>Importação de dados concluída com sucesso!</h1>"
    except Exception as e:
        return f"<h1>Ocorreu um erro durante a importação:</h1><p>{e}</p>"


# Bloco para rodar a aplicação localmente para testes
if __name__ == '__main__':
    app.run(debug=True, port=5001)