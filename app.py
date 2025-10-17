# app.py (Final Definitive Version)
from dotenv import load_dotenv
load_dotenv()
from db_connection import engine
import os
from flask import Flask

# Import extensions from the new file
from extensions import bcrypt, login_manager

# --- FACTORY DE CRIAÇÃO DA APLICAÇÃO ---
def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'uma-chave-secreta-muito-dificil-de-adivinhar')
    app.config['SUPER_ADMIN_EMAIL'] = 'op.almeida@hotmail.com'
    
    # Initialize extensions with the application
    bcrypt.init_app(app)
    login_manager.init_app(app)
    
    login_manager.login_view = 'auth.login'
    login_manager.login_message = "Por favor, faça login para aceder a esta página."
    login_manager.login_message_category = "info"

    # Import and register Blueprints INSIDE the factory
    from blueprints.main import main_bp
    from blueprints.auth import auth_bp
    from blueprints.api import api_bp
    from blueprints.super_admin import super_admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(super_admin_bp)

    # Filters and Context Processors
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
        return dict(is_admin_in_context=is_admin_in_context)

    return app

# --- EXECUTION ---
app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)