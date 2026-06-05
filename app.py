#Teste de versao Final Definitive Version - Corrigido)

import os

from biweb_env import load_env

load_env()

from flask import Flask, request, redirect, url_for, session

from werkzeug.middleware.proxy_fix import ProxyFix

from flask_login import current_user



from extensions import bcrypt, login_manager

from tenant import (
    ensure_local_admin,
    ensure_transportadora,
    get_transportadora_id,
    get_transportadora_nome,
    try_auto_login,
)
from biweb_paths import is_frozen, resource_root



# --- FACTORY DE CRIAÇÃO DA APLICAÇÃO ---

def create_app():

    if is_frozen():
        app = Flask(
            __name__,
            template_folder=str(resource_root() / "templates"),
            static_folder=str(resource_root() / "static"),
        )
    else:
        app = Flask(__name__)

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'uma-chave-secreta-muito-dificil-de-adivinhar')

    upload_folder_path = os.path.join(app.root_path, 'static', 'uploads')

    os.makedirs(upload_folder_path, exist_ok=True)

    app.config['UPLOAD_FOLDER'] = upload_folder_path

    app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}



    bcrypt.init_app(app)

    login_manager.init_app(app)



    login_manager.login_view = 'main.index'

    login_manager.login_message = None



    with app.app_context():

        tid = ensure_transportadora()
        ensure_local_admin(tid)



    from blueprints.main import main_bp

    from blueprints.auth import auth_bp

    from blueprints.api import api_bp



    app.register_blueprint(main_bp)

    app.register_blueprint(auth_bp)

    app.register_blueprint(api_bp)



    from blueprints.helpers import is_admin_in_context



    @app.template_filter('currency')

    def format_currency(value):

        if value is None or not isinstance(value, (int, float)):

            return "R$ 0,00"

        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")



    @app.template_filter('percentage')

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
        return dict(
            is_admin_in_context=is_admin_in_context,
            transportadora_nome=get_transportadora_nome(),
            transportadora_id=get_transportadora_id(),
            usuario_nome=nome_ui,
        )



    @app.before_request
    def biweb_desktop_setup_gate():
        if not os.getenv("BIWEB_DESKTOP", "").strip():
            return
        allowed = {
            "static",
            "main.instalacao",
            "main.instalacao_atualizar",
            "main.iniciar_coleta_endpoint",
            "main.iniciar_atualizacao_bd_endpoint",
            "auth.login",
        }
        if request.endpoint in allowed:
            return
        from biweb_env import setup_completed

        if not setup_completed():
            return redirect(url_for("main.instalacao"))

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
        """Instalação única: sessão automática do administrador local."""
        biweb_clear_login_flashes()
        if request.endpoint in (
            "static",
            "main.instalacao",
            "main.instalacao_atualizar",
        ):
            return
        if not current_user.is_authenticated:
            try_auto_login()

    @app.before_request
    def biweb_registrar_atividade_sistema():
        """Marca atividade do usuário para disparar robôs só em ociosidade."""
        if request.endpoint in ("static",):
            return
        try:
            from fluxo_monitor import registrar_atividade

            tid = get_transportadora_id()
            if tid:
                registrar_atividade(int(tid), origem=request.endpoint or "http")
        except Exception:
            pass

    _iniciar_monitor_ocioso(app)

    return app


_idle_scheduler = None


def _iniciar_monitor_ocioso(app):
    """Agendador em background quando roda só o Flask (sem worker RQ)."""
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
                from fluxo_monitor import verificar_e_executar_tarefas_ociosas

                verificar_e_executar_tarefas_ociosas()
            except Exception as exc:
                print(f"[idle-monitor] {exc}")

    sched = BackgroundScheduler(daemon=True)
    sched.add_job(_tick, "interval", minutes=intervalo, id="biweb_idle_monitor")
    sched.start()
    _idle_scheduler = sched



app = create_app()



if __name__ == '__main__':

    # Robô com Chrome visível em dev; no .exe o launcher define ROBO_HEADLESS=true
    os.environ.setdefault("ROBO_HEADLESS", "false")

    app.run(host='0.0.0.0', port=5000, debug=True)

