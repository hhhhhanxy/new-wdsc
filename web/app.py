"""
Flask application for document review and generation platform.
"""
from flask import Flask
import os

def create_app():
    """Create and configure Flask application"""
    app = Flask(__name__)

    # Configuration
    secret_key = os.environ.get('SECRET_KEY')
    if not secret_key:
        import secrets
        secret_key = secrets.token_hex(32)
    app.config['SECRET_KEY'] = secret_key
    default_upload_folder = os.path.join(os.path.dirname(__file__), '..', 'uploads')
    app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', default_upload_folder)
    app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

    # Ensure upload directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Initialize database
    from web.models import Database
    db = Database(os.environ.get('DATABASE_PATH', 'web/database.db'))
    app.db = db

    # Register blueprints
    from web.routes import bp as index_bp
    from web.routes.review import bp as review_bp
    from web.routes.generate import bp as generate_bp
    from web.routes.records import bp as records_bp
    from web.routes.rules import bp as rules_bp
    from web.routes.knowledge import bp as knowledge_bp
    from web.routes.template_library import bp as template_library_bp
    from web.routes.options import bp as options_bp

    app.register_blueprint(index_bp)
    app.register_blueprint(review_bp, url_prefix='/review')
    app.register_blueprint(generate_bp, url_prefix='/generate')
    app.register_blueprint(records_bp, url_prefix='/records')
    app.register_blueprint(rules_bp, url_prefix='/rules')
    app.register_blueprint(knowledge_bp, url_prefix='/knowledge')
    app.register_blueprint(template_library_bp, url_prefix='/template-library')
    app.register_blueprint(options_bp)

    @app.context_processor
    def inject_sidebar_options():
        from web.option_registry import get_specialties

        return {
            'review_specialties': get_specialties('review'),
            'generate_specialties': get_specialties('generate'),
        }

    # Load extensions
    from extensions.registry import get_registry
    get_registry().load_extensions()

    return app

# Create app instance
app = create_app()

if __name__ == '__main__':
    app.run(debug=False, host='127.0.0.1', port=5000, use_reloader=False)
