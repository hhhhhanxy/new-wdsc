from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Any
from enum import Enum
from models.document import DocumentSection


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
    
    def enable_rule(self, rule_id: str):
        if rule_id in self._rules:
            self._rules[rule_id].enabled = True
    
    def disable_rule(self, rule_id: str):
        if rule_id in self._rules:
            self._rules[rule_id].enabled = False
