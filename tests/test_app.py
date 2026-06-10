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


def test_healthz():
    """Test that the web health check responds."""
    response = app.test_client().get('/healthz')
    assert response.status_code == 200
    assert response.get_json()["ok"] is True


def test_default_llm_config_uses_siliconflow_deepseek():
    """Document review and generation share this default LLM config."""
    from config.base import BaseSettings

    assert BaseSettings.model_fields["llm_provider"].default == "siliconflow"
    assert BaseSettings.model_fields["llm_base_url"].default == "https://api.siliconflow.cn/v1"
    assert BaseSettings.model_fields["llm_model"].default == "deepseek-ai/DeepSeek-V3.2"
