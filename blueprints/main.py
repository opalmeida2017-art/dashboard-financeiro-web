# blueprints/main.py (Corrigido)
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import login_required, current_user
import os
import getpass
import redis
from rq import Queue
import logic
import coletor_principal
import config
import database as db
from limpar_dados import limpar_dados_importados
from datetime import datetime
from .helpers import get_target_apartment_id, is_admin_in_context, super_admin_required, parse_filters
from extensions import bcrypt
from db_connection import engine
from .helpers import get_target_apartment_id, is_admin_in_context, super_admin_required, parse_filters
from db_connection import engine

main_bp = Blueprint('main', __name__)

REDIS_URL = os.environ.get('REDIS_URL')
redis_conn = redis.Redis.from_url(REDIS_URL) if REDIS_URL else None

@main_bp.route('/')
@login_required
def index():
    # Esta função agora usa 'current_app' implicitamente através de 'current_user'
    if current_user.email == 'op.almeida@hotmail.com' and not session.get('force_customer_view'):
        return redirect(url_for('main.admin_dashboard'))

    apartamento_id_alvo = get_target_apartment_id()
    if apartamento_id_alvo is None:
        flash("Não foi possível identificar a empresa. Por favor, faça login novamente.", "error")
        return redirect(url_for('auth.logout'))

    filters = parse_filters(request.args)
    summary_data = logic.get_dashboard_summary(
        apartamento_id=apartamento_id_alvo,
        start_date=filters['start_date_obj'],
        end_date=filters['end_date_obj'],
        placa_filter=filters['placa'],
        filial_filter=filters['filial'],
        tipo_negocio_filter=filters['tipo_negocio']
    )
    
    placas = logic.get_unique_plates_with_types(apartamento_id=apartamento_id_alvo)
    filiais = logic.get_unique_filiais(apartamento_id=apartamento_id_alvo)
    tipos_negocio = logic.get_unique_negocios(apartamento_id=apartamento_id_alvo)
    placa_filtrada = filters['placa'] and filters['placa'] != 'Todos'
    
    return render_template('index.html', 
                           summary=summary_data,
                           placas=placas,
                           filiais=filiais,
                           tipos_negocio=tipos_negocio,
                           selected_placa=filters['placa'],
                           selected_filial=filters['filial'],
                           selected_start_date=filters['start_date_str'],
                           selected_end_date=filters['end_date_str'],
                           selected_tipo_negocio=filters['tipo_negocio'],
                           placa_filtrada=placa_filtrada)
    
@main_bp.route('/faturamento_detalhes')
@login_required
def faturamento_detalhes():
    # --- CORREÇÃO ---
    # Usa a função 'parse_filters' importada do helpers.py
    filters = parse_filters(request.args)
    # --- FIM DA CORREÇÃO ---
    return render_template('faturamento_detalhes.html', 
                           selected_start_date=filters['start_date_str'],
                           selected_end_date=filters['end_date_str'],
                           selected_placa=filters['placa'],
                           selected_filial=filters['filial'])

@main_bp.route('/despesas_detalhes')
@login_required
def despesas_detalhes():
    # --- CORREÇÃO ---
    # Usa a função 'parse_filters' e passa os filtros para o template
    filters = parse_filters(request.args)
    return render_template('despesas_detalhes.html',
                           selected_start_date=filters['start_date_str'],
                           selected_end_date=filters['end_date_str'],
                           selected_placa=filters['placa'],
                           selected_filial=filters['filial'])
@main_bp.route('/upload', methods=['POST'])
@login_required
def upload_file():
    apartamento_id_alvo = get_target_apartment_id()
    if not apartamento_id_alvo:
        flash("Sessão inválida. Por favor, faça login novamente.", "error")
        return redirect(url_for('auth.login'))
        
    uploaded_files = request.files.getlist('files[]')
    if not uploaded_files or uploaded_files[0].filename == '':
        flash('Erro: Nenhum ficheiro selecionado.', 'error')
        return redirect(url_for('main.index'))

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
    return redirect(url_for('main.index'))

