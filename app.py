# app.py
import os
from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify
from werkzeug.utils import secure_filename
import logic  # Importa a nossa lógica refatorada
import io

# Configuração da Aplicação
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

app = Flask(__name__)
app.config = UPLOAD_FOLDER

# Garante que a pasta de uploads existe
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1).lower() in ALLOWED_EXTENSIONS

# Variável global para armazenar o DataFrame mais recente (simplificação para este exemplo)
# Numa aplicação real, isto seria gerido de forma mais robusta (ex: por sessão de utilizador)
latest_df = None

@app.route('/', methods=)
def index():
    global latest_df
    if request.method == 'POST':
        # Verifica se o pedido post tem a parte do ficheiro
        if 'file' not in request.files:
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config, filename)
            file.save(filepath)
            
            # Processa o ficheiro e armazena o DataFrame
            latest_df = logic.processar_ficheiro_excel(filepath)

            return redirect(url_for('index'))

    # Para um pedido GET, renderiza a página com os dados (se existirem)
    data_to_render = latest_df.to_dict(orient='records') if latest_df is not None else None
    return render_template('index.html', data=data_to_render)

@app.route('/plot.png')
def plot_png():
    """ Rota para gerar o gráfico matplotlib como uma imagem PNG. """
    global latest_df
    if latest_df is None:
        return "Nenhum dado para gerar o gráfico.", 404

    fig = logic.criar_grafico_matplotlib(latest_df)
    
    # Salva o gráfico num buffer de memória em vez de um ficheiro
    output = io.BytesIO()
    fig.savefig(output, format='png')
    output.seek(0)
    
    return send_file(output, mimetype='image/png')

@app.route('/api/data')
def api_data():
    """ Endpoint da API para fornecer dados para gráficos do lado do cliente. """
    global latest_df
    if latest_df is None:
        return jsonify({"error": "Nenhum dado disponível"}), 404
    
    # Converte o DataFrame para um formato JSON adequado para bibliotecas de gráficos
    json_data = latest_df.to_json(orient='records')
    return json_data

# --- ROTA SECRETA PARA IMPORTAÇÃO INICIAL DE DADOS ---
# Adicione este bloco no final do seu arquivo app.py

def _import_all_data():
    """
    Função auxiliar para importar dados de todos os arquivos Excel configurados.
    Baseado na lógica do seu main.py original.
    """
    # É preciso garantir que os arquivos .xls estejam na pasta do projeto no GitHub
    # para que o Render possa encontrá-los.
    import os
    import database as db # Garante que estamos usando o database.py atualizado
    import config

    print("\n--- INICIANDO IMPORTAÇÃO DE DADOS EXCEL PARA O POSTGRESQL ---")
    # O Dockerfile já define o WORKDIR como /app
    base_path = "/app" 

    for file_key, file_info in config.EXCEL_FILES_CONFIG.items():
        excel_path = os.path.join(base_path, file_info["path"])
        if os.path.exists(excel_path):
            print(f"-> Importando '{excel_path}' para a tabela '{file_info['table_name']}'...")
            db.import_excel_to_db(excel_path, file_info["sheet_name"], file_info["table_name"])
        else:
            print(f"-> AVISO: Arquivo '{file_info['path']}' não encontrado, importação ignorada.")
    print("--- IMPORTAÇÃO DE DADOS CONCLUÍDA. ---")


@app.route('/importar-dados-agora-12345') # A URL pode ser qualquer coisa difícil de adivinhar
def trigger_import():
    try:
        # Primeiro, recria as tabelas para garantir que estejam limpas
        db.create_tables() 
        # Depois, importa os dados
        _import_all_data()
        return "<h1>Importação de dados concluída com sucesso!</h1><p>Seu banco de dados PostgreSQL foi populado. Você já pode fechar esta aba e usar a aplicação normalmente.</p>"
    except Exception as e:
        return f"<h1>Ocorreu um erro durante a importação:</h1><p>{e}</p>"