from core.executor import DocumentReviewResult, SectionReviewResult
from reporters.base_reporter import DocxReporter
from rules.base_rule import RuleResult, RuleSeverity


def test_docx_reporter_uses_review_report_mvp_structure():
    result = DocumentReviewResult(
        document_path="D:/demo/需求规范.docx",
        document_title="需求规范",
        review_time="2026-08-25 10:30:00",
    )
    section = SectionReviewResult(section_id="1 范围", section_text="正文内容")
    section.add_rule_result(
        RuleResult(
            rule_id="format_title",
            rule_name="标题格式检查",
            passed=False,
            severity=RuleSeverity.ERROR,
            message="标题编号不符合规则要求",
            suggestions=["请按模板要求调整标题编号"],
            rule_reference="文档管理规范",
        )
    )
    result.add_section_result(section)

    doc = DocxReporter().generate(result)
    paragraph_text = "\n".join(paragraph.text for paragraph in doc.paragraphs)

    assert "一、文档基本信息" in paragraph_text
    assert "二、审查结论【不通过】" in paragraph_text
    assert "三、不符合项/问题清单" in paragraph_text
    assert "四、本次审查详情" in paragraph_text
    assert "二、问题总览" not in paragraph_text
    assert "三、本次审查规则依据与定位详情" not in paragraph_text

    table_text = "\n".join(cell.text for table in doc.tables for row in table.rows for cell in row.cells)
    assert "文件名称" in table_text
    assert "文件类型" in table_text
    assert "问题类别" in table_text
    assert "严重程度" in table_text
    assert "审查依据" in table_text
