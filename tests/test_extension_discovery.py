"""Tests for the extension discovery and registry system."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def test_text_position_dataclass():
    from rules.base_rule import TextPosition
    pos = TextPosition(start_char=10, end_char=20, context_snippet="some text")
    assert pos.start_char == 10
    assert pos.end_char == 20
    assert pos.line_number is None


def test_fix_suggestion_dataclass():
    from rules.base_rule import FixSuggestion
    fix = FixSuggestion(description="fix it", replacement_text="fixed", auto_fixable=True)
    assert fix.description == "fix it"
    assert fix.replacement_text == "fixed"
    assert fix.auto_fixable is True
    assert fix.confidence == 0.0


def test_rule_result_backward_compatible():
    from rules.base_rule import RuleResult, RuleSeverity
    r = RuleResult(
        rule_id="test",
        rule_name="test",
        passed=True,
        severity=RuleSeverity.INFO,
        message="ok"
    )
    assert r.position is None
    assert r.fix_suggestion is None


def test_rule_result_with_new_fields():
    from rules.base_rule import RuleResult, RuleSeverity, TextPosition, FixSuggestion
    pos = TextPosition(start_char=5, context_snippet="error here")
    fix = FixSuggestion(description="replace", replacement_text="correct")
    r = RuleResult(
        rule_id="test",
        rule_name="test",
        passed=False,
        severity=RuleSeverity.ERROR,
        message="bad",
        position=pos,
        fix_suggestion=fix
    )
    assert r.position.start_char == 5
    assert r.fix_suggestion.replacement_text == "correct"


def test_extension_registry_singleton():
    from extensions.registry import get_registry
    r1 = get_registry()
    r2 = get_registry()
    assert r1 is r2


def test_extension_registry_manual_rule():
    from extensions.registry import get_registry
    from rules.base_rule import Rule, RuleSeverity, RuleCategory
    reg = get_registry()
    rule = Rule(
        rule_id="test_rule_manual",
        name="Test Manual Rule",
        description="test",
        category=RuleCategory.CUSTOM,
        severity=RuleSeverity.INFO,
    )
    reg.register_rule(rule)
    rules = reg.get_extension_rules()
    assert any(r.rule_id == "test_rule_manual" for r in rules)


def test_discover_aviation_extension():
    from extensions.discovery import discover_extensions
    modules = discover_extensions()
    names = [m.__name__ for m in modules]
    assert "extensions.aviation_rules" in names


def test_collect_rules_from_extension():
    from extensions.discovery import collect_from_extensions
    rules = collect_from_extensions("register_rules")
    rule_ids = [r.rule_id for r in rules]
    assert "spec_reference_format" in rule_ids


def test_base_generator_interface():
    from generators.base_generator import BaseGenerator
    assert hasattr(BaseGenerator, "generate")


def test_simple_docx_generator():
    from generators.base_generator import SimpleDocxGenerator
    gen = SimpleDocxGenerator()
    assert gen.name == "simple_docx"


def test_generator_factory():
    from generators.base_generator import GeneratorFactory
    assert "simple_docx" in GeneratorFactory.available_generators()
    gen = GeneratorFactory.create("simple_docx")
    assert gen.name == "simple_docx"


if __name__ == "__main__":
    test_text_position_dataclass()
    test_fix_suggestion_dataclass()
    test_rule_result_backward_compatible()
    test_rule_result_with_new_fields()
    test_extension_registry_singleton()
    test_extension_registry_manual_rule()
    test_discover_aviation_extension()
    test_collect_rules_from_extension()
    test_base_generator_interface()
    test_simple_docx_generator()
    test_generator_factory()
    test_document_type_enum()
    test_review_phase_enum()
    test_security_detector_clean()
    test_security_detector_classified()
    test_template_manager()
    test_doc_type_detector()
    test_template_generator()
    print("All tests passed!")


# ---- New tests for aviation platform features ----

def test_document_type_enum():
    from models.document import DocumentType
    assert len(DocumentType) == 4
    assert DocumentType.REQUIREMENTS.value == "requirements"
    assert DocumentType.TECHNICAL_SPECIFICATION.value == "technical_specification"


def test_review_phase_enum():
    from rules.base_rule import ReviewPhase, PHASE_ORDER, PHASE_DISPLAY_NAMES
    assert len(PHASE_ORDER) == 5
    assert PHASE_ORDER[0] == ReviewPhase.FORMAT
    assert PHASE_ORDER[4] == ReviewPhase.TRACEABILITY
    assert PHASE_DISPLAY_NAMES[ReviewPhase.COMPLETENESS] == "完整性检查"


def test_security_detector_clean():
    from security.classification_detector import ClassificationDetector
    from models.document import ParsedDocument, DocumentSection, ContentType
    doc = ParsedDocument(file_path='t.docx', title='Clean', sections=[
        DocumentSection(section_id='s1', content_type=ContentType.PARAGRAPH, text='普通技术文档'),
    ], raw_text='普通技术文档')
    detector = ClassificationDetector()
    result = detector.check(doc)
    assert not result.is_classified


def test_security_detector_classified():
    from security.classification_detector import ClassificationDetector
    from models.document import ParsedDocument, DocumentSection, ContentType
    doc = ParsedDocument(file_path='t.docx', title='Secret', sections=[
        DocumentSection(section_id='s1', content_type=ContentType.PARAGRAPH, text='本文件为机密级别'),
    ], raw_text='本文件为机密级别')
    detector = ClassificationDetector()
    result = detector.check(doc)
    assert result.is_classified
    assert result.level == "机密"


def test_template_manager():
    from templates.template_manager import TemplateManager
    from models.document import DocumentType
    tm = TemplateManager()
    templates = tm.list_templates()
    assert len(templates) == 4
    t = tm.get_template(DocumentType.REQUIREMENTS)
    assert t is not None
    assert t.name == "需求文档模板"
    assert len(t.chapters) > 0


def test_doc_type_detector():
    from parsers.doc_type_detector import DocumentTypeDetector
    from models.document import ParsedDocument, DocumentSection, ContentType, DocumentType
    doc = ParsedDocument(file_path='t.docx', title='作动系统需求分析', sections=[
        DocumentSection(section_id='s1', content_type=ContentType.PARAGRAPH,
            text='本文档描述功能需求和性能需求'),
    ], raw_text='本文档描述功能需求和性能需求')
    detector = DocumentTypeDetector()
    doc_type = detector.detect(doc)
    assert doc_type == DocumentType.REQUIREMENTS


def test_template_generator():
    from generators.base_generator import GeneratorFactory
    assert "template_docx" in GeneratorFactory.available_generators()
    gen = GeneratorFactory.create("template_docx")
    assert gen.name == "template_docx"
