from flask import Blueprint, redirect, url_for

from flask_login import logout_user

from tenant import try_auto_login

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Instalação única: login manual desativado; redireciona ao painel."""
    try_auto_login()
    return redirect(url_for('main.index'))


@auth_bp.route('/acesso/<slug>', methods=['GET', 'POST'])
def login_por_slug(slug):
    return redirect(url_for('main.index'))


@auth_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.index'))
