# BIWEB — painel de gestão de transporte (100% Web / SaaS)

import os
import sys

from app.utils.env_loader import load_env

load_env()

from flask import Flask, redirect, render_template, request, session, url_for
from flask_login import current_user
from werkzeug.middleware.proxy_fix import ProxyFix

from app.data.tenant import (
    ensure_local_admin,
    ensure_transportadora,
    get_transportadora_id,
    get_transportadora_nome_exibicao,
    nome_exibicao_navbar,
    try_auto_login,
)
from app.extensions import bcrypt, login_manager


def create_app() -> Flask:
    frontend = os.path.join(os.path.dirname(__file__), "..", "frontend")
    app = Flask(
        __name__,
        template_folder=os.path.join(frontend, "templates"),
        static_folder=os.path.join(frontend, "static"),
        static_url_path="/static",
    )

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    app.config["SECRET_KEY"] = os.environ.get(
        "SECRET_KEY", "uma-chave-secreta-muito-dificil-de-adivinhar"
    )

    upload_folder_path = os.path.join(app.static_folder, "uploads")
    os.makedirs(upload_folder_path, exist_ok=True)
    app.config["UPLOAD_FOLDER"] = upload_folder_path
    app.config["ALLOWED_EXTENSIONS"] = {"png", "jpg", "jpeg", "gif"}

    bcrypt.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "main.index"
    login_manager.login_message = None

    with app.app_context():
        tid = ensure_transportadora()
        ensure_local_admin(tid)

    from app.routes.web import main_bp
    from app.routes.auth import auth_bp
    from app.routes.api import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp)

    from app.utils.helpers import is_admin_in_context

    @app.template_filter("currency")
    def format_currency(value):
        if value is None or not isinstance(value, (int, float)):
            return "R$ 0,00"
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    @app.template_filter("percentage")
    def format_percentage(value):
        if value is None or not isinstance(value, (int, float)):
            return "0,00%"
        return f"{value:.2f}".replace(".", ",") + "%"

    @app.context_processor
    def inject_user_roles():
        try_auto_login()
        nome_ui = (
            current_user.nome
            if current_user.is_authenticated
            else os.getenv("BIWEB_DEV_ADMIN_NOME", "Administrador")
        )
        from app.utils.tenant_urls import painel_home_url

        return dict(
            is_admin_in_context=is_admin_in_context,
            transportadora_nome=get_transportadora_nome_exibicao(),
            transportadora_id=get_transportadora_id(),
            usuario_nome=nome_exibicao_navbar(nome_ui),
            painel_home_url=painel_home_url,
        )

    @app.before_request
    def biweb_validar_slug_entrada():
        """Bloqueia /biweb/<slug>/ inválido (teste6, transportes-brasil-ltda, etc.)."""
        from infra.tenant_licensing.bi_tenant_context import tenant_slug_registrado
        from infra.tenant_licensing.bi_tenant_runtime import (
            _biweb_multi_tenant_ativo,
            _path_entrada_tenant,
            resolve_tenant_slug_from_request,
        )

        if not _biweb_multi_tenant_ativo():
            return
        if request.endpoint in ("static",) or (request.path or "").startswith("/static/"):
            return
        if not _path_entrada_tenant(request):
            return
        slug = resolve_tenant_slug_from_request(request)
        if not slug:
            return
        if tenant_slug_registrado(slug):
            return
        session.pop("bi_tenant_slug", None)
        return render_template("auth/tenant_nao_encontrado.html"), 404

    @app.before_request
    def biweb_require_tenant_link():
        from infra.tenant_licensing.bi_tenant_runtime import (
            _biweb_multi_tenant_ativo,
            _path_entrada_tenant,
            _request_tem_contexto_tenant,
            tenant_sessao_libera_rota_interna,
        )

        if not _biweb_multi_tenant_ativo():
            return
        if request.endpoint in ("static",) or (request.path or "").startswith("/static/"):
            return
        if _path_entrada_tenant(request):
            return
        if _request_tem_contexto_tenant(request):
            return
        if tenant_sessao_libera_rota_interna(request, session):
            return
        return render_template("auth/acesso_negado.html"), 403

    @app.before_request
    def biweb_switch_tenant():
        try:
            from infra.tenant_licensing.bi_tenant_context import (
                set_tenant,
                tenant_slug_registrado,
            )
            from infra.tenant_licensing.bi_tenant_runtime import (
                apply_tenant_env,
                resolve_tenant_slug_from_request,
            )
            from app.data.database import switch_engine_for_request

            slug = resolve_tenant_slug_from_request(request)
            slug_da_url = bool(slug)
            if not slug:
                slug = (session.get("bi_tenant_slug") or "").strip().lower() or None
            if not slug:
                return
            set_tenant(slug)
            if not apply_tenant_env(slug):
                if slug_da_url:
                    session.pop("bi_tenant_slug", None)
                    if not tenant_slug_registrado(slug):
                        return render_template("auth/tenant_nao_encontrado.html"), 404
                return
            session["bi_tenant_slug"] = slug
            switch_engine_for_request()
            tid = ensure_transportadora()
            ensure_local_admin(tid)
            try:
                from flask_login import current_user, logout_user

                if current_user.is_authenticated:
                    u_apt = getattr(current_user, "apartamento_id", None)
                    if u_apt is not None and int(u_apt) != int(tid):
                        logout_user()
                try_auto_login()
            except Exception:
                pass
        except Exception:
            pass

    @app.before_request
    def biweb_clear_login_flashes():
        flashes = session.get("_flashes")
        if not flashes:
            return
        cleaned = [
            item
            for item in flashes
            if "faça login" not in str(item[-1]).lower()
            and "faca login" not in str(item[-1]).lower()
        ]
        if len(cleaned) != len(flashes):
            session["_flashes"] = cleaned

    @app.before_request
    def biweb_auto_login():
        biweb_clear_login_flashes()
        if request.endpoint == "static":
            return
        if not current_user.is_authenticated:
            try_auto_login()

    @app.before_request
    def biweb_registrar_atividade_sistema():
        if request.endpoint in ("static",):
            return
        try:
            from infra.cloud.fluxo_monitor import registrar_atividade

            tid = get_transportadora_id()
            if tid:
                registrar_atividade(int(tid), origem=request.endpoint or "http")
        except Exception:
            pass

    _iniciar_monitor_ocioso(app)
    _iniciar_limpeza_chrome_zumbi(app)
    return app


