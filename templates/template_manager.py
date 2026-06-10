"""
模板管理系统。

管理四种航空技术文档的标准章节模板。
"""
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Union
from pathlib import Path

from models.document import DocumentType

logger = logging.getLogger(__name__)

TEMPLATE_DATA_DIR = Path(__file__).parent / "data"
CUSTOM_TEMPLATE_STORE = Path(__file__).parent.parent / "config" / "generation_templates.json"


@dataclass
class ChapterTemplate:
    """章节模板定义。"""
    number: str                     # "1", "1.1" 等
    title: str                      # 章节标题
    description: str = ""           # 章节内容指引
    required: bool = True
    sub_chapters: List['ChapterTemplate'] = field(default_factory=list)
    guidance_prompt: str = ""       # LLM 生成该章节的提示片段
    style_name: str = ""            # 模板中识别到的标题样式名称
    body_style_name: str = ""       # 模板中识别到的正文样式名称
    template_blocks: List[dict] = field(default_factory=list)  # 章节内模板正文/说明块
    placeholders: List[str] = field(default_factory=list)      # 章节内识别到的占位符


@dataclass
class DocumentTemplate:
    """文档模板定义。"""
    name: str
    description: str
    chapters: List[ChapterTemplate] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    doc_type: Optional[DocumentType] = None
    template_id: str = ""
    source_type: str = "built_in"


