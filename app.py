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