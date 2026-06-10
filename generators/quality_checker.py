"""Basic quality checks for generated DOCX files."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from docx import Document


class GeneratedDocxQualityChecker:
    """Run deterministic checks before later LLM review is wired in."""

    placeholder_pattern = re.compile(r"(?:N{3,}|X{2,}|X\s*项目|X项目|＿+|_{2,}|待填写|待替换)")
    guidance_pattern = re.compile(r"(?:【\s*)?(?:说明|举例|示例|填写说明|编写说明|填写要求)(?:\s*】)?\s*[:：]?")

    def check(self, file_path: str, *, template=None, inputs: dict[str, Any] | None = None, title: str = "") -> dict[str, Any]:
        inputs = inputs or {}
        path = Path(file_path)
        checks = []
        if not path.exists():
            return {
                "passed": False,
                "total_issues": 1,
                "checks": [{
                    "code": "file_missing",
                    "label": "生成文件存在性",
                    "passed": False,
                    "message": "生成文件不存在",
                }],
            }

        doc = Document(str(path))
        body_text = "\n".join(p.text.strip() for p in doc.paragraphs if p.text.strip())
        table_text = "\n".join(
            cell.text.strip()
            for table in doc.tables
            for row in table.rows
            for cell in row.cells
            if cell.text.strip()
        )
        all_text = "\n".join(part for part in (body_text, table_text) if part)

        checks.append(self._text_check(
            "placeholder_residue",
            "占位符残留",
            not self.placeholder_pattern.search(all_text),
            "未发现明显占位符残留",
            "生成文档中仍存在明显占位符，请补充素材或检查模板解析结果",
        ))
        checks.append(self._text_check(
            "guidance_residue",
            "说明/示例残留",
            not self.guidance_pattern.search(all_text),
            "未发现明显说明或示例残留",
            "生成文档中可能仍存在说明、举例或填写要求文字",
        ))
        checks.append(self._text_check(
            "content_non_empty",
            "正文内容",
            bool(all_text.strip()),
            "生成文档包含正文内容",
            "生成文档正文为空",
        ))
        empty_tables = self._empty_table_count(doc)
        checks.append(self._text_check(
            "table_non_empty",
            "表格填写",
            empty_tables == 0,
            "未发现完全空白表格",
            f"发现 {empty_tables} 个空白表格，请确认是否需要补充",
        ))
        product_name = str(inputs.get("product_name", "") or "").strip()
        if product_name:
            checks.append(self._text_check(
                "product_name_present",
                "产品名称一致性",
                product_name in all_text,
                "文档中包含产品名称",
                "文档中未发现用户输入的产品名称",
            ))
        if title:
            checks.append(self._text_check(
                "title_present",
                "标题一致性",
                str(title).strip() in all_text or any(str(title).strip() in p.text for p in doc.paragraphs[:3]),
                "文档中包含生成标题",
                "文档中未明显发现生成标题，请确认模板标题是否需要替换",
            ))
        missing_required = self._missing_required_chapters(doc, template)
        checks.append(self._text_check(
            "required_chapters",
            "必填章节",
            not missing_required,
            "未发现必填章节缺失",
            "可能缺少必填章节：" + "、".join(missing_required[:8]),
        ))
        pending_count = all_text.count("待补充")
        checks.append(self._text_check(
            "pending_content",
            "待补充内容",
            pending_count == 0,
            "未发现待补充内容",
            f"发现 {pending_count} 处“待补充”，请确认是否允许保留",
        ))

        total_issues = sum(1 for item in checks if not item["passed"])
        return {
            "passed": total_issues == 0,
            "total_issues": total_issues,
            "checks": checks,
        }

    def _empty_table_count(self, doc) -> int:
        count = 0
        for table in doc.tables:
            values = [
                cell.text.strip()
                for row in table.rows
                for cell in row.cells
                if cell.text.strip()
            ]
            if not values:
                count += 1
        return count

    def _missing_required_chapters(self, doc, template) -> list[str]:
        if not template:
            return []
        existing = "\n".join(p.text.strip() for p in doc.paragraphs if p.text.strip())
        missing = []
        for chapter in self._flatten_chapters(getattr(template, "chapters", []) or []):
            if not getattr(chapter, "required", True):
                continue
            title = str(getattr(chapter, "title", "") or "").strip()
            number = str(getattr(chapter, "number", "") or "").strip()
            candidates = [f"{number} {title}".strip(), title]
            if title and not any(candidate and candidate in existing for candidate in candidates):
                missing.append(f"{number} {title}".strip())
        return missing

    def _flatten_chapters(self, chapters) -> list[Any]:
        flat = []
        for chapter in chapters:
            flat.append(chapter)
            flat.extend(self._flatten_chapters(getattr(chapter, "sub_chapters", []) or []))
        return flat

    def _text_check(self, code: str, label: str, passed: bool, ok: str, fail: str) -> dict[str, Any]:
        return {
            "code": code,
            "label": label,
            "passed": bool(passed),
            "message": ok if passed else fail,
        }
