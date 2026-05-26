from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import logging
from functools import wraps
from typing import Type, Tuple, Any, Callable
import sys

logger = logging.getLogger(__name__)


class LLMRetryError(Exception):
    """LLM 重试失败异常"""
    pass


def llm_retry(
    max_attempts: int = None,
    min_wait: int = None,
    max_wait: int = None,
    retry_on: Tuple[Type[Exception], ...] = (Exception,),
):
    """
    LLM 调用重试装饰器

    Args:
        max_attempts: 最大重试次数（默认从配置读取）
        min_wait: 最小等待时间（默认从配置读取）
        max_wait: 最大等待时间（默认从配置读取）
        retry_on: 需要重试的异常类型
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # 延迟导入配置，避免循环导入
            from config.settings import settings

            actual_max_attempts = max_attempts or settings.retry_max_attempts
            actual_min_wait = min_wait or settings.retry_min_wait
            actual_max_wait = max_wait or settings.retry_max_wait

            if not settings.retry_enabled:
                return func(*args, **kwargs)

            @retry(
                stop=stop_after_attempt(actual_max_attempts),
                wait=wait_exponential(multiplier=1, min=actual_min_wait, max=actual_max_wait),
                retry=retry_if_exception_type(retry_on),
                before_sleep=before_sleep_log(logger, logging.WARNING),
                reraise=True,
            )
            def _retry_func(*args, **kwargs):
                return func(*args, **kwargs)

            try:
                return _retry_func(*args, **kwargs)
            except Exception as e:
                logger.error(f"LLM 调用失败，已重试 {actual_max_attempts} 次: {str(e)}")
                raise LLMRetryError(f"LLM 调用失败: {str(e)}") from e

        return wrapper
    return decorator


def safe_execute(func: Callable, fallback: Any = None, log_error: bool = True) -> Any:
    """
    安全执行函数，捕获所有异常

    Args:
        func: 要执行的函数
        fallback: 失败时的返回值
        log_error: 是否记录错误

    Returns:
        函数执行结果或 fallback
    """
    try:
        return func()
    except Exception as e:
        if log_error:
            logger.error(f"执行函数 {func.__name__} 失败: {str(e)}")
        return fallback


class CircuitBreaker:
    """
    简单的断路器实现，防止连续调用失败的服务
    """
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open

    def call(self, func: Callable, *args, **kwargs):
        """
        通过断路器调用函数

        Args:
            func: 要调用的函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            函数执行结果

        Raises:
            Exception: 断路器开启时抛出异常
        """
        import time

        if self.state == "open":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "half-open"
            else:
                raise Exception("断路器开启，服务暂时不可用")

        try:
            result = func(*args, **kwargs)
            if self.state == "half-open":
                self.state = "closed"
                self.failures = 0
            return result
        except Exception as e:
            self.failures += 1
            self.last_failure_time = time.time()

            if self.failures >= self.failure_threshold:
                self.state = "open"
                logger.warning(f"断路器开启，失败次数: {self.failures}")

            raise e
