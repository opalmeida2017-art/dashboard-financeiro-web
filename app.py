from dotenv import load_dotenv
load_dotenv()

import os
import logic
import database as db
import config
import coletor_principal
import getpass
import threading
import redis
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session, g, Response
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from datetime import datetime, timedelta
from functools import wraps
from sqlalchemy import text
from slugify import slugify
from rq import Queue
from apscheduler.schedulers.background import BackgroundScheduler
from db_connection import engine
import json
import time
from limpar_dados import limpar_dados_importados

app = Flask(__name__)
    
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'uma-chave-secreta-muito-dificil-de-adivinhar')
app.config['SUPER_ADMIN_EMAIL'] ='op.almeida@hotmail.com'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

# --- INICIALIZAÇÕES ---
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = "Por favor, faça login para aceder a esta página."
login_manager.login_message_category = "info"
app.jinja_env.globals['config'] = app.config

# --- Conexão Global com o Redis (feita uma vez no arranque) ---
REDIS_URL = os.environ.get('REDIS_URL')
redis_conn = None

if REDIS_URL:
    try:
        redis_conn = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        redis_conn.ping()
        print("✅ Conexão com o Redis estabelecida com sucesso!")
    except redis.exceptions.ConnectionError as e:
        print(f"❌ Erro ao conectar ao Redis (no arranque): {e}")
    except Exception as e:
        print(f"❌ Ocorreu um erro inesperado na configuração do Redis: {e}")
else:
    print("⚠️ A variável de ambiente REDIS_URL não foi definida. O serviço Redis não será utilizado.")
    

def get_target_apartment_id():
    """
    Determina o ID do apartamento correto a ser usado, respeitando o modo de
    visualização do super admin. Esta é a fonte única da verdade para o contexto.
    """
    if session.get('force_customer_view') and 'viewing_apartment_id' in session:
        return session['viewing_apartment_id']
    elif current_user.is_authenticated:
        return current_user.apartamento_id
    return None

def is_admin_in_context():
    """Verifica se o utilizador tem privilégios de admin no contexto atual."""
    if not current_user.is_authenticated:
        return False
    is_normal_admin = (current_user.role == 'admin')
    is_impersonating_admin = (
        current_user.email == app.config['SUPER_ADMIN_EMAIL'] and
        session.get('force_customer_view')
    )
    return is_normal_admin or is_impersonating_admin

@app.context_processor
def inject_user_roles():
    """Disponibiliza a função de verificação para todos os templates."""
    return dict(is_admin_in_context=is_admin_in_context)

def super_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.email != app.config['SUPER_ADMIN_EMAIL']:
            flash("Acesso negado. Esta área é restrita.", "error")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.before_request
def make_session_permanent():
    session.permanent = True

# --- MODELO DE UTILIZADOR E CARREGADOR ---
class User(UserMixin):
    def __init__(self, id, email, nome, apartamento_id, role):
        self.id = id
        self.email = email
        self.nome = nome
        self.apartamento_id = apartamento_id
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    with engine.connect() as conn:
        query = text("SELECT id, email, nome, apartamento_id, role FROM usuarios WHERE id = :user_id")
        user_data = conn.execute(query, {"user_id": user_id}).mappings().first()
    if user_data:
        return User(id=user_data['id'], email=user_data['email'], nome=user_data['nome'], apartamento_id=user_data['apartamento_id'], role=user_data['role'])
    return None

# --- FILTROS DE TEMPLATE (Jinja2) ---
@app.template_filter('currency')
def format_currency(value):
    if value is None or not isinstance(value, (int, float)):
        return "R$ 0,00"
    formatted_value = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted_value}"

@app.template_filter('percentage')
def format_percentage(value):
    if value is None or not isinstance(value, (int, float)):
        return "0,00%"
    formatted_value = f"{value:.2f}".replace(".", ",")
    return f"{formatted_value}%"

