from models.document import ContentType, DocumentRegionType, DocumentSection
from parsers.structure_parser import DocumentStructureParser


def test_structure_parser_detects_regions_and_body_tree():
    sections = [
        DocumentSection("s1", ContentType.TABLE, "阶段标识 | A\n版次 | V1.0"),
        DocumentSection("s2", ContentType.PARAGRAPH, "签署页\n编制：张三\n批准：李四"),
        DocumentSection("s3", ContentType.HEADING, "前言", level=1),
        DocumentSection("s4", ContentType.PARAGRAPH, "根据《XXX技术协议》开展。"),
        DocumentSection("s5", ContentType.HEADING, "4 接口要求", level=1),
        DocumentSection("s6", ContentType.HEADING, "4.1 机械接口", level=2),
        DocumentSection("s7", ContentType.PARAGRAPH, "安装方式采用四点固定安装结构。"),
        DocumentSection("s8", ContentType.HEADING, "4.2 电气接口", level=2),
        DocumentSection("s9", ContentType.PARAGRAPH, "电源接口应满足28 VDC输入要求。"),
    ]

    structure = DocumentStructureParser().parse(sections)

    regions = {region.region_type: region.section_ids for region in structure.regions}
    assert DocumentRegionType.COVER in regions
    assert DocumentRegionType.SIGNATURE in regions
    assert DocumentRegionType.PREFACE in regions
    assert DocumentRegionType.BODY in regions
    assert regions[DocumentRegionType.BODY] == ["s5", "s6", "s7", "s8", "s9"]

    interface = structure.body_tree[0]
    assert interface.number == "4"
    assert interface.title == "接口要求"
    assert len(interface.children) == 2
    assert interface.children[0].number == "4.1"
    assert interface.children[0].title == "机械接口"
    assert interface.children[1].number == "4.2"
    assert interface.children[1].title == "电气接口"
