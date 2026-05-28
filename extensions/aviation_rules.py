"""
参考扩展：航空规范引用格式检查规则。

演示如何通过扩展机制添加规则，无需修改任何核心源码。
"""
import re
from typing import List

from rules.base_rule import Rule, RuleResult, RuleSeverity, RuleCategory, ReviewType, ReviewPhase
from models.document import DocumentSection, ContentType


def _check_spec_reference(section: DocumentSection, context: dict) -> RuleResult:
    """检查规范引用是否符合标准格式。"""
    if section.content_type not in [ContentType.PARAGRAPH, ContentType.HEADING]:
        return RuleResult(
            rule_id="spec_reference_format",
            rule_name="规范引用格式检查",
            passed=True,
            severity=RuleSeverity.INFO,
            message="非文本内容，跳过"
        )

    # 匹配 DO-160, RTCA/DO-xxx, MIL-STD-xxx, GJB-xxx, HB-xxx 等规范引用
    spec_pattern = r'(?:RTCA/DO-\d+|MIL-STD-\w+|GJB\s*\d+|HB\s*\d+|DO-\d+)'
    matches = re.findall(spec_pattern, section.text)

    if matches:
        return RuleResult(
            rule_id="spec_reference_format",
            rule_name="规范引用格式检查",
            passed=True,
            severity=RuleSeverity.INFO,
            message=f"发现规范引用: {', '.join(matches)}",
            section_id=section.section_id,
            details={"references": matches}
        )

    return RuleResult(
        rule_id="spec_reference_format",
        rule_name="规范引用格式检查",
        passed=True,
        severity=RuleSeverity.INFO,
        message="未发现规范引用",
        section_id=section.section_id
    )


def register_rules() -> List[Rule]:
    """扩展入口：注册规则。"""
    return [
        Rule(
            rule_id="spec_reference_format",
            name="规范引用格式检查",
            description="检查航空规范引用（RTCA/DO、MIL-STD、GJB、HB）是否存在及格式",
            category=RuleCategory.COMPLIANCE,
            severity=RuleSeverity.INFO,
            check_func=_check_spec_reference,
            source="aviation",
            review_type=ReviewType.BOTH,
            phase=ReviewPhase.STANDARD_COMPLIANCE
        )
    ]
