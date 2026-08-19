"""Prompt builder for template-constrained document generation."""
from __future__ import annotations

from typing import Any

from templates.docx_block_classifier import DocxBlockClassifier


class ChapterPromptBuilder:
    """Build per-chapter prompts from template metadata and user inputs."""

    classifier = DocxBlockClassifier()

    system_prompt = (
        "你是航空技术文档编写助手。请严格依据用户素材、模板正文、章节说明和示例编写正式工程技术文档。"
        "事实内容以用户输入素材和上传补充材料为最高优先级，模板用于约束结构与格式，参考案例仅用于学习写作风格。"
        "不得编造未提供的数据、编号、结论或标准条款；缺失信息写“待补充”。"
    )

    def build(
        self,
        *,
        title: str,
        template_name: str,
        chapter: Any,
        inputs: dict[str, Any],
        target_text: str = "",
        target_index: int = 0,
        target_total: int = 0,
    ) -> str:
        chapter_name = self._chapter_name(chapter)
        template_text = self._blocks_text(chapter, {"template_text", "template_list", "template_table"})
        guidance_text = self._blocks_text(chapter, {"instruction", "instruction_table", "example", "example_table"})
        user_material = self._user_material(inputs, chapter)
        requirements = str(inputs.get("generation_requirements", "")).strip()
        reference_case_context = str(inputs.get("reference_case_context", "") or "").strip()
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
            "【参考案例特征】",
            reference_case_context or "无",
            "参考案例使用边界：仅参考章节组织、术语习惯、语气风格、详略程度、条款表达颗粒度和格式特点；不得照搬案例中的产品型号、项目编号、试验数据、结论、日期、人员、单位或文件编号。",
            "",
            "【模板正文/结构参考】",
            template_text or "无",
            "",
            "【模板说明和示例】",
            (getattr(chapter, "guidance_prompt", "") or guidance_text or "无"),
            "",
            "【本章节人工补充要求】",
            str(getattr(chapter, "manual_guidance_prompt", "") or "").strip() or "无",
            "",
            "【本次回填位置】",
            (
                f"第 {target_index}/{target_total} 处：{target_text}"
                if target_text and target_total
                else target_text or "当前章节正文"
            ),
            "",
            "【输出要求】",
            "1. 只输出当前章节可直接写入正式文档的正文内容。",
            "2. 不要输出章节标题，不要输出“说明”“举例”“示例”等提示性标签。",
            "3. 保持正式工程技术文档语气，段落清晰，避免口语化。",
            "4. 对模板中的占位内容按用户素材替换；缺失信息写“待补充”。",
            "5. 不要使用 Markdown 表格；如需表格数据，仅用简洁文字说明，由模板表格承载。",
            "6. 事实内容优先级为：用户输入素材 > 上传补充材料 > 当前模板占位要求 > 参考案例写法；参考案例只影响表达方式，不改变事实内容。",
            "7. 当用户素材与参考案例不一致时，必须采用用户素材；当用户素材未提供时，不得从参考案例补造事实数据。",
            "8. 保持模板既有章节编号、标题层级、表格结构和版式意图，不自行新增不属于当前回填位置的章节。",
            "9. 模板中如包含“模板列表”，应保留原列表编号形式；用户素材条目多于模板示例时，可按同一编号规则继续扩展。",
        ] if part is not None)

    def _chapter_name(self, chapter: Any) -> str:
        number = str(getattr(chapter, "number", "") or "").strip()
        title = str(getattr(chapter, "title", "") or "").strip()
        return f"{number} {title}".strip() or "未命名章节"

    def _blocks_text(self, chapter: Any, types: set[str]) -> str:
        lines = []
        previous_effective_type = ""
        for block in getattr(chapter, "template_blocks", []) or []:
            effective_type = self._effective_block_type(block, previous_effective_type)
            previous_effective_type = effective_type
            if effective_type not in types:
                continue
            if self._is_empty_marker_block(block):
                continue
            text = str(block.get("text") or "").strip()
            if effective_type == "template_list":
                items = block.get("items") or []
                text = "\n".join(
                    f"{str(item.get('marker') or '').strip()}{str(item.get('text') or '').strip()}"
                    if str(item.get("text") or "").strip()
                    else str(item.get("marker") or "").strip()
                    for item in items
                    if str(item.get("marker") or item.get("text") or "").strip()
                ) or text
                if block.get("can_expand"):
                    text = f"{text}\n可按相同列表格式继续扩展。".strip()
            if not text and block.get("rows"):
                text = "\n".join(" | ".join(str(cell) for cell in row) for row in block.get("rows") or [])
            if text:
                label = self._effective_block_label(effective_type, block)
                lines.append(self._format_block_text(effective_type, label, text))
        return "\n".join(lines[:12])

    def _effective_block_type(self, block: dict, previous_effective_type: str = "") -> str:
        block_type = str(block.get("type") or "")
        text = str(block.get("text") or "").strip()
        if block_type == "template_text" and self.classifier.looks_like_instruction_or_example_text(text):
            return "example" if self.classifier.is_example_marker(text) else "instruction"
        if block_type == "template_list" and previous_effective_type in {"instruction", "example"}:
            return previous_effective_type
        return block_type

    def _effective_block_label(self, block_type: str, block: dict) -> str:
        if block_type == "instruction":
            return "说明"
        if block_type == "example":
            return "举例"
        return str(block.get("label") or block_type)

    def _format_block_text(self, block_type: str, label: str, text: str) -> str:
        if block_type in {"instruction", "example"}:
            return self.classifier.guidance_display_text(block_type, text)
        return f"{label}：{text}"

    def _is_empty_marker_block(self, block: dict) -> bool:
        block_type = str(block.get("type") or "")
        text = str(block.get("text") or "").strip()
        if block_type == "instruction":
            return text in {"【说明】", "说明", "说明：", "【要求】", "要求", "要求："}
        if block_type == "example":
            return text in {"【示例】", "示例", "示例：", "【举例】", "举例", "举例："}
        return False

    def _user_material(self, inputs: dict[str, Any], chapter: Any = None) -> str:
        labels = [
            ("生成需求", "generation_brief"),
            ("产品名称", "product_name"),
            ("项目名称", "project_name"),
            ("试验项目/受试对象", "test_item"),
            ("专业方向", "specialty_name"),
            ("背景说明", "background"),
            ("关键参数/素材", "technical_params"),
            ("引用文件", "references"),
            ("补充信息/其他素材", "additional_context"),
            ("结构化素材池", "parsed_material_context"),
            ("上传补充材料解析内容", "supplement_doc_text"),
            ("上传补充材料解析内容", "reference_doc_text"),
        ]
        parts = []
        for label, key in labels:
            value = str(inputs.get(key, "") or "").strip()
            if value:
                parts.append(f"{label}：{value}")
        dynamic_values = inputs.get("dynamic_fields") or {}
        definitions = inputs.get("dynamic_field_definitions") or []
        labels_by_key = {
            str(item.get("key") or ""): str(item.get("label") or item.get("key") or "")
            for item in definitions
            if isinstance(item, dict)
        }
        current_chapter = self._chapter_name(chapter) if chapter is not None else ""
        current_number = str(getattr(chapter, "number", "") or "").strip()
        current_title = str(getattr(chapter, "title", "") or "").strip()
        current_key = f"{current_number}::{current_title}".strip(":")
        definitions_by_key = {
            str(item.get("key") or ""): item
            for item in definitions
            if isinstance(item, dict)
        }
        for key, value in dynamic_values.items():
            text = str(value or "").strip()
            definition = definitions_by_key.get(str(key), {})
            chapter_keys = [str(item).strip() for item in definition.get("chapter_keys", [])]
            if chapter_keys and not any(
                item in {current_chapter, current_number, current_title, current_key}
                for item in chapter_keys
            ):
                continue
            if text:
                parts.append(f"{labels_by_key.get(str(key), str(key))}：{text}")
        return "\n".join(parts)
