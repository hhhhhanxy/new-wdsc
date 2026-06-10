"""Heuristics for classifying DOCX template blocks."""
from __future__ import annotations

import re


class DocxBlockClassifier:
    """Classify template text, guidance text, examples, and headings.

    The classifier intentionally uses multiple signals. Some templates mark
    guidance in red, others use bracketed labels such as "【说明】" or plain
    labels such as "注：" / "举例：".
    """

    heading_number_pattern = re.compile(r"^\s*(\d+(?:\.\d+)*)\s*[\.\、．]?\s*(.+?)\s*$")
    heading_style_pattern = re.compile(r"(?:Heading|标题)\s*(\d+)", re.IGNORECASE)
    numbered_line_pattern = re.compile(r"^\s*(?:\d+[\.\、]|[（(]?\d+[）)]|[a-zA-Z][\).、])\s*")

    example_marker_pattern = re.compile(
        r"^\s*(?:【\s*)?(?:举例|示例|例|参考示例|样例)(?:\s*】)?\s*[:：]?\s*$"
        r"|^\s*(?:举例|示例|例|参考示例|样例)\s*[:：]"
    )
    instruction_marker_pattern = re.compile(
        r"^\s*(?:【\s*)?(?:说明|注|注意|填写说明|编写说明|编制说明|生成说明|要求|填写要求|编写要求|表格填写要求)"
        r"(?:\s*】)?\s*[:：]?"
    )
    instruction_text_pattern = re.compile(
        r"(正式(?:文件|文档)中(?:应)?删除|生成(?:正式)?(?:文件|文档)时(?:应)?删除|"
        r"红色字体|斜体字|占位符|按需修改|根据.*(?:修改|填写|补充|确定)|"
        r"(?:本章|本节|此处|该处|表中|文中).*(?:应|需要|用于|填写|说明|替换|删除))"
    )

    def heading_level(self, paragraph) -> int:
        style_name = paragraph.style.name if paragraph.style else ""
        match = self.heading_style_pattern.search(style_name or "")
        if match:
            try:
                return max(1, int(match.group(1)))
            except ValueError:
                return 0
        text = paragraph.text.strip()
        number_match = self.heading_number_pattern.match(text)
        if number_match and len(text) <= 100:
            return number_match.group(1).count(".") + 1
        return 0

    def heading_parts(self, text: str) -> tuple[str, str]:
        match = self.heading_number_pattern.match(text)
        if not match:
            return "", text.strip()
        return match.group(1), match.group(2).strip()

    def classify_paragraph(self, paragraph, current_context: str = "") -> str:
        text = paragraph.text.strip()
        if self.is_example_marker(text):
            return "example"
        if self.is_instruction_marker(text):
            return "instruction"
        if current_context in {"example", "instruction"} and self.is_context_continuation(text):
            return current_context
        if self.is_red_paragraph(paragraph):
            return "example" if current_context == "example" else "instruction"
        return "template_text"

    def next_context(self, block_type: str, text: str, current_context: str = "") -> str:
        if block_type == "example" or self.is_example_marker(text):
            return "example"
        if block_type == "instruction" or self.is_instruction_marker(text):
            return "instruction"
        return "" if block_type == "template_text" else current_context

    def is_context_continuation(self, text: str) -> bool:
        if not text:
            return False
        if self.is_example_marker(text) or self.is_instruction_marker(text):
            return True
        if self.numbered_line_pattern.match(text):
            return True
        return self.looks_like_instruction_text(text)

    def is_example_marker(self, text: str) -> bool:
        return bool(self.example_marker_pattern.search(text.strip()))

    def is_instruction_marker(self, text: str) -> bool:
        return bool(self.instruction_marker_pattern.search(text.strip()))

    def looks_like_instruction_text(self, text: str) -> bool:
        return bool(self.instruction_text_pattern.search(text.strip()))

    def is_red_paragraph(self, paragraph) -> bool:
        visible_runs = [run for run in paragraph.runs if run.text.strip()]
        if not visible_runs:
            return False
        red_runs = [run for run in visible_runs if self.is_red_run(run)]
        return bool(red_runs) and len(red_runs) / len(visible_runs) >= 0.5

    def is_red_run(self, run) -> bool:
        rgb = getattr(run.font.color, "rgb", None)
        if rgb is None:
            return False
        channels = tuple(rgb)
        return channels[0] >= 180 and channels[1] <= 100 and channels[2] <= 100
