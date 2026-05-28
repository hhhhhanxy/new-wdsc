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
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), '..', 'uploads')
    app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

    # Ensure upload directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Initialize database
    from web.models import Database
    db = Database()
    app.db = db

    # Register blueprints
    from web.routes import bp as index_bp
    from web.routes.review import bp as review_bp
    from web.routes.generate import bp as generate_bp
    from web.routes.rules import bp as rules_bp

    app.register_blueprint(index_bp)
    app.register_blueprint(review_bp, url_prefix='/review')
    app.register_blueprint(generate_bp, url_prefix='/generate')
    app.register_blueprint(rules_bp, url_prefix='/rules')

    # Load extensions
    from extensions.registry import get_registry
    get_registry().load_extensions()

    return app

# Create app instance
app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
