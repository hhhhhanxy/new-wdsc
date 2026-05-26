"""
Application launcher for the web interface.
"""
from web.app import app
import os

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'True').lower() == 'true'

    print(f"Starting Web Interface on http://localhost:{port}")
    print(f"Upload directory: {app.config['UPLOAD_FOLDER']}")
    print(f"Database: {app.db.db_path}")

    app.run(debug=debug, host='0.0.0.0', port=port)
