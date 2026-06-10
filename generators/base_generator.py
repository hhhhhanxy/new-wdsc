"""
Base generator abstraction for document generation.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path
import logging

from docx.document import Document as DocumentType
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

from templates.docx_block_classifier import DocxBlockClassifier
from .prompt_builder import ChapterPromptBuilder

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
        progress_callback: Optional[Callable[[int, int, Any], None]] = None,
    ) -> str:
        """
        生成文档。

        Args:
            title: 文档标题
            params: 生成参数（description, technical_params, doc_type 等）
            llm_client: 可选的 LLM 客户端
            output_path: 输出文件路径
            progress_callback: 可选进度回调，参数为当前章节序号、总章节数、章节对象

        Returns:
            生成的文件路径
        """
        ...


class TemplateDocxGenerator(BaseGenerator):
    """基于原始 DOCX 模板的受控填充生成器。"""

    name = "template_docx"
    display_name = "DOCX 模板填充生成器"
    description = "保留原始 DOCX 模板正文与格式，删除说明文字并替换占位内容"
    supported_doc_types = [
        "requirements",
        "general_characteristics",
        "technical_specification",
        "verification",
    ]

    def __init__(self):
        self.classifier = DocxBlockClassifier()
        self.prompt_builder = ChapterPromptBuilder()

    def generate(
        self,
        title: str,
        params: Dict[str, Any],
        llm_client=None,
        output_path: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int, Any], None]] = None,
    ) -> str:
        if output_path is None:
            raise ValueError("output_path is required")

        from templates.template_manager import TemplateManager

        template_id = params.get("template_id") or params.get("doc_type")
        template = TemplateManager().get_template(template_id)
        if not template:
            raise ValueError(f"模板不存在: {template_id}")
        self.last_template = template

        inputs = params.get("inputs") or {}
        template_path = self._resolve_template_docx_path(template)
        if template_path and template_path.exists():
            return self._fill_template_document(
                template=template,
                title=title,
                inputs=inputs,
                params=params,
                llm_client=llm_client,
                output_path=output_path,
                progress_callback=progress_callback,
            )

        raise ValueError("该模板缺少原始 DOCX 文件，不能用于保留格式的文档生成；请在生成模板库中上传 DOCX 模板。")

    def _flatten_chapters(self, chapters) -> List[Any]:
        flat = []
        for chapter in chapters:
            flat.append(chapter)
            flat.extend(self._flatten_chapters(chapter.sub_chapters))
        return flat

    def _resolve_template_docx_path(self, template) -> Optional[Path]:
        source_path = (template.metadata or {}).get("source_docx_path") or (template.metadata or {}).get("source_path")
        if not source_path:
            return None
        path = Path(source_path)
        if not path.is_absolute():
            path = Path(__file__).resolve().parent.parent / path
        return path

    def _fill_template_document(
        self,
        template,
        title: str,
        inputs: Dict[str, Any],
        params: Dict[str, Any],
        llm_client,
        output_path: str,
        progress_callback: Optional[Callable[[int, int, Any], None]] = None,
    ) -> str:
        from docx import Document

        template_path = self._resolve_template_docx_path(template)
        if not template_path:
            raise ValueError("模板缺少原始 DOCX 文件路径")

        doc = Document(str(template_path))
        replacements = self._build_replacements(title, inputs)
        chapters = self._flatten_chapters(template.chapters)
        section_details: Dict[str, dict] = {}
        generated_sections = self._generate_sections(
            template=template,
            title=title,
            inputs=inputs,
            chapters=chapters,
            llm_client=llm_client,
            enabled=str(inputs.get("generation_mode") or "smart") == "smart",
            section_details=section_details,
        )
        params["_generation_meta"] = {
            "mode": str(inputs.get("generation_mode") or "smart"),
            "llm_enabled": bool(llm_client),
            "generated_sections": len(generated_sections),
            "sections": list(section_details.values()),
        }
        for index, chapter in enumerate(chapters, start=1):
            if progress_callback:
                progress_callback(index, len(chapters), chapter)

        delete_context = ""
        current_chapter_key = ""
        applied_generated_sections: set[str] = set()
        chapter_needs_target = {
            self._chapter_key(chapter): self._chapter_needs_specific_target(chapter)
            for chapter in chapters
        }
        chapter_strategies = {
            self._chapter_key(chapter): self._chapter_strategy(chapter)
            for chapter in chapters
        }
        for block in list(self._iter_block_items(doc)):
            if isinstance(block, Paragraph):
                text = block.text.strip()
                if self.classifier.heading_level(block) and not (
                    delete_context and self.classifier.is_context_continuation(text)
                ):
                    current_chapter_key = self._match_chapter_key(text, chapters)
                    delete_context = ""
                    self._replace_paragraph_runs(block, replacements)
                    continue
                block_type = self.classifier.classify_paragraph(block, delete_context)
                if block_type in {"instruction", "example"}:
                    delete_context = self.classifier.next_context(block_type, text, delete_context)
                    self._remove_paragraph(block)
                    continue
                if chapter_strategies.get(current_chapter_key) == "fixed_keep":
                    delete_context = ""
                    continue
                should_apply_generated = (
                    current_chapter_key
                    and current_chapter_key in generated_sections
                    and current_chapter_key not in applied_generated_sections
                    and (
                        not chapter_needs_target.get(current_chapter_key)
                        or self._is_replacement_target(block)
                    )
                )
                if should_apply_generated:
                    self._replace_paragraph_text(block, generated_sections[current_chapter_key])
                    applied_generated_sections.add(current_chapter_key)
                    if current_chapter_key in section_details:
                        section_details[current_chapter_key]["applied"] = True
                        section_details[current_chapter_key]["apply_target"] = (
                            "占位符/斜体/待补充段落"
                            if chapter_needs_target.get(current_chapter_key)
                            else "章节首个正文段落"
                        )
                    delete_context = ""
                    continue
                self._replace_paragraph_runs(block, replacements)
                delete_context = ""
            elif isinstance(block, Table):
                if delete_context == "example" or self._is_red_table(block):
                    self._remove_table(block)
                    delete_context = ""
                    continue
                if chapter_strategies.get(current_chapter_key) == "fixed_keep":
                    delete_context = ""
                    continue
                self._fill_known_table(block, inputs, replacements)
                self._replace_table_runs(block, replacements)
                delete_context = ""

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        doc.save(output_path)
        return output_path

    def _generate_sections(
        self,
        *,
        template,
        title: str,
        inputs: Dict[str, Any],
        chapters: List[Any],
        llm_client,
        enabled: bool,
        section_details: Dict[str, dict],
    ) -> Dict[str, str]:
        generated = {}
        for chapter in chapters:
            key = self._chapter_key(chapter)
            strategy = self._chapter_strategy(chapter)
            detail = {
                "chapter_key": key,
                "chapter": self._chapter_label(chapter),
                "strategy": strategy,
                "llm_called": False,
                "success": False,
                "prompt_summary": "",
                "prompt": "",
                "response": "",
                "error": "",
                "applied": False,
                "apply_target": "",
            }
            section_details[key] = detail
            if not enabled or not llm_client or not self._chapter_should_generate(chapter):
                continue
            try:
                prompt = self.prompt_builder.build(
                    title=title,
                    template_name=getattr(template, "name", ""),
                    chapter=chapter,
                    inputs=inputs,
                )
                detail["llm_called"] = True
                detail["prompt_summary"] = self._prompt_summary(prompt)
                detail["prompt"] = prompt
                response = llm_client.generate(prompt, system_prompt=self.prompt_builder.system_prompt)
                raw_content = getattr(response, "content", "") or ""
                detail["response"] = raw_content
                content = self._clean_generated_content(raw_content)
                if content:
                    generated[key] = content
                    detail["success"] = True
            except Exception as exc:
                detail["error"] = str(exc)
                logger.warning("章节智能生成失败，回退模板填充 - chapter=%s error=%s", key, exc)
        return generated

    def _chapter_should_generate(self, chapter) -> bool:
        if self._chapter_strategy(chapter) != "smart_generate":
            return False
        if getattr(chapter, "guidance_prompt", ""):
            return True
        blocks = getattr(chapter, "template_blocks", []) or []
        if any(block.get("type") in {"instruction", "example", "instruction_table", "example_table"} for block in blocks):
            return True
        return bool(getattr(chapter, "placeholders", []) or blocks)

    def _chapter_strategy(self, chapter) -> str:
        value = str(getattr(chapter, "generation_strategy", "") or "smart_generate")
        if value not in {"fixed_keep", "placeholder_replace", "smart_generate", "table_fill"}:
            return "smart_generate"
        return value

    def _chapter_label(self, chapter) -> str:
        return f"{getattr(chapter, 'number', '')} {getattr(chapter, 'title', '')}".strip()

    def _prompt_summary(self, prompt: str) -> str:
        lines = [line.strip() for line in str(prompt or "").splitlines() if line.strip()]
        return " / ".join(lines[:6])[:500]

    def _chapter_needs_specific_target(self, chapter) -> bool:
        return bool(getattr(chapter, "placeholders", []) or self._chapter_strategy(chapter) == "placeholder_replace")

    def _is_replacement_target(self, paragraph) -> bool:
        text = paragraph.text.strip()
        if not text:
            return True
        if any(run.italic and run.text.strip() for run in paragraph.runs):
            return True
        if any(token in text for token in ("NNN", "XXX", "X项目", "X 项目", "待补充", "待填写", "待替换", "____", "＿")):
            return True
        return False

    def _clean_generated_content(self, content: str) -> str:
        lines = [line.strip() for line in str(content or "").splitlines()]
        cleaned = [line for line in lines if line and not self.classifier.is_example_marker(line)]
        return "\n".join(cleaned).strip()

    def _build_replacements(self, title: str, inputs: Dict[str, Any]) -> Dict[str, str]:
        product_name = str(inputs.get("product_name", "")).strip()
        project_name = str(inputs.get("project_name", "")).strip() or str(inputs.get("background", "")).strip() or title
        test_item = str(inputs.get("test_item", "")).strip() or product_name
        replacements = {
            "NNNNN": product_name,
            "NNNN": product_name,
            "NNN": product_name,
            "XXX": project_name,
            "XX": project_name,
            "X 项目": project_name,
            "X项目": project_name,
            "受试设备": test_item,
        }
        return {key: value for key, value in replacements.items() if value}

    def _replace_paragraph_runs(self, paragraph, replacements: Dict[str, str]):
        for run in paragraph.runs:
            original = run.text
            replaced = self._replace_text(original, replacements)
            if run.italic and replaced == original:
                stripped = original.strip()
                if stripped:
                    replacement = self._replacement_for_italic_text(stripped, replacements)
                    if replacement:
                        replaced = original.replace(stripped, replacement)
                        run.italic = False
            if replaced != original:
                run.text = replaced

    def _replace_paragraph_text(self, paragraph, text: str):
        if paragraph.runs:
            paragraph.runs[0].text = text
            for run in paragraph.runs[1:]:
                run.text = ""
            return
        paragraph.add_run(text)

    def _replace_text(self, text: str, replacements: Dict[str, str]) -> str:
        result = text
        for placeholder, replacement in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
            result = result.replace(placeholder, replacement)
        return result

    def _replacement_for_italic_text(self, text: str, replacements: Dict[str, str]) -> str:
        if "项目" in text:
            return replacements.get("XXX") or replacements.get("XX") or ""
        return replacements.get("NNNNN") or replacements.get("受试设备") or ""

    def _is_red_paragraph(self, paragraph) -> bool:
        return self.classifier.is_red_paragraph(paragraph)

    def _is_red_run(self, run) -> bool:
        return self.classifier.is_red_run(run)

    def _is_example_paragraph(self, paragraph) -> bool:
        return self.classifier.is_example_marker(paragraph.text)

    def _is_red_table(self, table) -> bool:
        paragraphs = [
            paragraph
            for row in table.rows
            for cell in row.cells
            for paragraph in cell.paragraphs
            if paragraph.text.strip()
        ]
        if not paragraphs:
            return False
        red_count = sum(1 for paragraph in paragraphs if self._is_red_paragraph(paragraph))
        return red_count / len(paragraphs) >= 0.5

    def _replace_table_runs(self, table, replacements: Dict[str, str]):
        for row in table.rows:
            for cell in row.cells:
                for paragraph in list(cell.paragraphs):
                    if self._is_red_paragraph(paragraph):
                        self._remove_paragraph(paragraph)
                    elif self.classifier.classify_paragraph(paragraph) in {"instruction", "example"}:
                        self._remove_paragraph(paragraph)
                    else:
                        self._replace_paragraph_runs(paragraph, replacements)

    def _fill_known_table(self, table, inputs: Dict[str, Any], replacements: Dict[str, str]):
        headers = [cell.text.strip() for cell in table.rows[0].cells] if table.rows else []
        if "文件编号" in headers and "文件名" in headers:
            rows = self._reference_rows(inputs, replacements)
            if rows:
                self._fill_table_rows(table, rows)

    def _reference_rows(self, inputs: Dict[str, Any], replacements: Dict[str, str]) -> List[List[str]]:
        raw = str(inputs.get("references", "")).strip()
        if not raw:
            return []
        rows = []
        for line in raw.splitlines():
            text = line.strip().strip(";；")
            if not text:
                continue
            text = self._replace_text(text, replacements)
            parts = [part.strip() for part in text.split("|")]
            if len(parts) >= 2:
                rows.append((parts + [""])[:3])
                continue
            rows.append(self._parse_reference_line(text))
        return rows

    def _parse_reference_line(self, text: str) -> List[str]:
        import re

        text = re.sub(r"^\s*(?:\[\d+\]|\d+[\.、])\s*", "", text).strip()
        date_match = re.search(r"(\d{4}(?:[-./]\d{1,2})?(?:[-./]\d{1,2})?)$", text)
        date = date_match.group(1) if date_match else ""
        if date:
            text = text[:date_match.start()].strip()
        parts = text.split(maxsplit=1)
        if len(parts) == 2 and re.search(r"\d", parts[0]):
            return [parts[0], parts[1], date]
        return ["", text, date]

    def _fill_table_rows(self, table, data_rows: List[List[str]]):
        while len(table.rows) < len(data_rows) + 1:
            table.add_row()
        for index, values in enumerate(data_rows, start=1):
            for col_index, value in enumerate(values):
                if col_index >= len(table.rows[index].cells):
                    break
                table.rows[index].cells[col_index].text = value
        for row_index in range(len(data_rows) + 1, len(table.rows)):
            for cell in table.rows[row_index].cells:
                cell.text = ""

    def _remove_paragraph(self, paragraph):
        element = paragraph._element
        parent = element.getparent()
        parent.remove(element)
        paragraph._p = paragraph._element = None

    def _remove_table(self, table):
        element = table._element
        parent = element.getparent()
        parent.remove(element)

    def _chapter_key(self, chapter) -> str:
        return f"{getattr(chapter, 'number', '')}::{getattr(chapter, 'title', '')}".strip(":")

    def _match_chapter_key(self, heading_text: str, chapters: List[Any]) -> str:
        normalized = self._normalize_heading(heading_text)
        for chapter in chapters:
            candidates = [
                f"{getattr(chapter, 'number', '')} {getattr(chapter, 'title', '')}".strip(),
                str(getattr(chapter, "title", "") or ""),
            ]
            if any(self._normalize_heading(candidate) == normalized for candidate in candidates if candidate):
                return self._chapter_key(chapter)
        return ""

    def _normalize_heading(self, text: str) -> str:
        import re

        return re.sub(r"\s+", "", str(text or "")).strip("：:。.、")

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
GeneratorFactory.register("template_docx", TemplateDocxGenerator)