def _parse_filters():
    filters = {
        'placa': request.args.get('placa', 'Todos'),
        'filial': request.args.getlist('filial'),
        'start_date_str': request.args.get('start_date', ''),
        'end_date_str': request.args.get('end_date', '')
    }
    try:
        filters['start_date_obj'] = datetime.strptime(filters['start_date_str'], '%Y-%m-%d') if filters['start_date_str'] else None
        filters['end_date_obj'] = datetime.strptime(filters['end_date_str'], '%Y-%m-%d').replace(hour=23, minute=59, second=59) if filters['end_date_str'] else None
    except ValueError:
        filters['start_date_obj'] = None
        filters['end_date_obj'] = None
    return filters

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        with engine.connect() as conn:
            query = text("SELECT id, password_hash FROM usuarios WHERE email = :email")
            user_data = conn.execute(query, {"email": email}).mappings().first()
        
        if user_data and bcrypt.check_password_hash(user_data['password_hash'], password):
            user = load_user(user_data['id'])
            if user:
                login_user(user)
                return redirect(url_for('index'))
        
        flash('Email ou senha inválidos. Tente novamente.', 'error')
    return render_template('login.html')

@app.route('/acesso/<slug>', methods=['GET', 'POST'])
def login_por_slug(slug):
    apartamento = logic.get_apartment_by_slug(slug)
    if not apartamento:
        return "Página não encontrada.", 404

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        with engine.connect() as conn:
            query = text("SELECT id, password_hash, apartamento_id FROM usuarios WHERE email = :email")
            user_data = conn.execute(query, {"email": email}).mappings().first()
        
        if user_data and bcrypt.check_password_hash(user_data['password_hash'], password):
            is_super_admin = (email == app.config['SUPER_ADMIN_EMAIL'])
            if not is_super_admin and (user_data['apartamento_id'] != apartamento['id']):
                flash('Este utilizador não pertence a esta empresa.', 'error')
                return redirect(url_for('login_por_slug', slug=slug))

            user = load_user(user_data['id'])
            if user:
                login_user(user)
                if is_super_admin:
                    session['force_customer_view'] = True
                    session['viewing_apartment_id'] = apartamento['id']
                return redirect(url_for('index'))
        
        flash('Email ou senha inválidos. Tente novamente.', 'error')
    return render_template('login.html', apartamento=apartamento, nome_empresa=apartamento['nome_empresa'])

@app.route('/logout')
@login_required
def logout():
    session.pop('force_customer_view', None)
    session.pop('viewing_apartment_id', None)
    logout_user()
    return redirect(url_for('login'))

# --- ROTAS PRINCIPAIS DA APLICAÇÃO ---

@app.route('/')
@login_required
def index():
    if current_user.email == app.config['SUPER_ADMIN_EMAIL'] and not session.get('force_customer_view'):
        return redirect(url_for('admin_dashboard'))

    apartamento_id_alvo = get_target_apartment_id()
    if apartamento_id_alvo is None:
        flash("Não foi possível identificar a empresa. Por favor, faça login novamente.", "error")
        return redirect(url_for('logout'))

    filters = _parse_filters()
    summary_data = logic.get_dashboard_summary(
        apartamento_id=apartamento_id_alvo,
        start_date=filters['start_date_obj'], 
        end_date=filters['end_date_obj'], 
        placa_filter=filters['placa'], 
        filial_filter=filters['filial']
    )
    placas = logic.get_unique_plates_with_types(apartamento_id=apartamento_id_alvo)
    filiais = logic.get_unique_filiais(apartamento_id=apartamento_id_alvo)
    
    placa_filtrada = filters['placa'] and filters['placa'] != 'Todos'
    
    return render_template('index.html', 
                           summary=summary_data,
                           placas=placas,
                           filiais=filiais,
                           selected_placa=filters['placa'],
                           selected_filial=filters['filial'],
                           selected_start_date=filters['start_date_str'],
                           selected_end_date=filters['end_date_str'],
                           placa_filtrada=placa_filtrada)
    
