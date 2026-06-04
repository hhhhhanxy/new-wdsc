import re
from typing import Iterable

from models.document import (
    ContentType,
    DocumentRegion,
    DocumentRegionType,
    DocumentSection,
    DocumentStructure,
    DocumentStructureNode,
)


REGION_KEYWORDS = {
    DocumentRegionType.COVER: ("封面", "产品名称", "文件编号", "阶段标识", "版次"),
    DocumentRegionType.SIGNATURE: ("签署", "签字", "签署页", "编制", "校对", "审核", "批准", "会签", "审签"),
    DocumentRegionType.PREFACE: ("前言", "概述", "简介", "总则", "引言"),
}


class DocumentStructureParser:
    """从基础 DOCX 解析结果中识别文档区域和正文标题树。"""

    heading_number_pattern = re.compile(r"^\s*(\d+(?:\.\d+)*)\s*[\.\、]?\s*(.*)$")

    def parse(self, sections: Iterable[DocumentSection]) -> DocumentStructure:
        atomic_sections = list(sections)
        structure = DocumentStructure()

        section_regions = self._assign_regions(atomic_sections)
        structure.regions = self._build_regions(atomic_sections, section_regions)
        structure.body_tree = self._build_body_tree(atomic_sections, section_regions)
        return structure

    def _assign_regions(self, sections: list[DocumentSection]) -> dict[str, DocumentRegionType]:
        regions: dict[str, DocumentRegionType] = {}
        current = DocumentRegionType.COVER
        seen_preface = False

        for index, section in enumerate(sections):
            text_head = self._head_text(section)
            if self._matches_region(text_head, DocumentRegionType.SIGNATURE):
                current = DocumentRegionType.SIGNATURE
            elif self._matches_region(text_head, DocumentRegionType.PREFACE):
                current = DocumentRegionType.PREFACE
                seen_preface = True
            elif seen_preface and self._looks_like_body_heading(section):
                current = DocumentRegionType.BODY
            elif index > 0 and current == DocumentRegionType.COVER and self._looks_like_body_heading(section):
                current = DocumentRegionType.BODY

            regions[section.section_id] = current

        return regions

    def _build_regions(
        self,
        sections: list[DocumentSection],
        section_regions: dict[str, DocumentRegionType],
    ) -> list[DocumentRegion]:
        ordered = [
            DocumentRegionType.COVER,
            DocumentRegionType.SIGNATURE,
            DocumentRegionType.PREFACE,
            DocumentRegionType.BODY,
        ]
        result = []
        for region_type in ordered:
            ids = [s.section_id for s in sections if section_regions.get(s.section_id) == region_type]
            if ids:
                result.append(DocumentRegion(region_type=region_type, title=self._region_title(region_type), section_ids=ids))
        return result

    def _build_body_tree(
        self,
        sections: list[DocumentSection],
        section_regions: dict[str, DocumentRegionType],
    ) -> list[DocumentStructureNode]:
        roots: list[DocumentStructureNode] = []
        stack: list[DocumentStructureNode] = []

        for section in sections:
            if section_regions.get(section.section_id) != DocumentRegionType.BODY:
                continue
            if section.content_type == ContentType.HEADING:
                number, title = self._split_heading(section.text)
                level = self._heading_level(section, number)
                node = DocumentStructureNode(
                    node_id=f"node_{section.section_id}",
                    title=title or section.text.strip(),
                    number=number,
                    level=level,
                    region=DocumentRegionType.BODY,
                    section_ids=[section.section_id],
                )
                while stack and stack[-1].level >= level:
                    stack.pop()
                if stack:
                    stack[-1].children.append(node)
                else:
                    roots.append(node)
                stack.append(node)
            elif stack:
                stack[-1].section_ids.append(section.section_id)

        return roots

    def _matches_region(self, text: str, region_type: DocumentRegionType) -> bool:
        return any(keyword in text for keyword in REGION_KEYWORDS.get(region_type, ()))

    def _head_text(self, section: DocumentSection) -> str:
        lines = [line.strip() for line in section.text.splitlines() if line.strip()]
        return "\n".join(lines[:3])

    def _looks_like_body_heading(self, section: DocumentSection) -> bool:
        if section.content_type == ContentType.HEADING and section.text.strip():
            return True
        return bool(self.heading_number_pattern.match(section.text.strip()))

    def _split_heading(self, text: str) -> tuple[str, str]:
        stripped = text.strip()
        match = self.heading_number_pattern.match(stripped)
        if not match:
            return "", stripped
        return match.group(1), (match.group(2) or stripped).strip()

    def _heading_level(self, section: DocumentSection, number: str) -> int:
        if number:
            return max(1, number.count(".") + 1)
        return max(1, section.level or 1)

    def _region_title(self, region_type: DocumentRegionType) -> str:
        return {
            DocumentRegionType.COVER: "封面",
            DocumentRegionType.SIGNATURE: "签署页",
            DocumentRegionType.PREFACE: "前言",
            DocumentRegionType.BODY: "正文",
        }[region_type]
