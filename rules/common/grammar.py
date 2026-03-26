import re
from typing import List
from models.document import DocumentSection, ContentType
from rules.base_rule import Rule, RuleResult, RuleSeverity, RuleCategory, ReviewType

class GrammarChecker:

    def __init__(self):
        self.common_mistakes = {
            "的地得": [
                (r'地([^的得]|$)', "'地'后应接动词，不能接名词"),
                (r'的([^的得]|$)', "'的'后应接名词，不能接动词"),
                (r'得([^的得]|$)', "'得'后应接形容词或副词"),
            ]
        }

    def check(self, section: DocumentSection, context: dict) -> RuleResult:

        if section.content_type not in [ContentType.PARAGRAPH, ContentType.HEADING]:
            return RuleResult(
                rule_id="grammar",
                rule_name="语法检查",
                passed=True,
                severity=RuleSeverity.INFO,
                message="非文本内容，跳过"
            )

        text = section.text
        issues = []

        for category, patterns in self.common_mistakes.items():
            for pattern, description in patterns:
                matches = re.findall(pattern, text)
                if matches:
                    issues.append(f"{category}使用不当: {description}")

        passed = len(issues) == 0

        return RuleResult(
            rule_id="grammar",
            rule_name="语法检查",
            passed=passed,
            severity=RuleSeverity.WARNING,
            message="; ".join(issues) if issues else "语法正确",
            section_id=section.section_id,
            suggestions=self._generate_suggestions(issues)
        )

    def _generate_suggestions(self, issues: List[str]) -> List[str]:
        suggestions = []

        if any("的地得" in issue for issue in issues):
            suggestions.append("请根据语法规则正确使用“的、地、得”")

        return suggestions


def create_grammar_rule() -> Rule:
    checker = GrammarChecker()

    return Rule(
        rule_id="grammar",
        name="语法检查",
        description="检查常见语法错误（如的地得）",
        category=RuleCategory.CONTENT,
        severity=RuleSeverity.WARNING,
        check_func=checker.check,
        review_type=ReviewType.BOTH
    )