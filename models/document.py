from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class ContentType(Enum):
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    TABLE = "table"
    LIST = "list"
    IMAGE = "image"


class DocumentType(Enum):
    REQUIREMENTS = "requirements"                              # 需求文档
    GENERAL_CHARACTERISTICS = "general_characteristics"        # 通用特性文档
    TECHNICAL_SPECIFICATION = "technical_specification"        # 技术说明书
    VERIFICATION = "verification"                              # 验证文档


class DocumentRegionType(Enum):
    COVER = "cover"
    SIGNATURE = "signature"
    PREFACE = "preface"
    BODY = "body"


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
class DocumentStructureNode:
    node_id: str
    title: str
    number: str = ""
    level: int = 1
    region: DocumentRegionType = DocumentRegionType.BODY
    section_ids: List[str] = field(default_factory=list)
    children: List["DocumentStructureNode"] = field(default_factory=list)


@dataclass
class DocumentRegion:
    region_type: DocumentRegionType
    title: str
    section_ids: List[str] = field(default_factory=list)


@dataclass
class DocumentStructure:
    regions: List[DocumentRegion] = field(default_factory=list)
    body_tree: List[DocumentStructureNode] = field(default_factory=list)


@dataclass
class ParsedDocument:
    file_path: str
    title: str
    sections: List[DocumentSection]
    raw_text: str
    metadata: dict = field(default_factory=dict)
    doc_type: Optional[DocumentType] = None
    detected_doc_type: Optional[DocumentType] = None
    structure: Optional[DocumentStructure] = None
    
    def get_section_by_id(self, section_id: str) -> Optional[DocumentSection]:
        for section in self.sections:
            if section.section_id == section_id:
                return section
        return None
    
    def get_sections_by_type(self, content_type: ContentType) -> List[DocumentSection]:
        return [s for s in self.sections if s.content_type == content_type]