@app.route('/faturamento_detalhes')
@login_required
def faturamento_detalhes():
    filters = _parse_filters()
    return render_template('faturamento_detalhes.html', **filters)

@app.route('/despesas_detalhes')
@login_required
def despesas_detalhes():
    return render_template('despesas_detalhes.html')

# --- ROTAS DE API (PARA GRÁFICOS) ---

@app.route('/api/monthly_summary')
@login_required
def api_monthly_summary():
    apartamento_id_alvo = get_target_apartment_id()
    if apartamento_id_alvo is None:
        return jsonify({"error": "Contexto do apartamento não encontrado"}), 400

    filters = _parse_filters()
    monthly_data = logic.get_monthly_summary(
        apartamento_id=apartamento_id_alvo,
        start_date=filters['start_date_obj'],
        end_date=filters['end_date_obj'],
        placa_filter=filters['placa'],
        filial_filter=filters['filial']
    )
    return jsonify(monthly_data.to_dict(orient='records'))

@app.route('/api/get_robot_logs')
@login_required
def api_get_robot_logs():
    apartamento_id_alvo = get_target_apartment_id()
    if not apartamento_id_alvo:
        return jsonify({"error": "Contexto do apartamento não encontrado"}), 400
    try:
        with engine.connect() as conn:
            query = text("SELECT timestamp, mensagem FROM tb_logs_robo WHERE apartamento_id = :apt_id ORDER BY timestamp DESC LIMIT 100")
            result = conn.execute(query, {"apt_id": apartamento_id_alvo})
            logs = [{"timestamp": row[0].strftime('%d/%m/%Y %H:%M:%S') if row[0] else '', "mensagem": row[1]} for row in result]
            return jsonify(logs)
    except Exception as e:
        print(f"Erro ao buscar logs do robô: {e}")
        return jsonify({"error": f"Erro ao buscar logs: {e}"}), 500

@app.route('/api/clear_robot_logs', methods=['POST'])
@login_required
def api_clear_robot_logs():
    apartamento_id_alvo = get_target_apartment_id()
    if not apartamento_id_alvo:
        return jsonify({"status": "error", "message": "Contexto do apartamento não encontrado"}), 400
    try:
        with engine.connect() as conn:
            query = text("DELETE FROM tb_logs_robo WHERE apartamento_id = :apt_id")
            conn.execute(query, {"apt_id": apartamento_id_alvo})
            conn.commit()
        flash('Logs do robô foram limpos com sucesso!', 'success')
        return jsonify({"status": "success", "message": "Logs limpos com sucesso!"})
    except Exception as e:
        print(f"Erro ao limpar logs do robô: {e}")
        return jsonify({"status": "error", "message": f"Erro ao limpar logs: {e}"}), 500

@app.route('/api/faturamento_dashboard_data')
@login_required
def api_faturamento_dashboard_data():
    apartamento_id_alvo = get_target_apartment_id()
    if apartamento_id_alvo is None:
        return jsonify({"error": "Contexto do apartamento não encontrado"}), 400
    filters = _parse_filters()
    dashboard_data = logic.get_faturamento_details_dashboard_data(
        apartamento_id=apartamento_id_alvo,
        start_date=filters['start_date_obj'],
        end_date=filters['end_date_obj'],
        placa_filter=filters['placa'],
        filial_filter=filters['filial']
    )
    return jsonify(dashboard_data)


