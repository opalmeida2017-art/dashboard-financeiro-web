import os
import threading
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from datetime import datetime, timedelta
import logic
import database as db
import config
import coletor_principal
import getpass
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'uma-chave-secreta-muito-dificil-de-adivinhar'
app.config['SUPER_ADMIN_EMAIL'] ='op.almeida@hotmail.com'

# NOVO: Define o tempo de vida da sessão para 30 minutos
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

# --- INICIALIZAÇÕES ---
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = "Por favor, faça login para acessar esta página."
login_manager.login_message_category = "info"
app.jinja_env.globals['config'] = app.config


@app.before_request
def make_session_permanent():
    session.permanent = True
    
# --- MODELO DE USUÁRIO PARA O FLASK-LOGIN ---
class User(UserMixin):
    def __init__(self, id, email, nome, apartamento_id, role):
        self.id = id
        self.email = email
        self.nome = nome
        self.apartamento_id = apartamento_id
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    with db.get_db_connection() as conn:
        cursor = conn.cursor()
        user_data = cursor.execute('SELECT id, email, nome, apartamento_id, role FROM usuarios WHERE id = %s', (user_id,)).fetchone()
        if user_data:
            # Acessa os dados pelo nome da coluna, pois conn.row_factory = sqlite3.Row
            return User(id=user_data['id'], email=user_data['email'], nome=user_data['nome'], apartamento_id=user_data['apartamento_id'], role=user_data['role'])
    return None

# --- FILTROS DE TEMPLATE (Jinja2) ---
@app.template_filter('currency')
def format_currency(value):
    if value is None or not isinstance(value, (int, float)):
        return "R$ 0,00"
    formatted_value = f"{value:,.2f}"
    formatted_value = formatted_value.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted_value}"

@app.template_filter('percentage')
def format_percentage(value):
    if value is None or not isinstance(value, (int, float)):
        return "0,00%"
    formatted_value = f"{value:.2f}"
    formatted_value = formatted_value.replace(".", ",")
    return f"{formatted_value}%"

# --- INICIALIZAÇÃO DO BANCO DE DADOS ---
with app.app_context():
    print("Verificando e garantindo que todas as tabelas do banco de dados existam...")
    db.create_tables()
    print("Verificação do banco de dados concluída.")

FILENAME_TO_KEY_MAP = {info['path']: key for key, info in config.EXCEL_FILES_CONFIG.items()}

def _parse_filters():
    filters = {
        'placa': request.args.get('placa', 'Todos'),
        'filial': request.args.get('filial', 'Todos'),
        'start_date_str': request.args.get('start_date', ''),
        'end_date_str': request.args.get('end_date', '')
    }
    filters['start_date_obj'] = datetime.strptime(filters['start_date_str'], '%Y-%m-%d') if filters['start_date_str'] else None
    filters['end_date_obj'] = datetime.strptime(filters['end_date_str'], '%Y-%m-%d').replace(hour=23, minute=59, second=59) if filters['end_date_str'] else None
    return filters

