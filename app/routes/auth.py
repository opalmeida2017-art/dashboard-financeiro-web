from flask import Blueprint, redirect, url_for, session, render_template

from flask_login import logout_user

from app.data.tenant import try_auto_login

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Instalação única: login manual desativado; redireciona ao painel."""
    try:
        from infra.tenant_licensing.bi_tenant_runtime import _biweb_multi_tenant_ativo
        if _biweb_multi_tenant_ativo():
            return render_template("auth/acesso_negado.html"), 403
    except Exception:
        pass
    try_auto_login()
    return redirect(url_for('main.index'))


@auth_bp.route('/acesso/<slug>', methods=['GET', 'POST'])
def login_por_slug(slug):
    from infra.tenant_licensing.bi_tenant_context import set_tenant

    slug_norm = str(slug or "").strip().lower()
    if slug_norm:
        session["bi_tenant_slug"] = slug_norm
        set_tenant(slug_norm)
    try:
        from infra.tenant_licensing.bi_tenant_runtime import _biweb_multi_tenant_ativo
        if _biweb_multi_tenant_ativo():
            return redirect(f"/biweb/{slug_norm}/")
    except Exception:
        pass
    return redirect(url_for('main.index'))


@auth_bp.route('/logout')
def logout():
    logout_user()
    session.pop("bi_tenant_slug", None)
    try:
        from infra.tenant_licensing.bi_tenant_runtime import _biweb_multi_tenant_ativo
        if _biweb_multi_tenant_ativo():
            return render_template("auth/acesso_negado.html"), 403
    except Exception:
        pass
    return redirect(url_for('main.index'))
