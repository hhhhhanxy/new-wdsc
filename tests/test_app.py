"""
Tests for Flask application initialization.
"""
from web.app import app

def test_app_exists():
    """Test that Flask app can be imported"""
    assert app is not None
    assert app.name == 'web.app'

def test_app_config():
    """Test that app has required configuration"""
    assert app.config['SECRET_KEY'] is not None
    assert app.config['UPLOAD_FOLDER'] is not None
    assert app.config['MAX_CONTENT_LENGTH'] == 50 * 1024 * 1024


def test_knowledge_page_loads():
    """Test that the reserved knowledge page renders."""
    response = app.test_client().get('/knowledge/')
    assert response.status_code == 200
    assert '知识库'.encode('utf-8') in response.data