@main_bp.route('/gerenciar-grupos-dados')
@login_required
def gerenciar_grupos_dados():
    apartamento_id_alvo = get_target_apartment_id()
    logic.sync_expense_groups(apartamento_id_alvo) 
    df_flags = logic.get_group_flags_with_tipo_d_status(apartamento_id_alvo)
    flags_dict = df_flags.set_index('group_name').to_dict('index') if not df_flags.empty else {}
    return jsonify(flags_dict)

@main_bp.route('/gerenciar-grupos-salvar', methods=['POST'])
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
    return redirect(url_for('main.index'))

@main_bp.route('/iniciar-coleta', methods=['POST'])
@login_required
def iniciar_coleta_endpoint():
    apartamento_id_alvo = get_target_apartment_id()
    if not apartamento_id_alvo:
        return jsonify({'status': 'erro', 'mensagem': 'Contexto do apartamento não encontrado.'}), 400

    execution_mode = os.getenv("EXECUTION_MODE", "async")
    
    try:
        if execution_mode == "sync":
            coletor_principal.executar_todas_as_coletas(apartamento_id_alvo)
            flash('Coleta de dados finalizada com sucesso!', 'success')
            return jsonify({'status': 'sucesso', 'mensagem': 'Coleta finalizada!'})
        else:
            if not redis_conn:
                return jsonify({'status': 'erro', 'mensagem': 'Serviço de fila (Redis) não está disponível.'}), 500
            
            q = Queue(connection=redis_conn)
            q.enqueue(coletor_principal.executar_todas_as_coletas, apartamento_id_alvo, job_timeout=1800)
            flash('A coleta de dados foi iniciada em segundo plano.', 'success')
            return jsonify({'status': 'sucesso', 'mensagem': 'A coleta de dados foi iniciada em segundo plano.'})

    except Exception as e:
        flash(f'Ocorreu um erro ao iniciar a tarefa: {e}', 'error')
        return jsonify({'status': 'erro', 'mensagem': f'Ocorreu um erro ao iniciar a tarefa: {e}'}), 500

