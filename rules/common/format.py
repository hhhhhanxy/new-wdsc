import re
from typing import List
from models.document import DocumentSection, ContentType
from rules.base_rule import Rule, RuleResult, RuleSeverity, RuleCategory


class FormatChecker:

    def __init__(self):

        self.punctuation_patterns = [
            (r'[，。；：！？]\s*[，。；：！？]', "连续标点符号"),
            (r'\s+[，。；：！？]', "标点前有空格"),
            (r'[a-zA-Z0-9]+[，。；：！？]', "英文/数字后直接跟中文标点"),
            (r'[，。；：！？][a-zA-Z0-9]', "中文标点后直接跟英文/数字"),
            (r'\s+\.', "句点前有空格"),
            (r'\.[a-zA-Z0-9]', "句点后无空格"),
        ]

        self.format_patterns = [
            (r'\t', "使用了制表符"),
            (r'\s{3,}', "连续空格过多"),
            (r'\s+$', "行尾有空格"),
        ]

    def check(self, section: DocumentSection, context: dict) -> RuleResult:

        if section.content_type not in [ContentType.PARAGRAPH, ContentType.HEADING]:
            return RuleResult(
                rule_id="format",
                rule_name="格式检查",
                passed=True,
                severity=RuleSeverity.INFO,
                message="非文本内容，跳过"
            )

        text = section.text
        issues = []

        # 标点检查
        for pattern, description in self.punctuation_patterns:
            matches = re.findall(pattern, text)
            if matches:
                issues.append(f"{description}: {len(matches)}处")

        # 空格/格式
        for pattern, description in self.format_patterns:
            matches = re.findall(pattern, text)
            if matches:
                issues.append(f"{description}: {len(matches)}处")

        # 标题额外规则
        if section.content_type == ContentType.HEADING:
            if text.startswith((' ', '\t', '\u3000')):
                issues.append("标题行首不应有空格")

        passed = len(issues) == 0

        return RuleResult(
            rule_id="format",
            rule_name="格式检查",
            passed=passed,
            severity=RuleSeverity.WARNING,
            message="; ".join(issues) if issues else "格式正确",
            section_id=section.section_id,
            suggestions=self._generate_suggestions(issues)
        )

    def _generate_suggestions(self, issues: List[str]) -> List[str]:
        suggestions = []

        if any("连续标点" in i for i in issues):
            suggestions.append("避免连续使用标点")

        if any("空格" in i for i in issues):
            suggestions.append("规范空格使用")

        return suggestions


def create_format_rule() -> Rule:
    checker = FormatChecker()

    return Rule(
        rule_id="format",
        name="格式检查",
        description="检查标点、空格和排版问题",
        category=RuleCategory.FORMAT,
        severity=RuleSeverity.WARNING,
        check_func=checker.check
    )