# --- ROTAS DE AUTENTICAÇÃO ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        # Se o super admin já estiver logado, redireciona para o painel dele
        if current_user.email == app.config['SUPER_ADMIN_EMAIL']:
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        with db.get_db_connection() as conn:
            cursor = conn.cursor()
            user_data = cursor.execute('SELECT id, password_hash FROM usuarios WHERE email = %s', (email,)).fetchone()
            if user_data and bcrypt.check_password_hash(user_data['password_hash'], password):
                user = load_user(user_data['id'])
                if user:
                    login_user(user)
                    
                    # --- LÓGICA DE REDIRECIONAMENTO INTELIGENTE ---
                    # Se o email do utilizador for o do Super Admin, redireciona para o painel do síndico.
                    if user.email == app.config['SUPER_ADMIN_EMAIL']:
                        return redirect(url_for('admin_dashboard'))
                    
                    # Para todos os outros utilizadores, redireciona para o dashboard normal.
                    return redirect(url_for('index'))
                    
            flash('Email ou senha inválidos. Tente novamente.', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- ROTAS PROTEGIDAS DA APLICAÇÃO ---
@app.route('/')

@login_required
def index():
    filters = _parse_filters()
    summary_data = logic.get_dashboard_summary(
        apartamento_id=current_user.apartamento_id,
        start_date=filters['start_date_obj'], 
        end_date=filters['end_date_obj'], 
        placa_filter=filters['placa'], 
        filial_filter=filters['filial']
    )
    placas = logic.get_unique_plates(apartamento_id=current_user.apartamento_id)
    filiais = logic.get_unique_filiais(apartamento_id=current_user.apartamento_id)
    
    return render_template('index.html', 
                           summary=summary_data,
                           placas=placas,
                           filiais=filiais,
                           selected_placa=filters['placa'],
                           selected_filial=filters['filial'],
                           selected_start_date=filters['start_date_str'],
                           selected_end_date=filters['end_date_str'])

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
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
                    extra_cols = logic.import_single_excel_to_db(file, file_key, current_user.apartamento_id)
                    flash(f'Sucesso: Planilha "{filename}" importada.', 'success')
                    if extra_cols:
                        flash(f'Aviso para "{filename}": As seguintes colunas não existem no banco e foram ignoradas: {", ".join(extra_cols)}', 'warning')
                except Exception as e:
                    flash(f'Erro ao processar "{filename}": {e}', 'error')
            else:
                flash(f'Erro: Nome de arquivo "{filename}" não reconhecido.', 'error')
    return redirect(url_for('index'))

@app.route('/gerenciar-grupos-dados')

@login_required
def gerenciar_grupos_dados():
    logic.sync_expense_groups(current_user.apartamento_id) 
    df_flags = logic.get_all_group_flags(current_user.apartamento_id)
    flags_dict = df_flags.set_index('group_name').to_dict('index') if not df_flags.empty else {}
    return jsonify(flags_dict)

@app.route('/gerenciar-grupos-salvar', methods=['POST'])
@login_required
def gerenciar_grupos_salvar():
    all_groups = logic.get_all_expense_groups(current_user.apartamento_id)
    update_data = {}
    for group in all_groups:
        if f"{group}_custo" in request.form: 
            update_data[group] = 'custo_viagem'
        elif f"{group}_despesa" in request.form: 
            update_data[group] = 'despesa'
        else: 
            update_data[group] = 'nenhum'
    logic.update_all_group_flags(current_user.apartamento_id, update_data)
    flash('Classificação de grupos salva com sucesso!', 'success')
    return redirect(url_for('index'))

@app.route('/api/monthly_summary')
@login_required
def api_monthly_summary():
    filters = _parse_filters()
    monthly_data = logic.get_monthly_summary(
        apartamento_id=current_user.apartamento_id,
        start_date=filters['start_date_obj'],
        end_date=filters['end_date_obj'],
        placa_filter=filters['placa'],
        filial_filter=filters['filial']
    )
    return jsonify(monthly_data.to_dict(orient='records'))

@app.route('/faturamento_detalhes')
@login_required
def faturamento_detalhes():
    filters = _parse_filters()
    return render_template('faturamento_detalhes.html', **filters)

@app.route('/api/faturamento_dashboard_data')
@login_required
def api_faturamento_dashboard_data():
    filters = _parse_filters()
    dashboard_data = logic.get_faturamento_details_dashboard_data(
        apartamento_id=current_user.apartamento_id,
        start_date=filters['start_date_obj'],
        end_date=filters['end_date_obj'],
        placa_filter=filters['placa'],
        filial_filter=filters['filial']
    )
    return jsonify(dashboard_data)

@app.route('/iniciar-coleta', methods=['POST'])
@login_required
def iniciar_coleta():
    print("Requisição para iniciar o orquestrador de coleta recebida.")
    thread = threading.Thread(target=coletor_principal.executar_todas_as_coletas, args=(current_user.apartamento_id,))
    thread.start()
    return jsonify({'status': 'sucesso', 'mensagem': 'A coleta de dados foi iniciada em segundo plano.'})

@app.route('/configuracao', methods=['GET', 'POST'])
@login_required
def configuracao():
    if request.method == 'POST':
        configs = {
            'URL_LOGIN': request.form.get('URL_LOGIN'),
            'USUARIO_ROBO': request.form.get('USUARIO_ROBO'),
            'SENHA_ROBO': request.form.get('SENHA_ROBO'),
            'CODIGO_VIAGENS_CLIENTE': request.form.get('CODIGO_VIAGENS_CLIENTE'),
            'CODIGO_VIAGENS_FAT_CLIENTE': request.form.get('CODIGO_VIAGENS_FAT_CLIENTE'),
            'CODIGO_CONTAS_PAGAR': request.form.get('CODIGO_CONTAS_PAGAR'),
            'CODIGO_CONTAS_RECEBER': request.form.get('CODIGO_CONTAS_RECEBER'),
            'CODIGO_DESPESAS': request.form.get('CODIGO_DESPESAS'),
            'DATA_INICIAL_ROBO': request.form.get('DATA_INICIAL_ROBO'),
            'DATA_FINAL_ROBO': request.form.get('DATA_FINAL_ROBO'),
        }
        logic.salvar_configuracoes_robo(current_user.apartamento_id, configs)
        flash('Configurações salvas com sucesso!', 'success')
        return redirect(url_for('configuracao'))
    
    configs_salvas = logic.ler_configuracoes_robo(current_user.apartamento_id)
    return render_template('configuracao.html', configs=configs_salvas)

# --- COMANDO CLI PARA CRIAR ADMIN ---
@app.cli.command("criar-admin")
def criar_admin_command():
    """Cria o primeiro inquilino (apartamento) e seu usuário administrador."""
    print("--- Assistente de Criação do Primeiro Apartamento e Admin ---")
    
    nome_empresa = input("Nome da Empresa (Apartamento): ")
    admin_nome = input("Seu nome completo: ")
    admin_email = input("Seu email (será seu login): ")
    admin_password = getpass.getpass("Digite uma senha para você: ")

    if not all([nome_empresa, admin_nome, admin_email, admin_password]):
        print("Erro: Todos os campos são obrigatórios.")
        return

    try:
        with db.get_db_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute(
                'INSERT INTO apartamentos (nome_empresa, status, data_criacao) VALUES (?, ?, ?)',
                (nome_empresa, 'ativo', now)
            )
            apartamento_id = cursor.lastrowid
            print(f"-> Apartamento '{nome_empresa}' criado com ID: {apartamento_id}")

            password_hash = bcrypt.generate_password_hash(admin_password).decode('utf-8')
            cursor.execute(
                'INSERT INTO usuarios (apartamento_id, email, password_hash, nome, role) VALUES (?, ?, ?, ?, ?)',
                (apartamento_id, admin_email, password_hash, admin_nome, 'admin')
            )
            print(f"-> Usuário administrador '{admin_email}' criado com sucesso.")
            conn.commit()
            print("\n--- Processo concluído! ---")
    except Exception as e:
        print(f"\nOcorreu um erro: {e}")
        print("A operação foi cancelada.")
        
@app.route('/gerenciar-usuarios')
@login_required
def gerenciar_usuarios():
    # Garante que apenas administradores possam aceder a esta página
    if current_user.role != 'admin':
        flash('Acesso negado. Você não tem permissão para ver esta página.', 'error')
        return redirect(url_for('index'))
    
    # Busca os utilizadores do apartamento do admin logado
    users = logic.get_users_for_apartment(current_user.apartamento_id)
    
    return render_template('gerenciar_usuarios.html', users=users)

# Em app.py

# --- ROTAS DE GESTÃO DE UTILIZADORES (ADMIN DO APARTAMENTO) ---

@app.route('/gerenciar-usuarios/adicionar', methods=['POST'])
@login_required
def adicionar_usuario():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Acesso negado.'}), 403

    nome = request.form.get('nome')
    email = request.form.get('email')
    password = request.form.get('password')
    role = request.form.get('role', 'usuario')

    if not all([nome, email, password]):
        flash('Todos os campos são obrigatórios.', 'error')
        return redirect(url_for('gerenciar_usuarios'))

    password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    
    success, message = logic.add_user_to_apartment(
        apartamento_id=current_user.apartamento_id,
        nome=nome,
        email=email,
        password_hash=password_hash,
        role=role
    )

    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
        
    return redirect(url_for('gerenciar_usuarios'))


@app.route('/gerenciar-usuarios/dados/<int:user_id>', methods=['GET'])
@login_required
def get_user_data(user_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Acesso negado'}), 403
    
    user = logic.get_user_by_id(user_id, current_user.apartamento_id)
    if user:
        return jsonify(user)
    return jsonify({'error': 'Utilizador não encontrado'}), 404


@app.route('/gerenciar-usuarios/editar/<int:user_id>', methods=['POST'])
@login_required
def editar_usuario(user_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Acesso negado.'}), 403

    nome = request.form.get('nome')
    email = request.form.get('email')
    password = request.form.get('password')
    role = request.form.get('role', 'usuario')

    if not all([nome, email]):
        flash('Nome e email são obrigatórios.', 'error')
        return redirect(url_for('gerenciar_usuarios'))

    new_password_hash = None
    if password:
        new_password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    success, message = logic.update_user_in_apartment(
        user_id=user_id,
        apartamento_id=current_user.apartamento_id,
        nome=nome,
        email=email,
        role=role,
        new_password_hash=new_password_hash
    )

    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
        
    return redirect(url_for('gerenciar_usuarios'))

@app.route('/gerenciar-usuarios/apagar/<int:user_id>', methods=['POST'])
@login_required
def apagar_usuario(user_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Acesso negado.'}), 403
    
    # Não permitir que o admin se apague a si mesmo
    if user_id == current_user.id:
        flash('Não pode apagar a sua própria conta de administrador.', 'error')
        return redirect(url_for('gerenciar_usuarios'))

    success, message = logic.delete_user_from_apartment(user_id, current_user.apartamento_id)

    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')

    return redirect(url_for('gerenciar_usuarios'))

# Função auxiliar para verificar se o utilizador é o Super Admin
def super_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.email != app.config['SUPER_ADMIN_EMAIL']:
            flash("Acesso negado. Esta área é restrita.", "error")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

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
            return redirect(url_for('criar_apartamento'))

        password_hash = bcrypt.generate_password_hash(admin_password).decode('utf-8')
        
        success, message = logic.create_apartment_and_admin(nome_empresa, admin_nome, admin_email, password_hash)

        if success:
            flash(message, 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash(message, 'error')
            return redirect(url_for('criar_apartamento'))

    return render_template('super_admin/criar_apartamento.html')

@app.route('/super-admin')
@login_required
@super_admin_required
def admin_dashboard():
    # MODIFICADO: Chama a nova função para obter estatísticas de uso.
    apartamentos = logic.get_apartments_with_usage_stats()
    return render_template('super_admin/dashboard.html', apartamentos=apartamentos)

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

if __name__ == '__main__':
    app.run(debug=True, port=5001)
