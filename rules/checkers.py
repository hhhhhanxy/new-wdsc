import re
from typing import List
from models.document import DocumentSection, ContentType
from rules.base_rule import Rule, RuleResult, RuleSeverity, RuleCategory, BaseRuleChecker


class RequiredSectionChecker(BaseRuleChecker):
    def __init__(self, required_sections: List[str]):
        self.required_sections = required_sections
    
    def check(self, section: DocumentSection, context: dict) -> RuleResult:
        found_sections = context.get("found_sections", set())
        missing = set(self.required_sections) - found_sections
        
        return RuleResult(
            rule_id="required_sections",
            rule_name="必需章节检查",
            passed=len(missing) == 0,
            severity=RuleSeverity.ERROR,
            message=f"缺少必需章节: {', '.join(missing)}" if missing else "所有必需章节都存在",
            suggestions=[f"请添加章节: {s}" for s in missing] if missing else []
        )


class KeywordChecker(BaseRuleChecker):
    def __init__(self, required_keywords: List[str], forbidden_keywords: List[str] = None):
        self.required_keywords = required_keywords
        self.forbidden_keywords = forbidden_keywords or []
    
    def check(self, section: DocumentSection, context: dict) -> RuleResult:
        text = section.text.lower()
        
        missing_required = []
        for keyword in self.required_keywords:
            if keyword.lower() not in text:
                missing_required.append(keyword)
        
        found_forbidden = []
        for keyword in self.forbidden_keywords:
            if keyword.lower() in text:
                found_forbidden.append(keyword)
        
        passed = len(missing_required) == 0 and len(found_forbidden) == 0
        
        messages = []
        if missing_required:
            messages.append(f"缺少关键词: {', '.join(missing_required)}")
        if found_forbidden:
            messages.append(f"发现禁止关键词: {', '.join(found_forbidden)}")
        
        return RuleResult(
            rule_id="keyword_check",
            rule_name="关键词检查",
            passed=passed,
            severity=RuleSeverity.WARNING,
            message="; ".join(messages) if messages else "关键词检查通过",
            section_id=section.section_id
        )


class FormatChecker(BaseRuleChecker):
    def __init__(self, pattern: str, description: str):
        self.pattern = re.compile(pattern)
        self.description = description
    
    def check(self, section: DocumentSection, context: dict) -> RuleResult:
        matches = self.pattern.findall(section.text)
        
        return RuleResult(
            rule_id=f"format_{self.description}",
            rule_name=f"格式检查: {self.description}",
            passed=len(matches) > 0,
            severity=RuleSeverity.INFO,
            message=f"找到 {len(matches)} 处匹配" if matches else f"未找到符合 {self.description} 的内容",
            section_id=section.section_id,
            details={"matches": matches}
        )


def create_default_rules() -> List[Rule]:
    rules = []
    
    def check_title_format(section: DocumentSection, context: dict) -> RuleResult:
        if section.content_type != ContentType.HEADING:
            return RuleResult(
                rule_id="title_format",
                rule_name="标题格式检查",
                passed=True,
                severity=RuleSeverity.INFO,
                message="非标题段落，跳过检查"
            )
        
        has_number = bool(re.match(r'^\d+\.?\s', section.text))
        return RuleResult(
            rule_id="title_format",
            rule_name="标题格式检查",
            passed=has_number,
            severity=RuleSeverity.WARNING,
            message="标题应包含编号" if not has_number else "标题格式正确",
            section_id=section.section_id,
            suggestions=["建议在标题前添加编号，如：1. 概述"] if not has_number else []
        )
    
    rules.append(Rule(
        rule_id="title_format",
        name="标题格式检查",
        description="检查标题是否包含编号",
        category=RuleCategory.FORMAT,
        severity=RuleSeverity.WARNING,
        check_func=check_title_format
    ))
    

    
    # 添加语法和标点检查规则
    from .grammar_checker import create_grammar_rule
    grammar_rule = create_grammar_rule()
    rules.append(grammar_rule)
    
    return rules
