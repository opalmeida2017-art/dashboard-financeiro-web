# blueprints/super_admin.py
from flask import Blueprint, render_template, redirect, url_for, session, request, flash, jsonify
from flask_login import login_required
import logic
from limpar_dados import limpar_dados_importados

# --- CORREÇÃO ---
from extensions import bcrypt
from .helpers import super_admin_required
# --- FIM DA CORREÇÃO ---

super_admin_bp = Blueprint('super_admin', __name__, url_prefix='/super-admin')

@super_admin_bp.route('/')
@login_required
@super_admin_required
def admin_dashboard():
    session.pop('force_customer_view', None)
    session.pop('viewing_apartment_id', None)
    apartamentos = logic.get_apartments_with_usage_stats()
    for apt in apartamentos:
        if apt.get('slug'):
            apt['access_link'] = url_for('auth.login_por_slug', slug=apt['slug'], _external=True)
        else:
            apt['access_link'] = "Sem slug definido"
    
    return render_template('super_admin/dashboard.html', apartamentos=apartamentos)

@super_admin_bp.route('/visualizar/<int:apartamento_id>')
@login_required
@super_admin_required
def visualizar_como_cliente(apartamento_id):
    session['force_customer_view'] = True
    session['viewing_apartment_id'] = apartamento_id
    flash(f'Visualizando o dashboard para o Apartamento ID: {apartamento_id}. Para sair, use o botão "Sair".', 'info')
    return redirect(url_for('main.index'))

@super_admin_bp.route('/limpar-dados/<int:apartamento_id>', methods=['POST'])
@login_required
@super_admin_required
def limpar_dados_apartamento(apartamento_id):
    try:
        limpar_dados_importados(apartamento_id)
        flash(f'Dados do apartamento {apartamento_id} limpos com sucesso.', 'success')
        return jsonify({'status': 'success', 'message': 'Dados limpos.'})
    except Exception as e:
        flash(f'Erro ao limpar dados do apartamento {apartamento_id}: {e}', 'error')
        return jsonify({'status': 'error', 'message': f'Erro ao limpar dados: {e}'}), 500

@super_admin_bp.route('/criar', methods=['GET', 'POST'])
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
            return redirect(url_for('super_admin.admin_dashboard'))
        else:
            flash(message, 'error')
    return render_template('super_admin/criar_apartamento.html')

@super_admin_bp.route('/gerir/<int:apartamento_id>', methods=['GET', 'POST'])
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
        
        return redirect(url_for('super_admin.admin_dashboard'))

    apartamento = logic.get_apartment_details(apartamento_id)
    if not apartamento:
        flash("Apartamento não encontrado.", "error")
        return redirect(url_for('super_admin.admin_dashboard'))
    
    return render_template('super_admin/gerir_apartamento.html', apartamento=apartamento)