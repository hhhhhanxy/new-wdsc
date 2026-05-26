import hashlib
import json
import logging
from typing import Any, Optional, Callable
from functools import wraps
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CacheEntry:
    """缓存条目"""
    def __init__(self, value: Any, ttl: int):
        self.value = value
        self.created_at = datetime.now()
        self.ttl = ttl

    def is_expired(self) -> bool:
        """检查是否过期"""
        return datetime.now() - self.created_at > timedelta(seconds=self.ttl)


class SimpleCache:
    """
    简单的内存缓存实现
    """
    def __init__(self):
        self._cache: dict = {}

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        entry = self._cache.get(key)
        if entry is None:
            return None

        if entry.is_expired():
            del self._cache[key]
            return None

        return entry.value

    def set(self, key: str, value: Any, ttl: int = 3600):
        """设置缓存值"""
        self._cache[key] = CacheEntry(value, ttl)

    def delete(self, key: str):
        """删除缓存值"""
        if key in self._cache:
            del self._cache[key]

    def clear(self):
        """清空缓存"""
        self._cache.clear()

    def size(self) -> int:
        """获取缓存大小"""
        return len(self._cache)


# 全局缓存实例
_global_cache = SimpleCache()


def get_cache() -> SimpleCache:
    """获取全局缓存实例"""
    return _global_cache


def generate_cache_key(*args, **kwargs) -> str:
    """
    生成缓存键

    Args:
        *args: 位置参数
        **kwargs: 关键字参数

    Returns:
        缓存键
    """
    # 将参数序列化为字符串
    key_parts = []

    for arg in args:
        if isinstance(arg, str):
            key_parts.append(arg)
        else:
            key_parts.append(str(hash(str(arg))))

    for k, v in sorted(kwargs.items()):
        key_parts.append(f"{k}={v}")

    key_string = ":".join(key_parts)

    # 使用 MD5 生成短键
    return hashlib.md5(key_string.encode()).hexdigest()[:16]


def cached(
    ttl: int = None,
    key_prefix: str = "",
    enabled: bool = True,
):
    """
    缓存装饰器

    Args:
        ttl: 缓存过期时间（秒），默认从配置读取
        key_prefix: 缓存键前缀
        enabled: 是否启用缓存
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 延迟导入配置
            from config.settings import settings

            if not enabled or not settings.cache_enabled:
                return func(*args, **kwargs)

            actual_ttl = ttl or settings.cache_ttl

            # 生成缓存键
            cache_key = key_prefix + generate_cache_key(func.__name__, *args, **kwargs)

            # 尝试从缓存获取
            cache = get_cache()
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"缓存命中: {cache_key}")
                return cached_value

            # 执行函数
            result = func(*args, **kwargs)

            # 存入缓存
            cache.set(cache_key, result, actual_ttl)
            logger.debug(f"缓存存入: {cache_key}")

            return result

        return wrapper
    return decorator


def clear_cache():
    """清空全局缓存"""
    _global_cache.clear()
    logger.info("缓存已清空")


def cache_info() -> dict:
    """获取缓存信息"""
    cache = get_cache()
    return {
        "size": cache.size(),
        "keys": list(cache._cache.keys())
    }
