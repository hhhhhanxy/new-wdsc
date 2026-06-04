from models.document import ContentType, DocumentSection, ParsedDocument
from rules.base_rule import Rule, RuleCategory, RuleRegistry, RuleResult, RuleScope, RuleSeverity, ReviewType
from core.executor import ReviewExecutor, ReviewMode


class FakeLLMResponse:
    def __init__(self, content: str):
        self.content = content


class FakeLLMClient:
    def __init__(self, response: str = '{"passed": true, "issues": [], "summary": "ok"}'):
        self.prompts = []
        self.system_prompts = []
        self.response = response

    def generate(self, prompt: str, system_prompt=None):
        self.prompts.append(prompt)
        self.system_prompts.append(system_prompt)
        return FakeLLMResponse(self.response)


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
    assert llm.system_prompts[0]


def test_review_executor_matches_llm_issue_by_rule_code():
    registry = RuleRegistry()
    registry.register(Rule(
        rule_id="任务来源检查",
        name="任务来源",
        description="审查文档是否说明任务来源",
        category=RuleCategory.CUSTOM,
        severity=RuleSeverity.ERROR,
        review_type=ReviewType.LLM,
        code="P-001",
    ))

    document = ParsedDocument(
        file_path="test.docx",
        title="测试文档",
        sections=[DocumentSection("s1", ContentType.PARAGRAPH, "本文档缺少任务来源说明")],
        raw_text="本文档缺少任务来源说明",
    )

    llm = FakeLLMClient(
        '{"passed": false, "issues": [{"rule_id": "P-001", "rule_name": "任务来源检查", '
        '"description": "未说明任务来源", "severity": "error", "suggestion": "补充任务来源"}], "summary": "发现问题"}'
    )
    executor = ReviewExecutor(registry, llm_client=llm, mode=ReviewMode.BOTH)
    result = executor.review_document(document)

    issue = result.section_results[0].rule_results[0]
    assert issue.rule_id == "任务来源检查"
    assert issue.rule_name == "任务来源"
    assert issue.severity == RuleSeverity.ERROR


def test_preface_scope_rule_only_reviews_preface_section():
    registry = RuleRegistry()
    registry.register(Rule(
        rule_id="preface_rule",
        name="任务来源",
        description="只检查前言",
        category=RuleCategory.CUSTOM,
        severity=RuleSeverity.ERROR,
        review_type=ReviewType.LLM,
        scope=RuleScope.PREFACE,
    ))

    document = ParsedDocument(
        file_path="test.docx",
        title="测试文档",
        sections=[
            DocumentSection("s1", ContentType.PARAGRAPH, "前言：根据《XXX技术协议》开展。"),
            DocumentSection("s2", ContentType.PARAGRAPH, "正文：这里不应再检查任务来源。"),
        ],
        raw_text="前言：根据《XXX技术协议》开展。\n正文：这里不应再检查任务来源。",
    )

    llm = FakeLLMClient()
    executor = ReviewExecutor(registry, llm_client=llm, mode=ReviewMode.BOTH)
    executor.review_document(document)

    assert len(llm.prompts) == 1
    assert "前言" in llm.prompts[0]
    assert "正文：这里不应再检查任务来源" not in llm.prompts[0]


def test_document_region_scopes_are_applied_independently():
    registry = RuleRegistry()
    for scope in (RuleScope.COVER, RuleScope.SIGNATURE, RuleScope.PREFACE, RuleScope.BODY):
        registry.register(Rule(
            rule_id=f"{scope.value}_rule",
            name=f"{scope.value}规则",
            description="按文档区域检查",
            category=RuleCategory.CUSTOM,
            severity=RuleSeverity.WARNING,
            review_type=ReviewType.LLM,
            scope=scope,
        ))

    document = ParsedDocument(
        file_path="test.docx",
        title="测试文档",
        sections=[
            DocumentSection("cover", ContentType.PARAGRAPH, "封面\n产品规范文件"),
            DocumentSection("signature", ContentType.PARAGRAPH, "签署页\n编制：张三 审核：李四 批准：王五"),
            DocumentSection("preface", ContentType.PARAGRAPH, "前言\n根据《XXX技术协议》开展。"),
            DocumentSection("body", ContentType.PARAGRAPH, "正文\n本章描述产品技术要求。"),
        ],
        raw_text="",
    )

    llm = FakeLLMClient()
    executor = ReviewExecutor(registry, llm_client=llm, mode=ReviewMode.BOTH)
    executor.review_document(document)

    assert len(llm.prompts) == 4
    assert "cover_rule" in llm.prompts[0]
    assert "signature_rule" in llm.prompts[1]
    assert "preface_rule" in llm.prompts[2]
    assert "body_rule" in llm.prompts[3]


