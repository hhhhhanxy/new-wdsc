"""
模板管理系统。

管理四种航空技术文档的标准章节模板。
"""
import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from pathlib import Path

from models.document import DocumentType

logger = logging.getLogger(__name__)

TEMPLATE_DATA_DIR = Path(__file__).parent / "data"


@dataclass
class ChapterTemplate:
    """章节模板定义。"""
    number: str                     # "1", "1.1" 等
    title: str                      # 章节标题
    description: str = ""           # 章节内容指引
    required: bool = True
    sub_chapters: List['ChapterTemplate'] = field(default_factory=list)
    guidance_prompt: str = ""       # LLM 生成该章节的提示片段


@dataclass
class DocumentTemplate:
    """文档模板定义。"""
    doc_type: DocumentType
    name: str
    description: str
    chapters: List[ChapterTemplate] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class TemplateManager:
    """文档模板管理器。"""

    def __init__(self, template_dir: str = None):
        self._template_dir = Path(template_dir) if template_dir else TEMPLATE_DATA_DIR
        self._templates: Dict[DocumentType, DocumentTemplate] = {}
        self._load_default_templates()

    def _load_default_templates(self):
        """从 data/ 目录加载 YAML/JSON 模板。"""
        for doc_type in DocumentType:
            # 尝试 JSON 格式
            json_path = self._template_dir / f"{doc_type.value}.json"
            if json_path.exists():
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    self._templates[doc_type] = self._parse_template(doc_type, data)
                    logger.info("Loaded template: %s", doc_type.value)
                except Exception as e:
                    logger.error("Failed to load template %s: %s", json_path, e)
                    continue

        # 如果没有外部模板文件，使用内置占位模板
        self._ensure_builtin_templates()

    def _ensure_builtin_templates(self):
        """确保每种文档类型都有模板（即使是占位）。"""
        builtin = {
            DocumentType.REQUIREMENTS: DocumentTemplate(
                doc_type=DocumentType.REQUIREMENTS,
                name="需求文档模板",
                description="航空产品需求文档标准模板",
                chapters=[
                    ChapterTemplate(number="1", title="范围", description="文档范围和适用性", required=True),
                    ChapterTemplate(number="2", title="引用文件", description="引用的标准和规范", required=True),
                    ChapterTemplate(number="3", title="需求", description="详细需求说明", required=True,
                        sub_chapters=[
                            ChapterTemplate(number="3.1", title="功能需求", required=True),
                            ChapterTemplate(number="3.2", title="性能需求", required=True),
                            ChapterTemplate(number="3.3", title="接口需求", required=False),
                            ChapterTemplate(number="3.4", title="环境适应性需求", required=False),
                        ]),
                    ChapterTemplate(number="4", title="验证", description="需求验证方法", required=True),
                    ChapterTemplate(number="5", title="质量保证", description="质量保证要求", required=False),
                ],
            ),
            DocumentType.GENERAL_CHARACTERISTICS: DocumentTemplate(
                doc_type=DocumentType.GENERAL_CHARACTERISTICS,
                name="通用特性文档模板",
                description="航空产品通用特性文档标准模板",
                chapters=[
                    ChapterTemplate(number="1", title="范围", required=True),
                    ChapterTemplate(number="2", title="引用文件", required=True),
                    ChapterTemplate(number="3", title="产品概述", required=True),
                    ChapterTemplate(number="4", title="物理特性", required=True,
                        sub_chapters=[
                            ChapterTemplate(number="4.1", title="尺寸与重量", required=True),
                            ChapterTemplate(number="4.2", title="外观与颜色", required=False),
                        ]),
                    ChapterTemplate(number="5", title="功能特性", required=True),
                    ChapterTemplate(number="6", title="性能参数", required=True),
                    ChapterTemplate(number="7", title="环境适应性", required=True),
                    ChapterTemplate(number="8", title="可靠性", required=False),
                ],
            ),
            DocumentType.TECHNICAL_SPECIFICATION: DocumentTemplate(
                doc_type=DocumentType.TECHNICAL_SPECIFICATION,
                name="技术说明书模板",
                description="航空产品技术说明书标准模板",
                chapters=[
                    ChapterTemplate(number="1", title="范围", required=True),
                    ChapterTemplate(number="2", title="引用文件", required=True),
                    ChapterTemplate(number="3", title="系统概述", required=True),
                    ChapterTemplate(number="4", title="系统设计", required=True,
                        sub_chapters=[
                            ChapterTemplate(number="4.1", title="总体设计", required=True),
                            ChapterTemplate(number="4.2", title="详细设计", required=True),
                            ChapterTemplate(number="4.3", title="接口定义", required=True),
                        ]),
                    ChapterTemplate(number="5", title="安全性分析", required=True),
                    ChapterTemplate(number="6", title="验证与确认", required=True),
                    ChapterTemplate(number="7", title="使用与维护", required=False),
                    ChapterTemplate(number="8", title="附录", required=False),
                ],
            ),
            DocumentType.VERIFICATION: DocumentTemplate(
                doc_type=DocumentType.VERIFICATION,
                name="验证文档模板",
                description="航空产品验证文档标准模板",
                chapters=[
                    ChapterTemplate(number="1", title="范围", required=True),
                    ChapterTemplate(number="2", title="引用文件", required=True),
                    ChapterTemplate(number="3", title="验证目的", required=True),
                    ChapterTemplate(number="4", title="验证方法", required=True,
                        sub_chapters=[
                            ChapterTemplate(number="4.1", title="试验验证", required=False),
                            ChapterTemplate(number="4.2", title="分析验证", required=False),
                            ChapterTemplate(number="4.3", title="检查验证", required=False),
                        ]),
                    ChapterTemplate(number="5", title="验证环境", required=True),
                    ChapterTemplate(number="6", title="验证结果", required=True),
                    ChapterTemplate(number="7", title="结论与建议", required=True),
                ],
            ),
        }

        for doc_type, template in builtin.items():
            if doc_type not in self._templates:
                self._templates[doc_type] = template

    def _parse_template(self, doc_type: DocumentType, data: dict) -> DocumentTemplate:
        """解析模板 JSON 数据。"""
        chapters = []
        for ch in data.get("chapters", []):
            chapters.append(self._parse_chapter(ch))
        return DocumentTemplate(
            doc_type=doc_type,
            name=data.get("name", ""),
            description=data.get("description", ""),
            chapters=chapters,
        )

    def _parse_chapter(self, data: dict) -> ChapterTemplate:
        """解析章节模板。"""
        sub = [self._parse_chapter(s) for s in data.get("sub_chapters", [])]
        return ChapterTemplate(
            number=data.get("number", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            required=data.get("required", True),
            sub_chapters=sub,
            guidance_prompt=data.get("guidance_prompt", ""),
        )

    def get_template(self, doc_type: DocumentType) -> DocumentTemplate:
        """获取指定文档类型的模板。"""
        return self._templates.get(doc_type)

    def list_templates(self) -> List[DocumentTemplate]:
        """列出所有可用模板。"""
        return list(self._templates.values())

    def register_template(self, template: DocumentTemplate):
        """注册自定义模板。"""
        self._templates[template.doc_type] = template
