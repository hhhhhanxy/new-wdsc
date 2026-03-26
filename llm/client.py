from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from openai import OpenAI
from config.settings import settings


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
        self.api_key = api_key or settings.llm_api_key
        self.base_url = base_url or settings.llm_base_url
        self.model = model or settings.llm_model
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
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
