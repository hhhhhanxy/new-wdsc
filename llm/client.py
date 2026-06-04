from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import logging
import os

import httpx
from openai import OpenAI
from config.settings import settings

logger = logging.getLogger(__name__)


def _get_float_setting(name: str, default: float) -> float:
    value = getattr(settings, name, None)
    if value is None:
        env_name = name.upper()
        value = os.getenv(env_name)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _get_bool_setting(name: str, default: bool) -> bool:
    value = getattr(settings, name, None)
    if value is None:
        value = os.getenv(name.upper())
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class LLMResponse:
    content: str
    model: str
    usage: Dict[str, int]
    finish_reason: str


class BaseLLMClient(ABC):
    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        pass


class OpenAIClient(BaseLLMClient):
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.api_key = api_key or settings.get_api_key()
        self.base_url = base_url or settings.llm_base_url
        self.model = model or settings.llm_model
        llm_timeout = _get_float_setting("llm_timeout", 120.0)
        llm_connect_timeout = _get_float_setting("llm_connect_timeout", 30.0)
        llm_trust_env = _get_bool_setting("llm_trust_env", True)
        timeout = httpx.Timeout(
            llm_timeout,
            connect=llm_connect_timeout,
        )
        http_client = httpx.Client(
            timeout=timeout,
            trust_env=llm_trust_env,
        )

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=timeout,
            http_client=http_client,
        )
        logger.info(
            "LLM 客户端初始化完成 - provider=%s, model=%s, base_url=%s, timeout=%ss, connect_timeout=%ss, trust_env=%s",
            settings.llm_provider,
            self.model,
            self.base_url,
            llm_timeout,
            llm_connect_timeout,
            llm_trust_env,
        )
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=settings.max_tokens,
            temperature=settings.temperature
        )
        
        return LLMResponse(
            content=response.choices[0].message.content,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            },
            finish_reason=response.choices[0].finish_reason
        )
    



class LLMClientFactory:
    _clients = {
        "openai": OpenAIClient,
        "siliconflow": OpenAIClient,
    }
    
    @classmethod
    def create_client(cls, provider: str = "openai", **kwargs) -> BaseLLMClient:
        client_class = cls._clients.get(provider.lower())
        if client_class:
            return client_class(**kwargs)
        raise ValueError(f"Unknown LLM provider: {provider}")
    
    @classmethod
    def register_client(cls, provider: str, client_class: type):
        cls._clients[provider.lower()] = client_class
