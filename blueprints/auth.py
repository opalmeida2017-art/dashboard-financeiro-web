# blueprints/auth.py (Final Corrected Version)
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_login import login_user, logout_user, current_user, login_required
from sqlalchemy import text
import logic

# --- CORRECTION ---
from extensions import bcrypt, load_user
from db_connection import engine
# --- END CORRECTION ---

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

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
                return redirect(url_for('main.index'))
        
        flash('Email ou senha inválidos. Tente novamente.', 'error')
    return render_template('login.html')

# ... (rest of your auth.py file remains the same)
@auth_bp.route('/acesso/<slug>', methods=['GET', 'POST'])
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
            is_super_admin = (email == current_app.config['SUPER_ADMIN_EMAIL'])
            if not is_super_admin and (user_data['apartamento_id'] != apartamento['id']):
                flash('Este utilizador não pertence a esta empresa.', 'error')
                return redirect(url_for('auth.login_por_slug', slug=slug))

            user = load_user(user_data['id'])
            if user:
                login_user(user)
                if is_super_admin:
                    session['force_customer_view'] = True
                    session['viewing_apartment_id'] = apartamento['id']
                return redirect(url_for('main.index'))
        
        flash('Email ou senha inválidos. Tente novamente.', 'error')
    return render_template('login.html', apartamento=apartamento, nome_empresa=apartamento['nome_empresa'])

@auth_bp.route('/logout')
@login_required
def logout():
    session.pop('force_customer_view', None)
    session.pop('viewing_apartment_id', None)
    logout_user()
    return redirect(url_for('auth.login'))