@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    apartamento_id_alvo = get_target_apartment_id()
    if not apartamento_id_alvo:
        flash("Sessão inválida. Por favor, faça login novamente.", "error")
        return redirect(url_for('login'))
        
    uploaded_files = request.files.getlist('files[]')
    if not uploaded_files or uploaded_files[0].filename == '':
        flash('Erro: Nenhum ficheiro selecionado.', 'error')
        return redirect(url_for('index'))

    for file in uploaded_files:
        if file and file.filename:
            filename = file.filename
            file_key = {info['path']: key for key, info in config.EXCEL_FILES_CONFIG.items()}.get(filename)
            if file_key:
                try:
                    table_info = config.EXCEL_FILES_CONFIG[file_key]
                    sheet_name = table_info.get('sheet_name')
                    table_name = table_info['table']
                    if table_name == 'relFilDespesasGerais':
                        extra_cols = db.process_and_import_despesas(excel_source=file, sheet_name=sheet_name, table_name=table_name, apartamento_id=apartamento_id_alvo)
                    else:
                        key_columns = config.TABLE_PRIMARY_KEYS.get(table_name)
                        if not key_columns:
                            flash(f"ERRO: Chaves primárias não definidas para a tabela '{table_name}'.", 'error')
                            continue
                        extra_cols = db.import_excel_to_db(excel_source=file, sheet_name=sheet_name, table_name=table_name, key_columns=key_columns, apartamento_id=apartamento_id_alvo)
                    
                    flash(f'Sucesso: Planilha "{filename}" importada.', 'success')
                    if extra_cols:
                        flash(f'Aviso para "{filename}": As seguintes colunas não existem na base de dados e foram ignoradas: {", ".join(extra_cols)}', 'warning')
                except Exception as e:
                    flash(f'Erro ao processar "{filename}": {e}', 'error')
            else:
                flash(f'Erro: Nome de ficheiro "{filename}" não reconhecido.', 'error')
    
    logic.sync_expense_groups(apartamento_id_alvo)
    return redirect(url_for('index'))

@app.route('/gerenciar-grupos-dados')
@login_required
def gerenciar_grupos_dados():
    apartamento_id_alvo = get_target_apartment_id()
    logic.sync_expense_groups(apartamento_id_alvo) 
    df_flags = logic.get_group_flags_with_tipo_d_status(apartamento_id_alvo)
    flags_dict = df_flags.set_index('group_name').to_dict('index') if not df_flags.empty else {}
    return jsonify(flags_dict)

@app.route('/gerenciar-grupos-salvar', methods=['POST'])
@login_required
def gerenciar_grupos_salvar():
    apartamento_id_alvo = get_target_apartment_id()
    all_groups = logic.get_all_expense_groups(apartamento_id_alvo)
    update_data = {}
    
    for group in all_groups:
        classification = 'nenhum'
        if f"{group}_custo" in request.form: 
            classification = 'custo_viagem'
        elif f"{group}_despesa" in request.form: 
            classification = 'despesa'
        
        incluir_tipo_d = f"{group}_tipo_d" in request.form
        update_data[group] = {'classification': classification, 'incluir_tipo_d': incluir_tipo_d}
        
    logic.update_all_group_flags(apartamento_id_alvo, update_data)
    flash('Classificação de grupos salva com sucesso!', 'success')
    return redirect(url_for('index'))

@app.route('/iniciar-coleta', methods=['POST'])
@login_required
def iniciar_coleta_endpoint():
    apartamento_id_alvo = get_target_apartment_id()
    if not apartamento_id_alvo:
        return jsonify({'status': 'erro', 'mensagem': 'Contexto do apartamento não encontrado.'}), 400

    execution_mode = os.getenv("EXECUTION_MODE", "async")
    
    try:
        if execution_mode == "sync":
            print(f"--- INICIANDO COLETA SÍNCRONA PARA APARTAMENTO {apartamento_id_alvo} ---")
            coletor_principal.executar_todas_as_coletas(apartamento_id_alvo)
            print(f"--- COLETA SÍNCRONA FINALIZADA ---")
            flash('Coleta de dados finalizada com sucesso!', 'success')
            return jsonify({'status': 'sucesso', 'mensagem': 'Coleta finalizada!'})
        else:
            if not redis_conn:
                return jsonify({'status': 'erro', 'mensagem': 'Serviço de fila (Redis) não está disponível.'}), 500
            
            print(f"--- ENFILEIRANDO COLETA ASSÍNCRONA PARA APARTAMENTO {apartamento_id_alvo} ---")
            q = Queue(connection=redis_conn)
            q.enqueue(coletor_principal.executar_todas_as_coletas, apartamento_id_alvo, job_timeout=1800)
            flash('A coleta de dados foi iniciada em segundo plano.', 'success')
            return jsonify({'status': 'sucesso', 'mensagem': 'A coleta de dados foi iniciada em segundo plano.'})

    except Exception as e:
        print(f"Erro ao executar/enfileirar tarefa: {e}")
        flash(f'Ocorreu um erro ao iniciar a tarefa: {e}', 'error')
        return jsonify({'status': 'erro', 'mensagem': f'Ocorreu um erro ao iniciar a tarefa: {e}'}), 500