def test_target_heading_rule_only_reviews_matching_section():
    registry = RuleRegistry()
    registry.register(Rule(
        rule_id="interface_rule",
        name="接口要求",
        description="只检查接口章节",
        category=RuleCategory.CUSTOM,
        severity=RuleSeverity.ERROR,
        review_type=ReviewType.LLM,
        scope=RuleScope.BODY,
        target_headings=["接口要求", "机械接口", "电气接口"],
        required_elements=["机械接口", "电气接口", "电源接口", "信号接口"],
    ))
    document = ParsedDocument(
        file_path="test.docx",
        title="测试文档",
        sections=[
            DocumentSection("s1", ContentType.PARAGRAPH, "功能要求\n这里没有接口内容", metadata={"region": "body", "heading_text": "功能要求"}),
            DocumentSection("s2", ContentType.PARAGRAPH, "接口要求\n机械接口\n电气接口\n电源接口\n信号接口", metadata={"region": "body", "heading_text": "接口要求"}),
        ],
        raw_text="",
    )

    llm = FakeLLMClient()
    executor = ReviewExecutor(registry, llm_client=llm, mode=ReviewMode.BOTH)
    result = executor.review_document(document)

    assert len(llm.prompts) == 1
    assert "接口要求" in llm.prompts[0]
    assert "功能要求" not in llm.prompts[0]
    assert result.total_issues == 0


def test_required_elements_are_checked_before_llm():
    registry = RuleRegistry()
    registry.register(Rule(
        rule_id="interface_rule",
        name="接口要求",
        description="检查接口要素",
        category=RuleCategory.CUSTOM,
        severity=RuleSeverity.ERROR,
        review_type=ReviewType.LLM,
        scope=RuleScope.BODY,
        target_headings=["接口要求"],
        required_elements=["机械接口", "电气接口", "电源接口", "信号接口"],
    ))
    document = ParsedDocument(
        file_path="test.docx",
        title="测试文档",
        sections=[
            DocumentSection("s1", ContentType.PARAGRAPH, "接口要求\n机械接口\n电气接口", metadata={"region": "body", "heading_text": "接口要求"}),
        ],
        raw_text="",
    )

    llm = FakeLLMClient()
    executor = ReviewExecutor(registry, llm_client=llm, mode=ReviewMode.BOTH)
    result = executor.review_document(document)

    assert len(llm.prompts) == 0
    issue = result.section_results[0].rule_results[0]
    assert issue.rule_id == "interface_rule"
    assert "电源接口" in issue.message
    assert "信号接口" in issue.message


def test_missing_target_heading_rule_reports_once_for_document():
    registry = RuleRegistry()
    registry.register(Rule(
        rule_id="life_rule",
        name="寿命要求",
        description="检查寿命要求章节",
        category=RuleCategory.CUSTOM,
        severity=RuleSeverity.ERROR,
        review_type=ReviewType.LLM,
        scope=RuleScope.BODY,
        target_headings=["寿命要求", "贮存期", "首翻期", "总寿命"],
        required_elements=["贮存期", "首翻期", "总寿命"],
    ))
    document = ParsedDocument(
        file_path="test.docx",
        title="测试文档",
        sections=[
            DocumentSection("s1", ContentType.PARAGRAPH, "功能要求\n这里没有寿命内容", metadata={"region": "body", "heading_text": "功能要求"}),
            DocumentSection("s2", ContentType.PARAGRAPH, "接口要求\n机械接口\n电气接口", metadata={"region": "body", "heading_text": "接口要求"}),
        ],
        raw_text="",
    )

    llm = FakeLLMClient()
    executor = ReviewExecutor(registry, llm_client=llm, mode=ReviewMode.BOTH)
    result = executor.review_document(document)

    assert len(llm.prompts) == 0
    assert result.total_issues == 1
    issue = result.section_results[-1].rule_results[0]
    assert issue.section_id == "document_structure"
    assert issue.rule_id == "life_rule"
    assert "未找到规则要求的目标章节" in issue.message


