import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class Config:
    # 系统配置
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
    DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'
    
    # 路径配置
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    TEMPLATES_DIR = os.path.join(DATA_DIR, 'templates')
    KNOWLEDGE_DIR = os.path.join(DATA_DIR, 'knowledge')
    RULES_DIR = os.path.join(DATA_DIR, 'rules')
    
    # 模型配置
    NLP_MODEL = os.environ.get('NLP_MODEL', 'zh_core_web_sm')
    
    # 服务配置
    API_PREFIX = '/api'
    
    # 审查规则配置
    DEFAULT_RULES = {
        'required_sections': ['摘要', '引言', '设计方案', '验证结果', '结论'],
        'required_standards': ['GB/T 19001', 'AS9100'],
        'terminology_standards': '航空作动系统术语规范'
    }

# 创建配置实例
config = Config()