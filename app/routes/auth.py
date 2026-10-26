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
    parent = slug_norm
    usuario = ""
    try:
        from infra.tenant_licensing.acesso_registry import get_acesso
        from infra.tenant_licensing.bi_tenant_context import tenant_slug_registrado

        if slug_norm and not tenant_slug_registrado(slug_norm):
            acesso = get_acesso(slug_norm)
            if acesso and acesso.get("ativo", True):
                parent = str(acesso.get("tenant_slug") or "").lower()
                usuario = slug_norm
    except Exception:
        pass
    if parent:
        session["bi_tenant_slug"] = parent
        set_tenant(parent)
    if usuario:
        session["bi_acesso_slug"] = usuario
    else:
        session.pop("bi_acesso_slug", None)
    try:
        from infra.tenant_licensing.bi_tenant_runtime import _biweb_multi_tenant_ativo
        if _biweb_multi_tenant_ativo():
            if usuario:
                return redirect(f"/acesso/{parent}/{usuario}")
            return redirect(f"/biweb/{parent}/")
    except Exception:
        pass
    return redirect(url_for('main.index'))


@auth_bp.route('/acesso/<tenant>/<usuario>', methods=['GET', 'POST'])
def login_por_usuario(tenant, usuario):
    from infra.tenant_licensing.acesso_registry import acesso_for_tenant
    from infra.tenant_licensing.bi_tenant_context import set_tenant, tenant_slug_registrado

    parent = str(tenant or "").strip().lower()
    user = str(usuario or "").strip().lower()
    if not parent or not tenant_slug_registrado(parent):
        return render_template("auth/tenant_nao_encontrado.html"), 404
    acesso = acesso_for_tenant(user, parent)
    if not acesso:
        return render_template("auth/tenant_nao_encontrado.html"), 404
    session["bi_tenant_slug"] = parent
    session["bi_acesso_slug"] = user
    set_tenant(parent)
    try:
        from infra.tenant_licensing.bi_tenant_runtime import _biweb_multi_tenant_ativo
        if _biweb_multi_tenant_ativo():
            return redirect(f"/biweb/{parent}/")
    except Exception:
        pass
    return redirect(url_for("main.index"))


@auth_bp.route('/logout')
def logout():
    logout_user()
    session.pop("bi_tenant_slug", None)
    session.pop("bi_acesso_slug", None)
    try:
        from infra.tenant_licensing.bi_tenant_runtime import _biweb_multi_tenant_ativo
        if _biweb_multi_tenant_ativo():
            return render_template("auth/acesso_negado.html"), 403
    except Exception:
        pass
    return redirect(url_for('main.index'))
