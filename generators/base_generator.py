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
            f"请根据以下信息生成一份{doc_type}。\n\n"
            f"文档标题：{title}\n"
            f"产品描述：{description}\n"
            f"关键技术参数：{tech_params}\n\n"
            "请按照标准技术文档的章节结构，生成完整的文档内容。要求：\n"
            "1. 内容专业、准确，依据用户输入的信息和定义展开\n"
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


class UserDefinedDocxGenerator(BaseGenerator):
    """用户定义生成器：根据用户提供的生成定义生成 DOCX。"""

    name = "user_defined_docx"
    display_name = "用户定义 DOCX 生成器"
    description = "根据用户维护的文档生成定义、章节要求和输入信息生成 DOCX"
    supported_doc_types = ["custom"]

    def generate(
        self,
        title: str,
        params: Dict[str, Any],
        llm_client=None,
        output_path: Optional[str] = None,
    ) -> str:
        if not llm_client:
            raise ValueError("UserDefinedDocxGenerator 需要 LLM 客户端")
        if output_path is None:
            raise ValueError("output_path is required")

        definition = params.get("generation_definition", "").strip()
        if not definition:
            raise ValueError("请先填写文档生成定义")

        description = params.get("description", "")
        tech_params = params.get("technical_params", "")
        doc_type = params.get("doc_type", "用户自定义文档")

        prompt = (
            "请严格依据用户提供的生成定义生成技术文档正文。\n\n"
            f"文档类型：{doc_type}\n"
            f"文档标题：{title}\n"
            f"输入说明：{description}\n"
            f"关键参数/素材：{tech_params}\n\n"
            f"【用户生成定义】\n{definition}\n\n"
            "要求：\n"
            "1. 仅使用用户输入和生成定义中的依据，不补造未提供的密级、标准或型号信息\n"
            "2. 保持技术文档语气，章节层次清晰\n"
            "3. 如定义中给出章节结构，必须按该结构组织\n"
            "4. 直接输出正文内容"
        )

        response = llm_client.generate(prompt)

        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        doc = Document()
        heading = doc.add_heading(title, 0)
        heading.alignment = WD_ALIGN_PARAGRAPH.CENTER

        content = response.content
        for block in content.split("\n"):
            text = block.strip()
            if not text:
                continue
            if text.startswith("#"):
                doc.add_heading(text.lstrip("# "), level=min(text.count("#"), 3))
            elif len(text) > 2 and text[0].isdigit() and text[1] in ".、":
                doc.add_heading(text, level=1)
            else:
                doc.add_paragraph(text)

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
GeneratorFactory.register("user_defined_docx", UserDefinedDocxGenerator)
