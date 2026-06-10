"""Prompt builder for template-constrained document generation."""
from __future__ import annotations

from typing import Any


class ChapterPromptBuilder:
    """Build per-chapter prompts from template metadata and user inputs."""

    system_prompt = (
        "你是航空技术文档编写助手。请严格依据用户素材、模板正文、章节说明和示例编写正式工程技术文档。"
        "不得编造未提供的数据、编号、结论或标准条款；缺失信息写“待补充”。"
    )

    def build(self, *, title: str, template_name: str, chapter: Any, inputs: dict[str, Any]) -> str:
        chapter_name = self._chapter_name(chapter)
        template_text = self._blocks_text(chapter, {"template_text", "template_table"})
        guidance_text = self._blocks_text(chapter, {"instruction", "instruction_table", "example", "example_table"})
        user_material = self._user_material(inputs)
        requirements = str(inputs.get("generation_requirements", "")).strip()
        return "\n".join(part for part in [
            f"文档标题：{title}",
            f"模板名称：{template_name}",
            f"当前章节：{chapter_name}",
            "",
            "【用户输入素材】",
            user_material or "待补充",
            "",
            "【用户生成要求】",
            requirements or "按模板要求生成正式、准确、简洁的工程技术文档。",
            "",
            "【模板正文/结构参考】",
            template_text or "无",
            "",
            "【模板说明和示例】",
            (getattr(chapter, "guidance_prompt", "") or guidance_text or "无"),
            "",
            "【输出要求】",
            "1. 只输出当前章节可直接写入正式文档的正文内容。",
            "2. 不要输出章节标题，不要输出“说明”“举例”“示例”等提示性标签。",
            "3. 保持正式工程技术文档语气，段落清晰，避免口语化。",
            "4. 对模板中的占位内容按用户素材替换；缺失信息写“待补充”。",
        ] if part is not None)

    def _chapter_name(self, chapter: Any) -> str:
        number = str(getattr(chapter, "number", "") or "").strip()
        title = str(getattr(chapter, "title", "") or "").strip()
        return f"{number} {title}".strip() or "未命名章节"

    def _blocks_text(self, chapter: Any, types: set[str]) -> str:
        lines = []
        for block in getattr(chapter, "template_blocks", []) or []:
            if block.get("type") not in types:
                continue
            text = str(block.get("text") or "").strip()
            if not text and block.get("rows"):
                text = "\n".join(" | ".join(str(cell) for cell in row) for row in block.get("rows") or [])
            if text:
                lines.append(f"{block.get('label') or block.get('type')}：{text}")
        return "\n".join(lines[:12])

    def _user_material(self, inputs: dict[str, Any]) -> str:
        labels = [
            ("产品名称", "product_name"),
            ("项目名称", "project_name"),
            ("试验项目/受试对象", "test_item"),
            ("背景说明", "background"),
            ("关键参数/素材", "technical_params"),
            ("引用文件", "references"),
            ("补充信息/其他素材", "additional_context"),
            ("上传补充材料解析内容", "supplement_doc_text"),
            ("上传补充材料解析内容", "reference_doc_text"),
        ]
        parts = []
        for label, key in labels:
            value = str(inputs.get(key, "") or "").strip()
            if value:
                parts.append(f"{label}：{value}")
        return "\n".join(parts)