class TemplateManager:
    """文档模板管理器。"""

    def __init__(self, template_dir: str = None, custom_store_path: str = None):
        self._template_dir = Path(template_dir) if template_dir else TEMPLATE_DATA_DIR
        self._custom_store_path = Path(custom_store_path) if custom_store_path else CUSTOM_TEMPLATE_STORE
        self._templates: Dict[str, DocumentTemplate] = {}
        self._hidden_builtin_template_ids: set[str] = set()
        self._load_default_templates()
        self._load_custom_templates()

    def _load_default_templates(self):
        """从 data/ 目录加载 YAML/JSON 模板。"""
        for doc_type in DocumentType:
            # 尝试 JSON 格式
            json_path = self._template_dir / f"{doc_type.value}.json"
            if json_path.exists():
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    template = self._parse_template(data, doc_type=doc_type)
                    self._templates[template.template_id] = template
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
                name="需求文档模板",
                description="航空产品需求文档标准模板",
                doc_type=DocumentType.REQUIREMENTS,
                template_id=DocumentType.REQUIREMENTS.value,
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
                name="通用特性文档模板",
                description="航空产品通用特性文档标准模板",
                doc_type=DocumentType.GENERAL_CHARACTERISTICS,
                template_id=DocumentType.GENERAL_CHARACTERISTICS.value,
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
                name="技术说明书模板",
                description="航空产品技术说明书标准模板",
                doc_type=DocumentType.TECHNICAL_SPECIFICATION,
                template_id=DocumentType.TECHNICAL_SPECIFICATION.value,
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
                name="验证文档模板",
                description="航空产品验证文档标准模板",
                doc_type=DocumentType.VERIFICATION,
                template_id=DocumentType.VERIFICATION.value,
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
            if doc_type.value not in self._templates:
                self._templates[doc_type.value] = template

    def _load_custom_templates(self):
        """从持久化文件加载用户模板。"""
        if not self._custom_store_path.exists():
            return
        try:
            with open(self._custom_store_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to load custom generation templates")
            return

        self._hidden_builtin_template_ids = set(data.get("hidden_builtin_template_ids", []))
        for template_id in self._hidden_builtin_template_ids:
            self._templates.pop(template_id, None)

        for item in data.get("templates", []):
            template = self._parse_template(item)
            template.source_type = item.get("source_type", "uploaded_docx")
            self._templates[template.template_id] = template

    def _save_custom_templates(self):
        """保存用户模板，内置模板不写入持久化文件。"""
        custom_templates = [
            self.serialize_template(template)
            for template in self._templates.values()
            if template.source_type != "built_in"
        ]
        self._custom_store_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._custom_store_path, "w", encoding="utf-8") as f:
            json.dump({
                "templates": custom_templates,
                "hidden_builtin_template_ids": sorted(self._hidden_builtin_template_ids),
            }, f, ensure_ascii=False, indent=2)

    def _parse_template(self, data: dict, doc_type: Optional[DocumentType] = None) -> DocumentTemplate:
        """解析模板 JSON 数据。"""
        chapters = []
        for ch in data.get("chapters", []):
            chapters.append(self._parse_chapter(ch))
        template_id = data.get("id") or data.get("template_id")
        if not template_id and doc_type:
            template_id = doc_type.value
        if not template_id:
            template_id = self._make_template_id(data.get("name", "template"))
        return DocumentTemplate(
            template_id=template_id,
            doc_type=doc_type,
            name=data.get("name", ""),
            description=data.get("description", ""),
            chapters=chapters,
            metadata=data.get("metadata", {}),
            source_type=data.get("source_type", "built_in" if doc_type else "uploaded_docx"),
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
            style_name=data.get("style_name", ""),
            body_style_name=data.get("body_style_name", ""),
            template_blocks=data.get("template_blocks", []),
            placeholders=data.get("placeholders", []),
        )

    def get_template(self, doc_type: Union[DocumentType, str]) -> Optional[DocumentTemplate]:
        """获取指定文档类型的模板。"""
        if isinstance(doc_type, DocumentType):
            return self._templates.get(doc_type.value)
        return self._templates.get(str(doc_type))

    def list_templates(self) -> List[DocumentTemplate]:
        """列出所有可用模板。"""
        return list(self._templates.values())

    def register_template(self, template: DocumentTemplate):
        """注册自定义模板。"""
        if not template.template_id:
            template.template_id = self._make_template_id(template.name)
        self._templates[template.template_id] = template
        if template.source_type != "built_in":
            self._save_custom_templates()

    def create_template(
        self,
        name: str,
        description: str,
        chapters: List[dict],
        metadata: Optional[dict] = None,
        source_type: str = "uploaded_docx",
        template_id: Optional[str] = None,
    ) -> DocumentTemplate:
        """创建并保存用户模板。"""
        data = {
            "id": template_id or self._make_template_id(name),
            "name": name,
            "description": description,
            "chapters": chapters,
            "metadata": metadata or {},
            "source_type": source_type,
        }
        while data["id"] in self._templates:
            data["id"] = self._make_template_id(name)
        template = self._parse_template(data)
        self.register_template(template)
        return template

    def update_template(self, template_id: str, data: dict) -> Optional[DocumentTemplate]:
        """更新用户模板。内置模板不允许覆盖。"""
        template = self.get_template(template_id)
        if not template or template.source_type == "built_in":
            return None
        template.name = data.get("name", template.name)
        template.description = data.get("description", template.description)
        if "chapters" in data:
            template.chapters = [self._parse_chapter(ch) for ch in data.get("chapters", [])]
        template.metadata.update(data.get("metadata", {}))
        self._templates[template.template_id] = template
        self._save_custom_templates()
        return template

    def delete_template(self, template_id: str) -> bool:
        """删除模板。内置示例模板会被隐藏，用户模板会从持久化文件删除。"""
        template = self.get_template(template_id)
        if not template:
            return False
        if template.source_type == "built_in":
            self._hidden_builtin_template_ids.add(template_id)
            self._templates.pop(template_id, None)
            self._save_custom_templates()
            return True
        del self._templates[template_id]
        self._save_custom_templates()
        return True

    def serialize_chapter(self, chapter: ChapterTemplate) -> dict:
        """序列化章节模板，供前端和生成器使用。"""
        return {
            "number": chapter.number,
            "title": chapter.title,
            "description": chapter.description,
            "required": chapter.required,
            "guidance_prompt": chapter.guidance_prompt,
            "style_name": chapter.style_name,
            "body_style_name": chapter.body_style_name,
            "template_blocks": chapter.template_blocks,
            "placeholders": chapter.placeholders,
            "sub_chapters": [self.serialize_chapter(ch) for ch in chapter.sub_chapters],
        }

    def serialize_template(self, template: DocumentTemplate) -> dict:
        """序列化文档模板。"""
        return {
            "id": template.template_id or (template.doc_type.value if template.doc_type else ""),
            "doc_type": template.doc_type.value if template.doc_type else "",
            "name": template.name,
            "description": template.description,
            "metadata": template.metadata,
            "source_type": template.source_type,
            "chapters": [self.serialize_chapter(ch) for ch in template.chapters],
        }

    def list_template_dicts(self) -> List[dict]:
        """列出所有模板的 JSON 安全字典。"""
        return [self.serialize_template(template) for template in self.list_templates()]

    def _make_template_id(self, name: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", str(name or "template").strip()).strip("_").lower()
        if not slug:
            slug = "template"
        return f"{slug}_{uuid.uuid4().hex[:8]}"
