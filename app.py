import os
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
from datetime import datetime
import logic
import database as db
import config

app = Flask(__name__)
app.config['SECRET_KEY'] = 'uma-chave-secreta-muito-dificil-de-adivinhar'

# --- FILTROS PERSONALIZADOS PARA FORMATAÇÃO ---
@app.template_filter('currency')
def format_currency(value):
    """Formata um número como moeda no padrão brasileiro (R$ 1.234,56)."""
    if value is None or not isinstance(value, (int, float)):
        return "R$ 0,00"
    formatted_value = f"{value:,.2f}"
    formatted_value = formatted_value.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted_value}"

@app.template_filter('percentage')
def format_percentage(value):
    """Formata um número como porcentagem no padrão brasileiro (12,34%)."""
    if value is None or not isinstance(value, (int, float)):
        return "0,00%"
    formatted_value = f"{value:.2f}"
    formatted_value = formatted_value.replace(".", ",")
    return f"{formatted_value}%"
# --- FIM DOS FILTROS ---

# --- CRIAÇÃO DAS TABELAS NO INÍCIO ---
print("Verificando e garantindo que todas as tabelas do banco de dados existam...")
db.create_tables()
print("Verificação do banco de dados concluída.")
# ----------------------------------------

FILENAME_TO_KEY_MAP = {info['path']: key for key, info in config.EXCEL_FILES_CONFIG.items()}

# --- NOVA FUNÇÃO AJUDANTE PARA CENTRALIZAR A LÓGICA DE FILTROS ---
def _parse_filters():
    """Lê os filtros da URL e retorna um dicionário com os valores processados."""
    filters = {
        'placa': request.args.get('placa', 'Todos'),
        'filial': request.args.get('filial', 'Todos'),
        'start_date_str': request.args.get('start_date', ''),
        'end_date_str': request.args.get('end_date', '')
    }
    filters['start_date_obj'] = datetime.strptime(filters['start_date_str'], '%Y-%m-%d') if filters['start_date_str'] else None
    filters['end_date_obj'] = datetime.strptime(filters['end_date_str'], '%Y-%m-%d').replace(hour=23, minute=59, second=59) if filters['end_date_str'] else None
    return filters

@app.route('/upload', methods=['POST'])
def upload_file():
    # ... (código inalterado) ...
    uploaded_files = request.files.getlist('files[]')
    if not uploaded_files or uploaded_files[0].filename == '':
        flash('Erro: Nenhum arquivo selecionado.', 'error')
        return redirect(url_for('index'))
    for file in uploaded_files:
        if file and file.filename:
            filename = file.filename
            file_key = FILENAME_TO_KEY_MAP.get(filename)
            if file_key:
                try:
                    extra_cols = logic.import_single_excel_to_db(file, file_key)
                    flash(f'Sucesso: Planilha "{filename}" importada.', 'success')
                    if extra_cols:
                        flash(f'Aviso para "{filename}": As seguintes colunas não existem no banco e foram ignoradas: {", ".join(extra_cols)}', 'warning')
                except Exception as e:
                    flash(f'Erro ao processar "{filename}": {e}', 'error')
            else:
                flash(f'Erro: Nome de arquivo "{filename}" não reconhecido.', 'error')
    return redirect(url_for('index'))


@app.route('/')
def index():
    # ALTERADO: Usa a função ajudante para pegar os filtros
    filters = _parse_filters()
    
    summary_data = logic.get_dashboard_summary(
        start_date=filters['start_date_obj'], 
        end_date=filters['end_date_obj'], 
        placa_filter=filters['placa'], 
        filial_filter=filters['filial']
    )
    
    placas = logic.get_unique_plates()
    filiais = logic.get_unique_filiais()
    
    return render_template('index.html', 
                           summary=summary_data,
                           placas=placas,
                           filiais=filiais,
                           selected_placa=filters['placa'],
                           selected_filial=filters['filial'],
                           selected_start_date=filters['start_date_str'],
                           selected_end_date=filters['end_date_str'])

@app.route('/gerenciar-grupos-dados')
def gerenciar_grupos_dados():
    # ... (código inalterado) ...
    logic.sync_expense_groups() 
    df_flags = logic.get_all_group_flags()
    flags_dict = df_flags.set_index('group_name').to_dict('index') if not df_flags.empty else {}
    return jsonify(flags_dict)

@app.route('/gerenciar-grupos-salvar', methods=['POST'])
def gerenciar_grupos_salvar():
    # ... (código inalterado) ...
    all_groups = logic.get_all_expense_groups()
    update_data = {}
    for group in all_groups:
        if f"{group}_custo" in request.form: 
            update_data[group] = 'custo_viagem'
        elif f"{group}_despesa" in request.form: 
            update_data[group] = 'despesa'
        else: 
            update_data[group] = 'nenhum'

    logic.update_all_group_flags(update_data)
    flash('Classificação de grupos salva com sucesso!', 'success')
    return redirect(url_for('index'))


@app.route('/api/monthly_summary')
def api_monthly_summary():
    # ALTERADO: Usa a função ajudante para pegar os filtros
    filters = _parse_filters()
    
    monthly_data = logic.get_monthly_summary(
        start_date=filters['start_date_obj'],
        end_date=filters['end_date_obj'],
        placa_filter=filters['placa'],
        filial_filter=filters['filial']
    )
    return jsonify(monthly_data.to_dict(orient='records'))

@app.route('/faturamento_detalhes')
def faturamento_detalhes():
    # ALTERADO: Usa a função ajudante para pegar os filtros
    filters = _parse_filters()
    # Passa os filtros para o template
    return render_template('faturamento_detalhes.html', **filters)

# app.py (adicione esta nova rota)

@app.route('/api/faturamento_dashboard_data')
def api_faturamento_dashboard_data():
    filters = _parse_filters() # Reutiliza nossa função de filtros
    dashboard_data = logic.get_faturamento_details_dashboard_data(
        start_date=filters['start_date_obj'],
        end_date=filters['end_date_obj'],
        placa_filter=filters['placa'],
        filial_filter=filters['filial']
    )
    return jsonify(dashboard_data)

if __name__ == '__main__':
    app.run(debug=True, port=5001)