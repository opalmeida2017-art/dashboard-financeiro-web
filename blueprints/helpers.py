# blueprints/helpers.py
from flask import session, flash, redirect, url_for, request, current_app
from flask_login import current_user
from functools import wraps
from datetime import datetime

def get_target_apartment_id():
    if session.get('force_customer_view') and 'viewing_apartment_id' in session:
        return session['viewing_apartment_id']
    elif current_user.is_authenticated:
        return current_user.apartamento_id
    return None

def is_admin_in_context():
    if not current_user.is_authenticated:
        return False
    is_normal_admin = (current_user.role == 'admin')
    is_impersonating_admin = (
        current_user.email == current_app.config['SUPER_ADMIN_EMAIL'] and
        session.get('force_customer_view')
    )
    return is_normal_admin or is_impersonating_admin

def super_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.email != current_app.config['SUPER_ADMIN_EMAIL']:
            flash("Acesso negado. Esta área é restrita.", "error")
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

def parse_filters(args):
    filters = {
        'placa': args.get('placa', 'Todos'),
        'filial': args.getlist('filial'),
        'start_date_str': args.get('start_date', ''),
        'end_date_str': args.get('end_date', ''),
        'tipo_negocio': args.get('tipo_negocio', 'Todos')
    }
    try:
        filters['start_date_obj'] = datetime.strptime(filters['start_date_str'], '%Y-%m-%d') if filters['start_date_str'] else None
        filters['end_date_obj'] = datetime.strptime(filters['end_date_str'], '%Y-%m-%d').replace(hour=23, minute=59, second=59) if filters['end_date_str'] else None
    except ValueError:
        filters['start_date_obj'] = None
        filters['end_date_obj'] = None
    return filters