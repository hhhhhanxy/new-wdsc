import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from models.document import ParsedDocument, DocumentSection
from rules.base_rule import Rule, RuleResult, RuleRegistry, RuleSeverity
from llm.client import BaseLLMClient, LLMResponse
from llm.prompts import ReviewPromptBuilder
from parsers.review_parser import ReviewResultParser


@dataclass
class SectionReviewResult:
    section_id: str
    section_text: str
    rule_results: List[RuleResult] = field(default_factory=list)
    llm_review: Optional[Dict[str, Any]] = None
    passed: bool = True
    llm_passed: bool = True
    
    def add_rule_result(self, result: RuleResult):
        self.rule_results.append(result)
        if not result.passed and result.severity in [RuleSeverity.ERROR, RuleSeverity.WARNING]:
            self.passed = False
    
    def add_llm_result(self, llm_result: Dict[str, Any]):
        self.llm_review = llm_result
        if "error" in llm_result:
            self.llm_passed = False
        elif "passed" in llm_result:
            self.llm_passed = llm_result.get("passed", True)
            if not self.llm_passed:
                self.passed = False


@dataclass
class DocumentReviewResult:
    document_path: str
    document_title: str
    section_results: List[SectionReviewResult] = field(default_factory=list)
    overall_passed: bool = True
    total_issues: int = 0
    errors: int = 0
    warnings: int = 0
    llm_issues: int = 0
    review_time: str = ""
    summary: str = ""
    
    def add_section_result(self, result: SectionReviewResult):
        self.section_results.append(result)
        if not result.passed:
            self.overall_passed = False
        
        for rule_result in result.rule_results:
            if not rule_result.passed:
                self.total_issues += 1
                if rule_result.severity == RuleSeverity.ERROR:
                    self.errors += 1
                elif rule_result.severity == RuleSeverity.WARNING:
                    self.warnings += 1
        
        if result.llm_review and "issues" in result.llm_review:
            llm_issues = result.llm_review.get("issues", [])
            self.llm_issues += len(llm_issues)
            self.total_issues += len(llm_issues)
            if not result.llm_passed:
                for issue in llm_issues:
                    severity = issue.get("severity", "info")
                    if severity == "error":
                        self.errors += 1
                    elif severity == "warning":
                        self.warnings += 1


class ReviewExecutor:
    def __init__(
        self,
        rule_registry: RuleRegistry,
        llm_client: Optional[BaseLLMClient] = None,
        use_llm: bool = True
    ):
        self.rule_registry = rule_registry
        self.llm_client = llm_client
        self.use_llm = use_llm and llm_client is not None
        self.prompt_builder = ReviewPromptBuilder(llm_client) if llm_client else None
        self.parser = ReviewResultParser()
    
    def review_document(
        self,
        document: ParsedDocument,
        rules: List[Rule] = None,
        context: Dict[str, Any] = None
    ) -> DocumentReviewResult:
        start_time = datetime.now()
        
        rules = rules or self.rule_registry.get_enabled_rules()
        context = context or {}
        
        context["found_sections"] = {s.text[:50] for s in document.sections if s.text}
        
        result = DocumentReviewResult(
            document_path=document.file_path,
            document_title=document.title
        )
        
        for section in document.sections:
            section_result = self._review_section(section, rules, context)
            result.add_section_result(section_result)
        
        if self.use_llm:
            llm_summary = self._get_llm_document_review(document, rules)
            if llm_summary:
                result.summary = llm_summary
        
        end_time = datetime.now()
        result.review_time = str(end_time - start_time)
        
        return result
    
    def _review_section(
        self,
        section: DocumentSection,
        rules: List[Rule],
        context: Dict[str, Any]
    ) -> SectionReviewResult:
        result = SectionReviewResult(
            section_id=section.section_id,
            section_text=section.text
        )
        
        for rule in rules:
            rule_result = rule.check(section, context)
            result.add_rule_result(rule_result)
        
        if self.use_llm and section.text.strip():
            llm_result = self._get_llm_section_review(section, rules)
            if llm_result:
                result.add_llm_result(llm_result)
        
        return result
    
    def _get_llm_section_review(
        self,
        section: DocumentSection,
        rules: List[Rule]
    ) -> Optional[Dict[str, Any]]:
        if not self.prompt_builder:
            return None
        
        rules_info = [
            {"name": r.name, "description": r.description}
            for r in rules
        ]
        
        try:
            response = self.prompt_builder.review_section(section.text, rules_info)
            llm_result = self.parser.parse(response.content)
            
            if not isinstance(llm_result, dict):
                llm_result = {"error": "LLM返回格式错误"}
            
            return llm_result
        except Exception as e:
            error_msg = str(e)
            if "Not Found" in error_msg:
                return {"error": "LLM模型未找到，请检查模型名称是否正确"}
            elif "401" in error_msg:
                return {"error": "LLM API密钥无效，请检查API密钥是否正确"}
            else:
                return {"error": f"LLM审查失败: {error_msg}"}
    
    def _get_llm_document_review(
        self,
        document: ParsedDocument,
        rules: List[Rule]
    ) -> Optional[str]:
        if not self.prompt_builder:
            return None
        
        rules_info = [
            {"name": r.name, "description": r.description}
            for r in rules
        ]
        
        try:
            response = self.prompt_builder.review_document(
                document.title,
                document.raw_text[:5000],
                rules_info
            )
            llm_summary = self.parser.parse(response.content)
            
            if not isinstance(llm_summary, dict):
                llm_summary = {"error": "LLM返回格式错误"}
            
            return llm_summary.get("summary", "")
        except Exception as e:
            error_msg = str(e)
            if "Not Found" in error_msg:
                return "LLM审查失败: 模型未找到，请检查模型名称是否正确"
            elif "401" in error_msg:
                return "LLM审查失败: API密钥无效，请检查API密钥是否正确"
            else:
                return f"LLM审查失败: {error_msg}"
    