_idle_scheduler = None


def _iniciar_monitor_ocioso(app: Flask) -> None:
    global _idle_scheduler
    if _idle_scheduler is not None:
        return
    if os.getenv("BIWEB_IDLE_MONITOR", "true").lower() in ("0", "false", "no", "off"):
        return
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        return

    try:
        intervalo = max(1, int(os.getenv("BIWEB_IDLE_CHECK_MINUTES", "2")))
    except ValueError:
        intervalo = 2

    def _tick():
        with app.app_context():
            try:
                from infra.cloud.fluxo_monitor import verificar_e_executar_tarefas_ociosas

                verificar_e_executar_tarefas_ociosas()
            except Exception as exc:
                print(f"[idle-monitor] {exc}")

    sched = BackgroundScheduler(daemon=True)
    sched.add_job(_tick, "interval", minutes=intervalo, id="biweb_idle_monitor")
    sched.start()
    _idle_scheduler = sched


_chrome_scheduler = None


def _iniciar_limpeza_chrome_zumbi(app: Flask) -> None:
    """Agendador periódico: mata Chrome/chromedriver órfãos no Debian."""
    global _chrome_scheduler
    if _chrome_scheduler is not None:
        return
    if not sys.platform.startswith("linux"):
        return
    if os.getenv("BIWEB_CHROME_CLEANUP", "true").lower() in ("0", "false", "no", "off"):
        return
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        return

    try:
        intervalo = max(5, int(os.getenv("BIWEB_CHROME_CLEANUP_MINUTES", "15")))
    except ValueError:
        intervalo = 15

    def _tick():
        with app.app_context():
            try:
                from sati_integration.robos.chrome_cleanup import (
                    limpar_chrome_orfaos,
                    limpar_perfis_antigos,
                )

                limpar_chrome_orfaos()
                limpar_perfis_antigos()
            except Exception as exc:
                print(f"[chrome-cleanup] {exc}")

    sched = BackgroundScheduler(daemon=True)
    sched.add_job(_tick, "interval", minutes=intervalo, id="biweb_chrome_cleanup")
    sched.start()
    _chrome_scheduler = sched


app = create_app()