def test_table_field_regex_rule_passes_for_cover_table_value():
    registry = RuleRegistry()
    registry.register(Rule(
        rule_id="stage_rule",
        name="阶段标识",
        description="检查阶段标识格式",
        category=RuleCategory.CUSTOM,
        severity=RuleSeverity.ERROR,
        review_type=ReviewType.RULE,
        scope=RuleScope.COVER,
        params={
            "check_type": "table_field_regex",
            "field_labels": ["阶段标识", "审查阶段标识"],
            "pattern": r"^.+-AB$",
        },
    ))
    document = ParsedDocument(
        file_path="test.docx",
        title="测试文档",
        sections=[
            DocumentSection(
                "cover",
                ContentType.TABLE,
                "[0] 阶段标识 | [1] XXX-AB",
                metadata={
                    "region": "cover",
                    "table_cells": [
                        {"row": 0, "col": 0, "text": "阶段标识"},
                        {"row": 0, "col": 1, "text": "XXX-AB"},
                    ],
                },
            ),
        ],
        raw_text="",
    )

    executor = ReviewExecutor(registry, llm_client=None, mode=ReviewMode.RULE_ONLY)
    result = executor.review_document(document)

    assert result.total_issues == 0
    assert result.section_results[0].rule_results[0].passed is True


def test_table_field_regex_rule_fails_for_invalid_cover_table_value():
    registry = RuleRegistry()
    registry.register(Rule(
        rule_id="stage_rule",
        name="阶段标识",
        description="检查阶段标识格式",
        category=RuleCategory.CUSTOM,
        severity=RuleSeverity.ERROR,
        review_type=ReviewType.RULE,
        scope=RuleScope.COVER,
        params={
            "check_type": "table_field_regex",
            "field_labels": ["阶段标识", "审查阶段标识"],
            "pattern": r"^.+-AB$",
        },
    ))
    document = ParsedDocument(
        file_path="test.docx",
        title="测试文档",
        sections=[
            DocumentSection(
                "cover",
                ContentType.TABLE,
                "[0] 审查阶段标识 | [1] 123-AC",
                metadata={
                    "region": "cover",
                    "table_cells": [
                        {"row": 0, "col": 0, "text": "审查阶段标识"},
                        {"row": 0, "col": 1, "text": "123-AC"},
                    ],
                },
            ),
        ],
        raw_text="",
    )

    executor = ReviewExecutor(registry, llm_client=None, mode=ReviewMode.RULE_ONLY)
    result = executor.review_document(document)

    assert result.total_issues == 1
    issue = result.section_results[0].rule_results[0]
    assert issue.passed is False
    assert "不符合格式要求" in issue.message


def test_table_field_regex_rule_supports_label_and_value_in_same_cell():
    registry = RuleRegistry()
    registry.register(Rule(
        rule_id="stage_rule",
        name="阶段标识",
        description="检查阶段标识格式",
        category=RuleCategory.CUSTOM,
        severity=RuleSeverity.ERROR,
        review_type=ReviewType.RULE,
        scope=RuleScope.COVER,
        params={
            "check_type": "table_field_regex",
            "field_labels": ["阶段标识", "审查阶段标识"],
            "pattern": r"^.+-AB$",
        },
    ))
    document = ParsedDocument(
        file_path="test.docx",
        title="测试文档",
        sections=[
            DocumentSection(
                "cover",
                ContentType.TABLE,
                "[0] 审查阶段标识：POI-AB",
                metadata={
                    "region": "cover",
                    "table_cells": [
                        {"row": 0, "col": 0, "text": "审查阶段标识：POI-AB"},
                    ],
                },
            ),
        ],
        raw_text="",
    )

    executor = ReviewExecutor(registry, llm_client=None, mode=ReviewMode.RULE_ONLY)
    result = executor.review_document(document)

    assert result.total_issues == 0
    assert result.section_results[0].rule_results[0].passed is True
