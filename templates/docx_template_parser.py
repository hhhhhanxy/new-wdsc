"""DOCX template structure parser."""
import re
from pathlib import Path
from typing import Any

from docx import Document
from docx.document import Document as DocumentType
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

from .docx_block_classifier import DocxBlockClassifier


class DocxTemplateParser:
    """Parse DOCX headings into an editable generation template chapter tree."""

    heading_number_pattern = re.compile(r"^\s*(\d+(?:\.\d+)*)\s*[\.\、．]?\s*(.+?)\s*$")
    heading_style_pattern = re.compile(r"(?:Heading|标题)\s*(\d+)", re.IGNORECASE)
    placeholder_pattern = re.compile(r"(?:N{3,}|X{2,}|X\s*项目|X项目|＿+|_{2,})")

    def __init__(self):
        self.classifier = DocxBlockClassifier()

    def parse(self, file_path: str) -> dict[str, Any]:
        doc = Document(file_path)
        headings = []
        current_heading = None
        current_context = ""

        for block_item in self._iter_block_items(doc):
            if isinstance(block_item, Paragraph):
                text = block_item.text.strip()
                if not text:
                    continue
                style_name = block_item.style.name if block_item.style else ""
                level = self.classifier.heading_level(block_item)
                number = ""
                title = text

                number_match = self.heading_number_pattern.match(text)
                if number_match and level:
                    number, title = self.classifier.heading_parts(text)
                    level = number.count(".") + 1

                if (level or number) and not (
                    current_context and self.classifier.is_context_continuation(text)
                ):
                    current_heading = {
                        "number": number,
                        "title": title,
                        "level": max(1, level or 1),
                        "style_name": style_name,
                        "body_style_name": "",
                        "description": "",
                        "required": True,
                        "guidance_prompt": "",
                        "template_blocks": [],
                        "placeholders": [],
                        "sub_chapters": [],
                        "_guidance_parts": [],
                    }
                    headings.append(current_heading)
                    current_context = ""
                    continue

                if current_heading:
                    block = self._paragraph_block(block_item, current_context)
                    current_heading["template_blocks"].append(block)
                    current_heading["placeholders"].extend(block.get("placeholders", []))
                    if block["type"] in ("instruction", "example"):
                        current_heading["_guidance_parts"].append(f"{block['label']}：{text}")
                    if not current_heading.get("body_style_name") and block["type"] == "template_text":
                        current_heading["body_style_name"] = style_name
                    current_context = self._next_context(block, current_context)
            elif isinstance(block_item, Table) and current_heading:
                block = self._table_block(block_item, current_context)
                current_heading["template_blocks"].append(block)
                current_heading["placeholders"].extend(block.get("placeholders", []))
                if block["type"] in ("instruction_table", "example_table"):
                    current_heading["_guidance_parts"].append(f"{block['label']}：{self._table_text(block)}")

        if not headings:
            headings = self._fallback_headings(doc)

        return {
            "name": Path(file_path).stem,
            "description": "由 DOCX 模板自动解析生成",
            "chapters": self._build_tree(headings),
        }

    def _fallback_headings(self, doc: Document) -> list[dict]:
        result = []
        for paragraph in doc.paragraphs:
            text = paragraph.text.strip()
            if text:
                result.append({
                    "number": str(len(result) + 1),
                    "title": text[:60],
                    "level": 1,
                    "style_name": paragraph.style.name if paragraph.style else "",
                    "body_style_name": paragraph.style.name if paragraph.style else "",
                    "description": "",
                    "required": True,
                    "guidance_prompt": "",
                    "template_blocks": [],
                    "placeholders": [],
                    "sub_chapters": [],
                })
            if len(result) >= 8:
                break
        return result

    def _build_tree(self, headings: list[dict]) -> list[dict]:
        roots = []
        stack = []
        for item in headings:
            chapter = {
                "number": item.get("number", ""),
                "title": item.get("title", ""),
                "description": item.get("description", ""),
                "required": item.get("required", True),
                "guidance_prompt": item.get("guidance_prompt", "") or self._make_guidance(item),
                "style_name": item.get("style_name", ""),
                "body_style_name": item.get("body_style_name", ""),
                "template_blocks": item.get("template_blocks", []),
                "placeholders": sorted(set(item.get("placeholders", []))),
                "sub_chapters": [],
            }
            level = int(item.get("level") or 1)
            while stack and stack[-1]["level"] >= level:
                stack.pop()
            if stack:
                stack[-1]["chapter"]["sub_chapters"].append(chapter)
            else:
                roots.append(chapter)
            stack.append({"level": level, "chapter": chapter})
        return roots

    def _make_guidance(self, item: dict) -> str:
        parts = [part.strip() for part in item.get("_guidance_parts", []) if part.strip()]
        if not parts:
            return item.get("description", "")
        text = "\n".join(parts)
        return text[:2000]

    def _paragraph_block(self, paragraph, current_context: str = "") -> dict[str, Any]:
        text = paragraph.text.strip()
        italic_texts = [run.text.strip() for run in paragraph.runs if run.italic and run.text.strip()]
        placeholders = self.placeholder_pattern.findall(text)
        placeholders.extend(italic_texts)
        block_type = self._paragraph_block_type(paragraph, current_context)
        return {
            "type": block_type,
            "label": self._block_label(block_type),
            "text": text,
            "style_name": paragraph.style.name if paragraph.style else "",
            "has_italic": bool(italic_texts),
            "italic_texts": italic_texts,
            "placeholders": sorted(set(placeholders)),
        }

    def _paragraph_block_type(self, paragraph, current_context: str = "") -> str:
        return self.classifier.classify_paragraph(paragraph, current_context)

    def _table_block(self, table, current_context: str = "") -> dict[str, Any]:
        rows = []
        placeholders = []
        for row in table.rows:
            row_values = []
            for cell in row.cells:
                text = "\n".join(p.text.strip() for p in cell.paragraphs if p.text.strip())
                row_values.append(text)
                placeholders.extend(self.placeholder_pattern.findall(text))
            rows.append(row_values)
        if current_context == "example":
            block_type = "example_table"
        elif current_context == "instruction":
            block_type = "instruction_table"
        else:
            block_type = "template_table"
        return {
            "type": block_type,
            "label": self._block_label(block_type),
            "rows": rows,
            "text": self._table_text({"rows": rows}),
            "placeholders": sorted(set(placeholders)),
        }

    def _table_text(self, block: dict) -> str:
        return "\n".join(" | ".join(cell for cell in row if cell) for row in block.get("rows", []))

    def _next_context(self, block: dict, current_context: str = "") -> str:
        return self.classifier.next_context(block["type"], block.get("text", ""), current_context)

    def _block_label(self, block_type: str) -> str:
        return {
            "template_text": "模板文字",
            "template_table": "模板表格",
            "instruction": "说明",
            "instruction_table": "说明表格",
            "example": "举例",
            "example_table": "举例表格",
        }.get(block_type, "模板内容")

    def _is_example_marker(self, text: str) -> bool:
        return self.classifier.is_example_marker(text)

    def _is_red_paragraph(self, paragraph) -> bool:
        return self.classifier.is_red_paragraph(paragraph)

    def _is_red_run(self, run) -> bool:
        return self.classifier.is_red_run(run)

    def _iter_block_items(self, parent):
        if isinstance(parent, DocumentType):
            parent_elm = parent.element.body
        else:
            parent_elm = parent._tc
        for child in parent_elm.iterchildren():
            if isinstance(child, CT_P):
                yield Paragraph(child, parent)
            elif isinstance(child, CT_Tbl):
                yield Table(child, parent)
