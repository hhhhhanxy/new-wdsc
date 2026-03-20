import re
from abc import ABC, abstractmethod
from typing import Optional
from docx import Document
from models.document import ParsedDocument, DocumentSection, ContentType


class BaseParser(ABC):
    @abstractmethod
    def parse(self, file_path: str) -> ParsedDocument:
        pass


class DocxParser(BaseParser):
    def __init__(self):
        self.section_counter = 0
    
    def parse(self, file_path: str) -> ParsedDocument:
        self.section_counter = 0
        doc = Document(file_path)
        sections = []
        raw_text_parts = []
        
        title = self._extract_title(doc)
        
        for element in doc.element.body:
            if element.tag.endswith('p'):
                section = self._parse_paragraph(element, doc)
                if section:
                    sections.append(section)
                    raw_text_parts.append(section.text)
            elif element.tag.endswith('tbl'):
                section = self._parse_table(element, doc)
                if section:
                    sections.append(section)
                    raw_text_parts.append(section.text)
        
        # raw_text = "\n".join(raw_text_parts)
        raw_text = "\n\n".join(raw_text_parts)
        
        return ParsedDocument(
            file_path=file_path,
            title=title,
            sections=sections,
            raw_text=raw_text,
            metadata={"total_sections": len(sections)}
        )
    
    def _extract_title(self, doc: Document) -> str:
        if doc.paragraphs and doc.paragraphs[0].style.name.startswith('Heading'):
            return doc.paragraphs[0].text
        elif doc.paragraphs:
            return doc.paragraphs[0].text[:50] if doc.paragraphs[0].text else "Untitled"
        return "Untitled"

    def _get_heading_level(self, style_name: str) -> int:
        match = re.search(r'Heading\s*(\d+)', style_name)
        return int(match.group(1)) if match else 1
    
    def _parse_paragraph(self, element, doc: Document) -> Optional[DocumentSection]:
        from docx.text.paragraph import Paragraph
        
        para = Paragraph(element, doc)
        original_text = para.text  # 保留原始文本（包含空格）
        
        # 检查是否为空段落（只包含空白字符）
        if not original_text.strip():
            return None
        
        self.section_counter += 1
        section_id = f"section_{self.section_counter}"
        
        if para.style.name.startswith('Heading'):
            level = level = self._get_heading_level(para.style.name)
            content_type = ContentType.HEADING
        else:
            level = 0
            content_type = ContentType.PARAGRAPH
        
        return DocumentSection(
            section_id=section_id,
            content_type=content_type,
            text=original_text,  # 使用原始文本
            level=level,
            metadata={"style": para.style.name}
        )
    
    def _parse_table(self, element, doc: Document) -> Optional[DocumentSection]:
        from docx.table import Table
        
        table = Table(element, doc)
        rows_text = []
        
        for row in table.rows:
            cells_text = [cell.text.strip() for cell in row.cells]
            # rows_text.append(" | ".join(cells_text))
            rows_text.append(" | ".join([f"[{j}] {cell}" for j, cell in enumerate(cells_text)]))

        text = "\n".join(rows_text)
        
        if not text.strip():
            return None
        
        self.section_counter += 1
        section_id = f"section_{self.section_counter}"
        
        return DocumentSection(
            section_id=section_id,
            content_type=ContentType.TABLE,
            text=text,
            metadata={"rows": len(table.rows), "cols": len(table.columns)}
        )


class ParserFactory:
    _parsers = {
        ".docx": DocxParser,
    }
    
    @classmethod
    def get_parser(cls, file_extension: str) -> Optional[BaseParser]:
        parser_class = cls._parsers.get(file_extension.lower())
        if parser_class:
            return parser_class()
        return None
    
    @classmethod
    def register_parser(cls, file_extension: str, parser_class: type):
        cls._parsers[file_extension.lower()] = parser_class
