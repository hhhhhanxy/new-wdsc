import re
from typing import List
from models.document import DocumentSection, ContentType
from rules.base_rule import Rule, RuleResult, RuleSeverity, RuleCategory, BaseRuleChecker


class GrammarAndPunctuationChecker(BaseRuleChecker):

    def __init__(self):

        # 标点问题
        self.punctuation_patterns = [
            (r'[，。；：！？]\s*[，。；：！？]', "连续标点符号"),
            (r'\s+[，。；：！？]', "标点前有空格"),
            (r'[a-zA-Z0-9]+[，。；：！？]', "英文/数字后直接跟中文标点"),
            (r'[，。；：！？][a-zA-Z0-9]', "中文标点后直接跟英文/数字"),
            (r'\s+\.', "句点前有空格"),
            (r'\.[a-zA-Z0-9]', "句点后无空格"),
        ]

        # 格式问题
        self.format_patterns = [
            (r'\t', "使用了制表符"),
            (r'\s{3,}', "连续空格过多"),
            (r'\s+$', "行尾有空格"),
        ]

        # 常见错误示例
        self.common_mistakes = {
            "的地得": [
                (r'地([的得])', "'地'后应接动词"),
                (r'的([地得])', "'的'后应接名词"),
                (r'得([的地])', "'得'后应接形容词或副词"),
            ],
            "标点符号": [
                (r'([，。；：！？]){2,}', "连续标点"),
            ],
        }

    def check(self, section: DocumentSection, context: dict) -> RuleResult:

        if section.content_type not in [ContentType.PARAGRAPH, ContentType.HEADING]:
            return RuleResult(
                rule_id="grammar_punctuation",
                rule_name="语法和标点检查",
                passed=True,
                severity=RuleSeverity.INFO,
                message="非文本内容，跳过检查"
            )

        text = section.text
        issues = []

        # =========================
        # 标点检查
        # =========================
        for pattern, description in self.punctuation_patterns:
            matches = re.findall(pattern, text)
            if matches:
                issues.append(f"{description}: 发现 {len(matches)} 处问题")

        # =========================
        # 格式检查
        # =========================
        for pattern, description in self.format_patterns:
            matches = re.findall(pattern, text)
            if matches:
                issues.append(f"{description}: 发现 {len(matches)} 处问题")

        # =========================
        # 错别字检查
        # =========================
        for category, patterns in self.common_mistakes.items():
            for pattern, description in patterns:
                matches = re.findall(pattern, text)
                if matches:
                    issues.append(f"{category}使用不当: {description}")

        # =========================
        # 段落结构检查
        # =========================
        if section.content_type != ContentType.PARAGRAPH:
            # 标题不能有行首空格
            if text.startswith(' ') or text.startswith('\t') or text.startswith('\u3000'):
                issues.append("标题行首不应有空格")

        passed = len(issues) == 0

        return RuleResult(
            rule_id="grammar_punctuation",
            rule_name="语法和标点检查",
            passed=passed,
            severity=RuleSeverity.WARNING,
            message="; ".join(issues) if issues else "语法和标点使用正确",
            section_id=section.section_id,
            suggestions=self._generate_suggestions(issues)
        )

    def _generate_suggestions(self, issues: List[str]) -> List[str]:

        suggestions = []

        if any("连续标点" in issue for issue in issues):
            suggestions.append("避免使用连续的标点符号")

        if any("标点前有空格" in issue for issue in issues):
            suggestions.append("标点符号前不应有空格")

        if any("英文/数字后直接跟中文标点" in issue for issue in issues):
            suggestions.append("英文/数字后应加空格再使用中文标点")

        if any("中文标点后直接跟英文/数字" in issue for issue in issues):
            suggestions.append("中文标点后应加空格再使用英文或数字")

        if any("使用了制表符" in issue for issue in issues):
            suggestions.append("建议使用空格代替制表符")

        if any("连续空格过多" in issue for issue in issues):
            suggestions.append("避免使用过多连续空格")

        if any("行尾有空格" in issue for issue in issues):
            suggestions.append("删除行尾多余空格")

        return suggestions


def create_grammar_rule() -> Rule:

    checker = GrammarAndPunctuationChecker()

    return Rule(
        rule_id="grammar_punctuation",
        name="语法和标点检查",
        description="检查语法、格式、错别字和标点符号使用不当的问题",
        category=RuleCategory.FORMAT,
        severity=RuleSeverity.WARNING,
        check_func=checker.check
    )