@main_bp.route('/configuracao', methods=['GET', 'POST'])
@login_required
def configuracao():
    if not is_admin_in_context():
        flash("Acesso negado. Você precisa ser um administrador para ver esta página.", "error")
        return redirect(url_for('main.index'))
    
    apartamento_id_alvo = get_target_apartment_id()
    if not apartamento_id_alvo:
        flash("Sessão inválida ou apartamento não encontrado.", "error")
        return redirect(url_for('auth.logout'))

    if request.method == 'POST':
        # --- INÍCIO DA VALIDAÇÃO DE DATAS NO BACKEND ---
        start_date_str = request.form.get('DATA_INICIAL_ROBO')
        end_date_str = request.form.get('DATA_FINAL_ROBO')

        if start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d')

                # Regra 1: Data final não pode ser menor que a inicial
                if end_date < start_date:
                    flash('Erro: A data final não pode ser anterior à data inicial.', 'error')
                    # Recarrega a página de configuração sem salvar
                    return redirect(url_for('main.configuracao'))
                
                # Regra 2: Intervalo não pode ser maior que 60 dias
                if (end_date - start_date).days > 60:
                    flash('Erro: O intervalo entre a data inicial e a final não pode ser maior que 60 dias.', 'error')
                    # Recarrega a página de configuração sem salvar
                    return redirect(url_for('main.configuracao'))

            except ValueError:
                flash('Formato de data inválido.', 'error')
                return redirect(url_for('main.configuracao'))
        # --- FIM DA VALIDAÇÃO DE DATAS NO BACKEND ---

        # Se a validação passar, o código de salvamento continua normalmente
        configs_to_save = {
            'URL_LOGIN': request.form.get('URL_LOGIN'),
            'USUARIO_ROBO': request.form.get('USUARIO_ROBO'),
            'SENHA_ROBO': request.form.get('SENHA_ROBO'),
            'CODIGO_VIAGENS_CLIENTE': request.form.get('CODIGO_VIAGENS_CLIENTE'),
            'CODIGO_VIAGENS_FAT_CLIENTE': request.form.get('CODIGO_VIAGENS_FAT_CLIENTE'),
            'CODIGO_CONTAS_PAGAR': request.form.get('CODIGO_CONTAS_PAGAR'),
            'CODIGO_CONTAS_RECEBER': request.form.get('CODIGO_CONTAS_RECEBER'),
            'CODIGO_DESPESAS': request.form.get('CODIGO_DESPESAS'),
            'CODIGO_ACERTO_MOTORISTA': request.form.get('CODIGO_ACERTO_MOTORISTA'),  
            'DATA_INICIAL_ROBO': datetime.strptime(start_date_str, '%Y-%m-%d').strftime('%d/%m/%Y') if start_date_str else '',
            'DATA_FINAL_ROBO': datetime.strptime(end_date_str, '%Y-%m-%d').strftime('%d/%m/%Y') if end_date_str else '',
            'live_monitoring_enabled': 'live_monitoring_enabled' in request.form
        }
        logic.salvar_configuracoes_robo(apartamento_id_alvo, configs_to_save)
        flash('Configurações salvas com sucesso!', 'success')
        return redirect(url_for('main.configuracao'))
    
    # Lógica para GET (exibir a página) permanece a mesma
    configs_salvas = logic.ler_configuracoes_robo(apartamento_id_alvo)
    try:
        if configs_salvas.get('DATA_INICIAL_ROBO'):
            configs_salvas['DATA_INICIAL_ROBO_YMD'] = datetime.strptime(configs_salvas['DATA_INICIAL_ROBO'], '%d/%m/%Y').strftime('%Y-%m-%d')
        if configs_salvas.get('DATA_FINAL_ROBO'):
            configs_salvas['DATA_FINAL_ROBO_YMD'] = datetime.strptime(configs_salvas['DATA_FINAL_ROBO'], '%d/%m/%Y').strftime('%Y-%m-%d')
    except (ValueError, TypeError):
        pass
    
    return render_template('configuracao.html', configs=configs_salvas)
@main_bp.route('/gerenciar-usuarios')
@login_required
def gerenciar_usuarios():
    if not is_admin_in_context():
        flash('Acesso negado.', 'error')
        return redirect(url_for('main.index'))
    
    apartamento_id_alvo = get_target_apartment_id()
    users = logic.get_users_for_apartment(apartamento_id_alvo)
    return render_template('gerenciar_usuarios.html', users=users)

@main_bp.route('/gerenciar-usuarios/adicionar', methods=['POST'])
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
        return redirect(url_for('main.gerenciar_usuarios'))

    password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    success, message = logic.add_user_to_apartment(
        apartamento_id=apartamento_id_alvo, nome=nome, email=email,
        password_hash=password_hash, role=role
    )

    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    return redirect(url_for('main.gerenciar_usuarios'))

@main_bp.route('/gerenciar-usuarios/dados/<int:user_id>', methods=['GET'])
@login_required
def get_user_data(user_id):
    if not is_admin_in_context():
        return jsonify({'error': 'Acesso negado'}), 403
    
    apartamento_id_alvo = get_target_apartment_id()
    user = logic.get_user_by_id(user_id, apartamento_id_alvo)
    if user:
        return jsonify(user)
    return jsonify({'error': 'Utilizador não encontrado'}), 404

@main_bp.route('/gerenciar-usuarios/editar/<int:user_id>', methods=['POST'])
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
        return redirect(url_for('main.gerenciar_usuarios'))

    new_password_hash = bcrypt.generate_password_hash(password).decode('utf-8') if password else None
    success, message = logic.update_user_in_apartment(
        user_id=user_id, apartamento_id=apartamento_id_alvo, nome=nome,
        email=email, role=role, new_password_hash=new_password_hash
    )

    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    return redirect(url_for('main.gerenciar_usuarios'))