@app.route('/configuracao', methods=['GET', 'POST'])
@login_required
def configuracao():
    if not is_admin_in_context():
        flash("Acesso negado. Você precisa ser um administrador para ver esta página.", "error")
        return redirect(url_for('index'))
    
    apartamento_id_alvo = get_target_apartment_id()
    if not apartamento_id_alvo:
        flash("Sessão inválida ou apartamento não encontrado.", "error")
        return redirect(url_for('logout'))

    if request.method == 'POST':
        live_monitoring_enabled = 'live_monitoring_enabled' in request.form
        configs = {
            'URL_LOGIN': request.form.get('URL_LOGIN'),
            'USUARIO_ROBO': request.form.get('USUARIO_ROBO'),
            'SENHA_ROBO': request.form.get('SENHA_ROBO'),
            'CODIGO_VIAGENS_CLIENTE': request.form.get('CODIGO_VIAGENS_CLIENTE'),
            'CODIGO_VIAGENS_FAT_CLIENTE': request.form.get('CODIGO_VIAGENS_FAT_CLIENTE'),
            'CODIGO_CONTAS_PAGAR': request.form.get('CODIGO_CONTAS_PAGAR'),
            'CODIGO_CONTAS_RECEBER': request.form.get('CODIGO_CONTAS_RECEBER'),
            'CODIGO_DESPESAS': request.form.get('CODIGO_DESPESAS'),
            'DATA_INICIAL_ROBO': datetime.strptime(request.form.get('DATA_INICIAL_ROBO'), '%Y-%m-%d').strftime('%d/%m/%Y') if request.form.get('DATA_INICIAL_ROBO') else '',
            'DATA_FINAL_ROBO': datetime.strptime(request.form.get('DATA_FINAL_ROBO'), '%Y-%m-%d').strftime('%d/%m/%Y') if request.form.get('DATA_FINAL_ROBO') else '',
            'live_monitoring_enabled': live_monitoring_enabled
        }
        logic.salvar_configuracoes_robo(apartamento_id_alvo, configs)
        flash('Configurações salvas com sucesso!', 'success')
        return redirect(url_for('configuracao'))
    
    configs_salvas = logic.ler_configuracoes_robo(apartamento_id_alvo)
    try:
        if configs_salvas.get('DATA_INICIAL_ROBO'):
            configs_salvas['DATA_INICIAL_ROBO_YMD'] = datetime.strptime(configs_salvas['DATA_INICIAL_ROBO'], '%d/%m/%Y').strftime('%Y-%m-%d')
        if configs_salvas.get('DATA_FINAL_ROBO'):
            configs_salvas['DATA_FINAL_ROBO_YMD'] = datetime.strptime(configs_salvas['DATA_FINAL_ROBO'], '%d/%m/%Y').strftime('%Y-%m-%d')
    except (ValueError, TypeError):
        pass
    
    return render_template('configuracao.html', configs=configs_salvas)

@app.route('/gerenciar-usuarios')
@login_required
def gerenciar_usuarios():
    if not is_admin_in_context():
        flash('Acesso negado.', 'error')
        return redirect(url_for('index'))
    
    apartamento_id_alvo = get_target_apartment_id()
    users = logic.get_users_for_apartment(apartamento_id_alvo)
    return render_template('gerenciar_usuarios.html', users=users)

