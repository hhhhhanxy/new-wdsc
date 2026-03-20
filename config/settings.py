from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    llm_api_key: str = "sk-mdqrrduahosrkudfrpxahoveroutolvjyxuhgkfdqrpsqhqm"
    llm_base_url: str = "https://api.siliconflow.cn/v1/chat/completions"
    llm_model: str = "deepseek-ai/DeepSeek-V3.2"
    max_tokens: int = 4096
    temperature: float = 0.1
    default_document_path: str = "E:\github\新建文件夹\profileRe\document.docx"
    # default_document_path: str = str(Path.cwd() / "documents" / "document.docx")
    llm_provider: str = "siliconflow"
    log_level: str = "INFO"
    chunk_size: int = 1000  # 文档分片长度
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
