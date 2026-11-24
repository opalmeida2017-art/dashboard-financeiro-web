from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_user, logout_user
from sqlalchemy import text

from app.data.tenant import try_auto_login

auth_bp = Blueprint('auth', __name__)


def _auth_obrigatoria() -> bool:
    from app.security import auth_obrigatoria

    return auth_obrigatoria()


def _tenant_ok_para_login() -> bool:
    try:
        from infra.tenant_licensing.bi_tenant_runtime import _biweb_multi_tenant_ativo
        if not _biweb_multi_tenant_ativo():
            return True
    except Exception:
        return True
    from app.security import tenant_atual

    return bool(tenant_atual())


def _iniciar_sessao(user_id: int) -> None:
    from app.extensions import load_user
    from app.security import hash_fingerprint, tenant_atual

    user = load_user(user_id)
    tenant = session.get("bi_tenant_slug")
    acesso = session.get("bi_acesso_slug")
    session.clear()
    if tenant:
        session["bi_tenant_slug"] = tenant
    if acesso:
        session["bi_acesso_slug"] = acesso
    session.permanent = True
    login_user(user, remember=False)
    session["auth_tenant"] = tenant_atual()
    session["auth_fp"] = hash_fingerprint(user.password_hash, user.email)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if not _auth_obrigatoria():
        try:
            from infra.tenant_licensing.bi_tenant_runtime import _biweb_multi_tenant_ativo
            if _biweb_multi_tenant_ativo():
                return render_template("auth/acesso_negado.html"), 403
        except Exception:
            pass
        try_auto_login()
        return redirect(url_for('main.index'))

    from app.security import (
        EMAILS_BLOQUEADOS, destino_seguro, login_bloqueado, registrar_acesso, usuario_autenticado,
    )

    if not _tenant_ok_para_login():
        return render_template("auth/acesso_negado.html"), 403
    nxt = request.values.get("next", "")
    if request.method == 'GET' and usuario_autenticado():
        return redirect(destino_seguro(nxt))

    erro = None
    email = ""
    if request.method == 'POST':
        email = (request.form.get("email") or "").strip().lower()
        senha = request.form.get("senha") or ""
        if login_bloqueado(email):
            erro = "Muitas tentativas. Aguarde 15 minutos e tente novamente."
            registrar_acesso(email, "login_bloqueado", False)
        else:
            from app.data.db_connection import engine
            from app.data.tenant import get_transportadora_id
            from app.extensions import bcrypt

            row = None
            if email and senha and email not in EMAILS_BLOQUEADOS:
                with engine.connect() as conn:
                    row = conn.execute(
                        text(
                            "SELECT id, password_hash FROM usuarios "
                            "WHERE LOWER(email) = :e AND apartamento_id = :tid"
                        ),
                        {"e": email, "tid": get_transportadora_id()},
                    ).first()
            ok = False
            if row:
                try:
                    ok = bcrypt.check_password_hash(row[1], senha)
                except ValueError:
                    ok = False
            registrar_acesso(email, "login", ok)
            if ok:
                _iniciar_sessao(int(row[0]))
                return redirect(destino_seguro(nxt))
            erro = "E-mail ou senha inválidos."
    from app.data.tenant import get_transportadora_nome_exibicao

    return render_template(
        "auth/login.html", erro=erro, email=email, next=nxt,
        transportadora_nome=get_transportadora_nome_exibicao(),
    ), (401 if erro else 200)


@auth_bp.route('/definir-senha/<token>', methods=['GET', 'POST'])
def definir_senha(token):
    from app.security import (
        hash_fingerprint, ler_token_convite, registrar_acesso, tenant_atual, validar_nova_senha,
    )
    from app.data.db_connection import engine
    from app.extensions import bcrypt

    dados = ler_token_convite(token)
    row = None
    if dados and dados.get("t", "") == tenant_atual():
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT id, email, nome, password_hash FROM usuarios WHERE id = :id"),
                {"id": int(dados.get("u") or 0)},
            ).mappings().first()
        if row and hash_fingerprint(row["password_hash"], row["email"]) != dados.get("h"):
            row = None
    if not row:
        return render_template("auth/definir_senha.html", invalido=True), 400

    erro = None
    if request.method == 'POST':
        senha = request.form.get("senha") or ""
        erro = validar_nova_senha(senha, request.form.get("confirmacao") or "", row["email"])
        if not erro:
            ph = bcrypt.generate_password_hash(senha).decode("utf-8")
            with engine.begin() as conn:
                conn.execute(
                    text("UPDATE usuarios SET password_hash = :h WHERE id = :id"),
                    {"h": ph, "id": row["id"]},
                )
            registrar_acesso(row["email"], "definir_senha", True)
            flash("Senha definida. Entre com seu e-mail e a nova senha.", "success")
            return redirect(url_for("auth.login"))
    return render_template("auth/definir_senha.html", invalido=False, erro=erro, usuario=row)


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
    if _auth_obrigatoria():
        from app.security import registrar_acesso

        if current_user.is_authenticated:
            registrar_acesso(getattr(current_user, "email", ""), "logout", True)
        logout_user()
        session.pop("auth_tenant", None)
        return redirect(url_for("auth.login"))
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
