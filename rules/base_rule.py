from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Any, Dict
from enum import Enum
from models.document import DocumentSection, DocumentType


class RuleSeverity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class RuleCategory(Enum):
    FORMAT = "format"
    CONTENT = "content"
    LOGIC = "logic"
    COMPLIANCE = "compliance"
    CUSTOM = "custom"


class ReviewType(Enum):
    RULE = "rule"
    LLM = "llm"
    BOTH = "both"


class ReviewPhase(Enum):
    FORMAT = "format"                         # 格式检查
    COMPLETENESS = "completeness"             # 完整性检查
    CONSISTENCY = "consistency"               # 一致性检查
    STANDARD_COMPLIANCE = "standard_compliance"  # 标准符合性检查
    TRACEABILITY = "traceability"             # 追溯性检查


PHASE_ORDER = [
    ReviewPhase.FORMAT,
    ReviewPhase.COMPLETENESS,
    ReviewPhase.CONSISTENCY,
    ReviewPhase.STANDARD_COMPLIANCE,
    ReviewPhase.TRACEABILITY,
]

PHASE_DISPLAY_NAMES = {
    ReviewPhase.FORMAT: "格式检查",
    ReviewPhase.COMPLETENESS: "完整性检查",
    ReviewPhase.CONSISTENCY: "一致性检查",
    ReviewPhase.STANDARD_COMPLIANCE: "标准符合性检查",
    ReviewPhase.TRACEABILITY: "追溯性检查",
}


@dataclass
class TextPosition:
    """问题在文本中的位置信息。"""
    start_char: Optional[int] = None
    end_char: Optional[int] = None
    line_number: Optional[int] = None
    context_snippet: Optional[str] = None


@dataclass
class FixSuggestion:
    """结构化的修复建议。"""
    description: str = ""
    replacement_text: Optional[str] = None
    confidence: float = 0.0
    auto_fixable: bool = False


@dataclass
class RuleResult:
    rule_id: str
    rule_name: str
    passed: bool
    severity: RuleSeverity
    message: str
    section_id: Optional[str] = None
    suggestions: List[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)
    rule_source: str = "RULE"
    position: Optional[TextPosition] = None
    fix_suggestion: Optional[FixSuggestion] = None
    rule_reference: Optional[str] = None
    phase: Optional[ReviewPhase] = None


@dataclass
class Rule:
    rule_id: str
    name: str
    description: str
    category: RuleCategory
    severity: RuleSeverity
    enabled: bool = True
    check_func: Optional[Callable] = None
    source: str = "common"
    review_type: ReviewType = ReviewType.RULE
    phase: ReviewPhase = ReviewPhase.FORMAT
    doc_types: List[DocumentType] = field(default_factory=list)
    params: Dict[str, Any] = field(default_factory=dict)

    def check(self, section: DocumentSection, context: dict = None) -> RuleResult:
        if not self.enabled:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message="Rule is disabled"
            )
        
        if self.check_func:
            return self.check_func(section, context or {})
        
        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.name,
            passed=True,
            severity=self.severity,
            message="No check function defined"
        )


class BaseRuleChecker(ABC):
    @abstractmethod
    def check(self, section: DocumentSection, context: dict) -> RuleResult:
        pass


class RuleRegistry:
    def __init__(self):
        self._rules: dict[str, Rule] = {}
    
    def register(self, rule: Rule):
        self._rules[rule.rule_id] = rule
    
    def unregister(self, rule_id: str):
        if rule_id in self._rules:
            del self._rules[rule_id]
    
    def get_rule(self, rule_id: str) -> Optional[Rule]:
        return self._rules.get(rule_id)
    
    def get_all_rules(self) -> List[Rule]:
        return list(self._rules.values())
    
    def get_enabled_rules(self) -> List[Rule]:
        return [r for r in self._rules.values() if r.enabled]
    
    def get_rules_by_category(self, category: RuleCategory) -> List[Rule]:
        return [r for r in self._rules.values() if r.category == category]

    def get_rules_by_phase(self, phase: ReviewPhase, doc_type: DocumentType = None) -> List[Rule]:
        rules = [r for r in self._rules.values() if r.enabled and r.phase == phase]
        if doc_type is not None:
            rules = [r for r in rules if not r.doc_types or doc_type in r.doc_types]
        return rules
    
    def enable_rule(self, rule_id: str):
        if rule_id in self._rules:
            self._rules[rule_id].enabled = True
    
    def disable_rule(self, rule_id: str):
        if rule_id in self._rules:
            self._rules[rule_id].enabled = False