@app.route('/gerenciar-usuarios/adicionar', methods=['POST'])
@login_required
def adicionar_usuario():
    if not is_admin_in_context():
        return jsonify({'success': False, 'message': 'Acesso negado.'}), 403
    
    apartamento_id_alvo = get_target_apartment_id()
    nome = request.form.get('nome')
    email = request.form.get('email')
    password = request.form.get('password')
    role = request.form.get('role', 'usuario')

    if not all([nome, email, password]):
        flash('Todos os campos são obrigatórios.', 'error')
        return redirect(url_for('gerenciar_usuarios'))

    password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    success, message = logic.add_user_to_apartment(
        apartamento_id=apartamento_id_alvo, nome=nome, email=email,
        password_hash=password_hash, role=role
    )

    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    return redirect(url_for('gerenciar_usuarios'))

@app.route('/gerenciar-usuarios/dados/<int:user_id>', methods=['GET'])
@login_required
def get_user_data(user_id):
    if not is_admin_in_context():
        return jsonify({'error': 'Acesso negado'}), 403
    
    apartamento_id_alvo = get_target_apartment_id()
    user = logic.get_user_by_id(user_id, apartamento_id_alvo)
    if user:
        return jsonify(user)
    return jsonify({'error': 'Utilizador não encontrado'}), 404

@app.route('/gerenciar-usuarios/editar/<int:user_id>', methods=['POST'])
@login_required
def editar_usuario(user_id):
    if not is_admin_in_context():
        return jsonify({'success': False, 'message': 'Acesso negado.'}), 403
    
    apartamento_id_alvo = get_target_apartment_id()
    nome = request.form.get('nome')
    email = request.form.get('email')
    password = request.form.get('password')
    role = request.form.get('role', 'usuario')

    if not all([nome, email]):
        flash('Nome e email são obrigatórios.', 'error')
        return redirect(url_for('gerenciar_usuarios'))

    new_password_hash = bcrypt.generate_password_hash(password).decode('utf-8') if password else None
    success, message = logic.update_user_in_apartment(
        user_id=user_id, apartamento_id=apartamento_id_alvo, nome=nome,
        email=email, role=role, new_password_hash=new_password_hash
    )

    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    return redirect(url_for('gerenciar_usuarios'))

@app.route('/gerenciar-usuarios/apagar/<int:user_id>', methods=['POST'])
@login_required
def apagar_usuario(user_id):
    if not is_admin_in_context():
        return jsonify({'success': False, 'message': 'Acesso negado.'}), 403
    
    apartamento_id_alvo = get_target_apartment_id()
    if user_id == current_user.id:
        flash('Não pode apagar a sua própria conta de administrador.', 'error')
        return redirect(url_for('gerenciar_usuarios'))

    success, message = logic.delete_user_from_apartment(user_id, apartamento_id_alvo)
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    return redirect(url_for('gerenciar_usuarios'))

# --- ROTAS DO SUPER ADMIN (SÍNDICO) ---

@app.route('/super-admin')
@login_required
@super_admin_required
def admin_dashboard():
    session.pop('force_customer_view', None)
    session.pop('viewing_apartment_id', None)
    apartamentos = logic.get_apartments_with_usage_stats()
    for apt in apartamentos:
        if apt.get('slug'):
            apt['access_link'] = url_for('login_por_slug', slug=apt['slug'], _external=True)
        else:
            apt['access_link'] = "Sem slug definido"
    
    return render_template('super_admin/dashboard.html', apartamentos=apartamentos)


@app.route('/super-admin/limpar-dados/<int:apartamento_id>', methods=['POST'])
@login_required
@super_admin_required
def limpar_dados_apartamento(apartamento_id):
    """
    Endpoint para limpar os dados de um apartamento específico.
    Acesso restrito ao super-admin.
    """
    try:
        limpar_dados_importados(apartamento_id)
        flash(f'Dados do apartamento {apartamento_id} limpos com sucesso.', 'success')
        return jsonify({'status': 'success', 'message': 'Dados limpos.'})
    except Exception as e:
        flash(f'Erro ao limpar dados do apartamento {apartamento_id}: {e}', 'error')
        return jsonify({'status': 'error', 'message': 'Erro ao limpar dados.'}), 500

