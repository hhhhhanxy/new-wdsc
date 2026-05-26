from config.base import BaseSettings
from config.dev import DevSettings
from config.prod import ProdSettings
from config.validator import validate_on_startup
import os


def create_settings() -> BaseSettings:
    """
    根据环境变量创建配置对象

    环境优先级:
    1. ENVIRONMENT 环境变量 (推荐)
    2. .env 文件中的 ENVIRONMENT
    3. 默认 'dev'

    Returns:
        BaseSettings: 配置对象
    """
    # 读取环境标识
    env = os.getenv("ENVIRONMENT", "dev").lower()

    if env == "prod":
        settings_cls = ProdSettings
    elif env == "dev":
        settings_cls = DevSettings
    else:
        # 默认使用开发环境配置
        settings_cls = DevSettings

    # 创建配置对象（会自动读取 .env 文件）
    settings = settings_cls()

    return settings


# 创建全局配置实例
settings = create_settings()

# 启动时验证配置
validate_on_startup(settings, verbose=True)

# 导出便于其他模块使用
__all__ = ["settings", "BaseSettings", "DevSettings", "ProdSettings", "create_settings"]