@main_bp.route('/gerenciar-usuarios/apagar/<int:user_id>', methods=['POST'])
@login_required
def apagar_usuario(user_id):
    if not is_admin_in_context():
        return jsonify({'success': False, 'message': 'Acesso negado.'}), 403
    
    apartamento_id_alvo = get_target_apartment_id()
    if user_id == current_user.id:
        flash('Não pode apagar a sua própria conta de administrador.', 'error')
        return redirect(url_for('main.gerenciar_usuarios'))

    success, message = logic.delete_user_from_apartment(user_id, apartamento_id_alvo)
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    return redirect(url_for('main.gerenciar_usuarios'))

@main_bp.route('/super-admin', methods=['GET', 'POST']) # <-- Adicionado 'POST'
@login_required
@super_admin_required
def admin_dashboard():
    # --- INÍCIO DA CORREÇÃO (LÓGICA PARA SALVAR) ---
    if request.method == 'POST':
        # Itera sobre todos os dados enviados pelo formulário
        for key, value in request.form.items():
            # Verifica se é um campo de intervalo (ex: 'interval_2')
            if key.startswith('interval_'):
                try:
                    # Extrai o ID do apartamento do nome do campo
                    apartamento_id = int(key.split('_')[1])
                    # Cria um dicionário com a chave e valor a serem salvos
                    config_para_salvar = {'live_monitoring_interval_minutes': value}
                    # Chama a função de lógica para salvar a configuração
                    logic.salvar_configuracoes_robo(apartamento_id, config_para_salvar)
                except (ValueError, IndexError):
                    flash(f'Erro ao processar o intervalo para o campo {key}.', 'error')
        
        flash('Intervalos atualizados com sucesso!', 'success')
        return redirect(url_for('main.admin_dashboard'))
    # --- FIM DA CORREÇÃO ---

    # A lógica para exibir a página (GET) permanece a mesma
    session.pop('force_customer_view', None)
    session.pop('viewing_apartment_id', None)
    apartamentos = logic.get_apartments_with_usage_stats()
    for apt in apartamentos:
        if apt.get('slug'):
            apt['access_link'] = url_for('auth.login_por_slug', slug=apt['slug'], _external=True)
        else:
            apt['access_link'] = "Sem slug definido"
    
    return render_template('super_admin/dashboard.html', apartamentos=apartamentos)

@main_bp.route('/super-admin/limpar-dados/<int:apartamento_id>', methods=['POST'])
@login_required
@super_admin_required
def limpar_dados_apartamento(apartamento_id):
    try:
        limpar_dados_importados(apartamento_id)
        flash(f'Dados do apartamento {apartamento_id} limpos com sucesso.', 'success')
        return jsonify({'status': 'success', 'message': 'Dados limpos.'})
    except Exception as e:
        flash(f'Erro ao limpar dados do apartamento {apartamento_id}: {e}', 'error')
        return jsonify({'status': 'error', 'message': 'Erro ao limpar dados.'}), 500

@main_bp.route('/super-admin/criar', methods=['GET', 'POST'])
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
            return render_template('super_admin/criar_apartamento.html')

        password_hash = bcrypt.generate_password_hash(admin_password).decode('utf-8')
        success, message = logic.create_apartment_and_admin(nome_empresa, admin_nome, admin_email, password_hash)

        if success:
            flash(message, 'success')
            return redirect(url_for('main.admin_dashboard'))
        else:
            flash(message, 'error')
            return render_template('super_admin/criar_apartamento.html')
    return render_template('super_admin/criar_apartamento.html')

@main_bp.route('/super-admin/gerir/<int:apartamento_id>', methods=['GET', 'POST'])
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
        
        return redirect(url_for('main.admin_dashboard'))

    apartamento = logic.get_apartment_details(apartamento_id)
    if not apartamento:
        flash("Apartamento não encontrado.", "error")
        return redirect(url_for('main.admin_dashboard'))
    
    return render_template('super_admin/gerir_apartamento.html', apartamento=apartamento)

@main_bp.cli.command("criar-admin")
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