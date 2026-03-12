from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class ContentType(Enum):
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    TABLE = "table"
    LIST = "list"
    IMAGE = "image"


@dataclass
class DocumentSection:
    section_id: str
    content_type: ContentType
    text: str
    level: int = 0
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class ParsedDocument:
    file_path: str
    title: str
    sections: List[DocumentSection]
    raw_text: str
    metadata: dict = field(default_factory=dict)
    
    def get_section_by_id(self, section_id: str) -> Optional[DocumentSection]:
        for section in self.sections:
            if section.section_id == section_id:
                return section
        return None
    
    def get_sections_by_type(self, content_type: ContentType) -> List[DocumentSection]:
        return [s for s in self.sections if s.content_type == content_type]
