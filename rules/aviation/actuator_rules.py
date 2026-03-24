from rules.base_rule import Rule, RuleResult, RuleSeverity, RuleCategory
from models.document import DocumentSection


def check_actuator_keywords(section: DocumentSection, context: dict) -> RuleResult:
    required_terms = ["作动器", "冗余", "液压", "电传"]

    missing = [t for t in required_terms if t not in section.text]

    return RuleResult(
        rule_id="actuator_keywords",
        rule_name="作动系统关键术语检查",
        passed=len(missing) == 0,
        severity=RuleSeverity.WARNING,
        message=f"缺少关键术语: {', '.join(missing)}" if missing else "术语完整",
        section_id=section.section_id,
        suggestions=[f"建议补充术语: {t}" for t in missing]
    )


def create_actuator_rules():
    return [
        Rule(
            rule_id="actuator_keywords",
            name="作动系统关键术语检查",
            description="检查文档是否包含作动系统关键术语",
            category=RuleCategory.CONTENT,
            severity=RuleSeverity.WARNING,
            check_func=check_actuator_keywords,
            source="aviation",
            enabled=False
        )
    ]
