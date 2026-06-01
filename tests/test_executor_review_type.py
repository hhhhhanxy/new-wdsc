from models.document import ContentType, DocumentSection, ParsedDocument
from rules.base_rule import Rule, RuleCategory, RuleRegistry, RuleResult, RuleSeverity, ReviewType
from core.executor import ReviewExecutor, ReviewMode


class FakeLLMResponse:
    def __init__(self, content: str):
        self.content = content


class FakeLLMClient:
    def __init__(self):
        self.prompts = []

    def generate(self, prompt: str):
        self.prompts.append(prompt)
        return FakeLLMResponse('{"passed": true, "issues": [], "summary": "ok"}')


def test_review_executor_uses_rule_review_type_to_select_engine():
    calls = {"rule": 0, "llm": 0, "both": 0}

    def make_check(name):
        def check(section, context):
            calls[name] += 1
            return RuleResult(
                rule_id=name,
                rule_name=name,
                passed=True,
                severity=RuleSeverity.WARNING,
                message="ok",
                section_id=section.section_id,
            )
        return check

    registry = RuleRegistry()
    registry.register(Rule(
        rule_id="rule_only",
        name="规则检查",
        description="只应由规则引擎执行",
        category=RuleCategory.CUSTOM,
        severity=RuleSeverity.WARNING,
        review_type=ReviewType.RULE,
        check_func=make_check("rule"),
    ))
    registry.register(Rule(
        rule_id="llm_only",
        name="LLM 检查",
        description="只应进入 LLM 审查",
        category=RuleCategory.CUSTOM,
        severity=RuleSeverity.WARNING,
        review_type=ReviewType.LLM,
        check_func=make_check("llm"),
    ))
    registry.register(Rule(
        rule_id="both",
        name="双引擎检查",
        description="规则和 LLM 都应执行",
        category=RuleCategory.CUSTOM,
        severity=RuleSeverity.WARNING,
        review_type=ReviewType.BOTH,
        check_func=make_check("both"),
    ))

    document = ParsedDocument(
        file_path="test.docx",
        title="测试文档",
        sections=[DocumentSection("s1", ContentType.PARAGRAPH, "测试内容")],
        raw_text="测试内容",
    )

    llm = FakeLLMClient()
    executor = ReviewExecutor(registry, llm_client=llm, mode=ReviewMode.BOTH)
    executor.review_document(document)

    assert calls == {"rule": 1, "llm": 0, "both": 1}
    assert "规则检查" not in llm.prompts[0]
    assert "LLM 检查" in llm.prompts[0]
    assert "双引擎检查" in llm.prompts[0]
