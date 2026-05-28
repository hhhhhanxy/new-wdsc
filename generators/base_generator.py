"""
Base generator abstraction for document generation.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class BaseGenerator(ABC):
    """文档生成器基类，子类必须实现 generate() 方法。"""

    name: str = ""
    display_name: str = ""
    description: str = ""
    supported_doc_types: List[str] = []

    @abstractmethod
    def generate(
        self,
        title: str,
        params: Dict[str, Any],
        llm_client=None,
        output_path: Optional[str] = None,
    ) -> str:
        """
        生成文档。

        Args:
            title: 文档标题
            params: 生成参数（description, technical_params, doc_type 等）
            llm_client: 可选的 LLM 客户端
            output_path: 输出文件路径

        Returns:
            生成的文件路径
        """
        ...


class SimpleDocxGenerator(BaseGenerator):
    """默认生成器：通过 LLM 生成内容并输出为 DOCX。"""

    name = "simple_docx"
    display_name = "简单 DOCX 生成器"
    description = "通过 LLM 生成文档内容并输出为 DOCX 格式"
    supported_doc_types = ["design_report", "test_report", "maintenance", "analysis"]

    def generate(
        self,
        title: str,
        params: Dict[str, Any],
        llm_client=None,
        output_path: Optional[str] = None,
    ) -> str:
        if not llm_client:
            raise ValueError("SimpleDocxGenerator 需要 LLM 客户端")

        description = params.get("description", "")
        tech_params = params.get("technical_params", "")
        doc_type = params.get("doc_type", "技术文档")

        prompt = (
            f"请根据以下信息生成一份航空作动领域的{doc_type}。\n\n"
            f"文档标题：{title}\n"
            f"产品描述：{description}\n"
            f"关键技术参数：{tech_params}\n\n"
            "请按照标准技术文档的章节结构，生成完整的文档内容。要求：\n"
            "1. 内容专业、准确，符合航空领域规范\n"
            "2. 使用规范的工程术语\n"
            "3. 各章节内容完整，逻辑清晰\n"
            "4. 格式规范，层次分明\n\n"
            "请直接输出文档正文内容。"
        )

        response = llm_client.generate(prompt)

        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        doc = Document()
        heading = doc.add_heading(title, 0)
        heading.alignment = WD_ALIGN_PARAGRAPH.CENTER

        content = response.content
        sections = content.split("\n\n") if "\n\n" in content else content.split("\n")

        for section in sections:
            section = section.strip()
            if not section:
                continue
            if section.startswith("#"):
                doc.add_heading(section.lstrip("# "), level=min(section.count("#"), 3))
            elif len(section) > 2 and section[0].isdigit() and section[1] in ".、":
                doc.add_heading(section[2:].strip(), level=1)
            else:
                doc.add_paragraph(section)

        if output_path is None:
            raise ValueError("output_path is required")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        doc.save(output_path)
        return output_path


class GeneratorFactory:
    """文档生成器工厂。"""

    _generators: Dict[str, type] = {}

    @classmethod
    def register(cls, name: str, generator_class: type):
        cls._generators[name] = generator_class

    @classmethod
    def create(cls, name: str, **kwargs) -> BaseGenerator:
        gen_class = cls._generators.get(name)
        if gen_class is None:
            raise ValueError(f"Unknown generator: {name}")
        return gen_class(**kwargs)

    @classmethod
    def available_generators(cls) -> List[str]:
        return list(cls._generators.keys())


# 注册内置生成器
GeneratorFactory.register("simple_docx", SimpleDocxGenerator)

from generators.aviation_generators import TemplateDocxGenerator
GeneratorFactory.register("template_docx", TemplateDocxGenerator)