@app.route('/super-admin/criar', methods=['GET', 'POST'])
@login_required
@super_admin_required
def criar_apartamento():
    if request.method == 'POST':
        nome_empresa = request.form.get('nome_empresa')
        admin_nome = request.form.get('admin_nome')
        admin_email = request.form.get('admin_email')
        admin_password = request.form.get('admin_password')

        if not all([nome_empresa, admin_nome, admin_email, admin_password]):
            flash("Todos os campos são obrigatórios.", "error")
            return render_template('criar_apartamento.html')

        password_hash = bcrypt.generate_password_hash(admin_password).decode('utf-8')
        success, message = logic.create_apartment_and_admin(nome_empresa, admin_nome, admin_email, password_hash)

        if success:
            flash(message, 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash(message, 'error')
            return render_template('super_admin/criar_apartamento.html')
    return render_template('super_admin/criar_apartamento.html')

@app.route('/super-admin/gerir/<int:apartamento_id>', methods=['GET', 'POST'])
@login_required
@super_admin_required
def gerir_apartamento(apartamento_id):
    if request.method == 'POST':
        nome_empresa = request.form.get('nome_empresa')
        status = request.form.get('status')
        data_vencimento = request.form.get('data_vencimento')
        notas = request.form.get('notas_admin')

        success, message = logic.update_apartment_details(apartamento_id, nome_empresa, status, data_vencimento, notas)
        
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
        
        return redirect(url_for('admin_dashboard'))

    apartamento = logic.get_apartment_details(apartamento_id)
    if not apartamento:
        flash("Apartamento não encontrado.", "error")
        return redirect(url_for('admin_dashboard'))
    
    return render_template('super_admin/gerir_apartamento.html', apartamento=apartamento)

# --- COMANDOS DE CLI ---
@app.cli.command("criar-admin")
def criar_admin_command():
    print("--- Assistente de Criação do Primeiro Apartamento e Admin ---")
    nome_empresa = input("Nome da Empresa (Apartamento): ")
    admin_nome = input("Seu nome completo: ")
    admin_email = input("Seu email (será seu login): ")
    admin_password = getpass.getpass("Digite uma senha para você: ")

    if not all([nome_empresa, admin_nome, admin_email, admin_password]):
        print("Erro: Todos os campos são obrigatórios.")
        return

    password_hash = bcrypt.generate_password_hash(admin_password).decode('utf-8')
    success, message = logic.create_apartment_and_admin(nome_empresa, admin_nome, admin_email, password_hash)
    
    if success:
        print(f"\nSUCESSO: {message}")
    else:
        print(f"\nERRO: {message}")
   
# --- API DE "HEARTBEAT" PARA RASTREAR ATIVIDADE ---
@app.route('/api/heartbeat', methods=['POST'])
@login_required
def api_heartbeat():
    """
    Recebe um 'ping' do frontend para registrar que o usuário está ativo.
    """
    apartamento_id_alvo = get_target_apartment_id()
    if not apartamento_id_alvo:
        return jsonify({"status": "error"}), 400
    
    try:
        with engine.connect() as conn:
            query = text("""
                INSERT INTO tb_user_activity (apartamento_id, last_seen_timestamp)
                VALUES (:apt_id, NOW())
                ON CONFLICT (apartamento_id) DO UPDATE
                SET last_seen_timestamp = NOW();
            """)
            conn.execute(query, {"apt_id": apartamento_id_alvo})
            conn.commit()
        return jsonify({"status": "ok"})
    except Exception as e:
        print(f"Erro no heartbeat: {e}")
        return jsonify({"status": "error"}), 500

# --- ROTA DE STREAMING DE STATUS (VERSÃO NATIVA PARA FLASK) ---
@app.route('/api/status_stream')
@login_required
@super_admin_required
def status_stream():
    """
    Mantém uma conexão aberta com o navegador do síndico e envia
    atualizações de status de usuário a cada 5 segundos.
    """
    def event_generator():
        while True:
            try:
                with engine.connect() as conn:
                    two_minutes_ago = datetime.now() - timedelta(minutes=2)
                    query = text("SELECT apartamento_id FROM tb_user_activity WHERE last_seen_timestamp >= :time_limit")
                    result = conn.execute(query, {"time_limit": two_minutes_ago})
                    active_ids = [row[0] for row in result]
                
                data_json = json.dumps({"active_apartments": active_ids})
                yield f"data: {data_json}\n\n"
                
                time.sleep(5)
            except Exception as e:
                print(f"Erro no stream de status: {e}")
                error_data = json.dumps({"error": str(e)})
                yield f"data: {error_data}\n\n"
                time.sleep(5)

    return Response(event_generator(), mimetype='text/event-stream')

@app.route('/api/despesas_por_filial_e_grupo')
@login_required
def api_despesas_por_filial_e_grupo():
    apartamento_id_alvo = get_target_apartment_id()
    if apartamento_id_alvo is None:
        return jsonify({"error": "Contexto do apartamento não encontrado"}), 400

    filters = _parse_filters()
    data_for_chart = logic.get_despesas_por_filial_e_grupo(
        apartamento_id=apartamento_id_alvo,
        start_date=filters['start_date_obj'],
        end_date=filters['end_date_obj'],
        placa_filter=filters.get('placa'),
        filial_filter=filters['filial']
    )
    return jsonify(data_for_chart)

@app.route('/api/despesas_dashboard_data')
@login_required
def api_despesas_dashboard_data():
    apartamento_id_alvo = get_target_apartment_id()
    if apartamento_id_alvo is None:
        return jsonify({"error": "Contexto do apartamento não encontrado"}), 400

    filters = _parse_filters()
    dashboard_data = logic.get_despesas_details_dashboard_data(
        apartamento_id=apartamento_id_alvo,
        start_date=filters['start_date_obj'],
        end_date=filters['end_date_obj'],
        placa_filter=filters['placa'],
        filial_filter=filters['filial']
    )
    return jsonify(dashboard_data)
   
# --- INICIALIZAÇÃO DO AGENDADOR (CORRIGIDO) ---
scheduler = BackgroundScheduler(daemon=True)

# --- LÓGICA DO AGENDADOR ---
def run_scheduled_collections():
    """
    Esta função será executada a cada minuto pelo agendador.
    Ela verifica quais clientes estão online e com a flag ativada, e dispara os robôs.
    """
    print(f"[{datetime.now()}] Verificando robôs agendados para execução...")
    with app.app_context():
        try:
            with engine.connect() as conn:
                two_minutes_ago = datetime.now() - timedelta(minutes=2)
                query = text("""
                    SELECT
                        a.id,
                        a.live_monitoring_interval_minutes
                    FROM apartamentos a
                    JOIN configuracoes_robo cr ON a.id = cr.apartamento_id
                    JOIN tb_user_activity ua ON a.id = ua.apartamento_id
                    WHERE
                        cr.live_monitoring_enabled = TRUE
                        AND ua.last_seen_timestamp >= :time_limit
                """)
                clientes_para_rodar = conn.execute(query, {"time_limit": two_minutes_ago}).mappings().all()

                for cliente in clientes_para_rodar:
                    apartamento_id = cliente['id']
                    print(f"--> Disparando coleta em tempo real para o apartamento ID: {apartamento_id}")
                    coletor_principal.executar_todas_as_coletas(apartamento_id)

        except Exception as e:
            print(f"ERRO no agendador de coletas: {e}")

scheduler.add_job(run_scheduled_collections, 'interval', seconds=60)

if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    print("Iniciando o agendador...")
    scheduler.start()
else:
    print("O agendador não será iniciado no processo de recarregamento do Flask.")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)