import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from models.document import ParsedDocument, DocumentSection
from rules.base_rule import Rule, RuleResult, RuleRegistry, RuleSeverity
from llm.client import BaseLLMClient
from llm.prompts import ReviewPromptBuilder
from parsers.review_parser import ReviewResultParser


@dataclass
class SectionReviewResult:
    section_id: str
    section_text: str
    rule_results: List[RuleResult] = field(default_factory=list)
    passed: bool = True

    def add_rule_result(self, result: RuleResult):
        self.rule_results.append(result)
        if not result.passed and result.severity in [RuleSeverity.ERROR, RuleSeverity.WARNING]:
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
    review_time: str = ""
    summary: str = ""

    def add_section_result(self, result: SectionReviewResult):
        self.section_results.append(result)
        if not result.passed:
            self.overall_passed = False

        # 累计问题
        for rule_result in result.rule_results:
            if not rule_result.passed:
                self.total_issues += 1
                if rule_result.severity == RuleSeverity.ERROR:
                    self.errors += 1
                elif rule_result.severity == RuleSeverity.WARNING:
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
        self.prompt_builder = ReviewPromptBuilder() if llm_client else None
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

        # LLM 文档总结（可选）
        if self.use_llm:
            result.summary = self._get_llm_document_summary(document, rules)

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

        # 只执行规则检查（RULE + BOTH）
        for rule in rules:
            try:
                review_type = rule.review_type.value if hasattr(rule.review_type, 'value') else rule.review_type
                if review_type in ["rule", "both"]:
                    rule_result = rule.check(section, context)
                    result.add_rule_result(rule_result)
            except Exception:
                pass

        # LLM 检查
        if self.use_llm and section.text.strip():
            llm_rules = []
            for r in rules:
                try:
                    review_type = r.review_type.value if hasattr(r.review_type, 'value') else r.review_type
                    if review_type in ["llm", "both"]:
                        llm_rules.append(r)
                except Exception:
                    pass
            if llm_rules:
                try:
                    llm_result = self._get_llm_section_review(section, llm_rules)
                    if llm_result and "issues" in llm_result:
                        # 将 LLM 结果转换为 RuleResult
                        for issue in llm_result.get("issues", []):
                            rule_id = issue.get("rule_id", "llm_generated")
                            rule_name = issue.get("rule_name", "LLM 审查")
                            severity_str = issue.get("severity", "warning")
                            severity = RuleSeverity(severity_str) if severity_str in [s.value for s in RuleSeverity] else RuleSeverity.WARNING
                            
                            rule_result = RuleResult(
                                rule_id=rule_id,
                                rule_name=rule_name,
                                passed=False,
                                severity=severity,
                                message=issue.get("description", ""),
                                section_id=section.section_id,
                                suggestions=[issue.get("suggestion", "")] if issue.get("suggestion") else [],
                                rule_source="LLM"
                            )
                            result.add_rule_result(rule_result)
                except Exception:
                    pass

        return result

    def _get_llm_section_review(
        self,
        section: DocumentSection,
        rules: List[Rule]
    ) -> Optional[Dict[str, Any]]:
        if not self.prompt_builder:
            return None

        rules_info = [{"name": r.name, "description": r.description} for r in rules]

        try:
            prompt = self.prompt_builder.build_section_review_prompt(section.text, rules_info)
            response = self.llm_client.generate(prompt)
            llm_result = self.parser.parse(response.content)
            if not isinstance(llm_result, dict):
                llm_result = {"error": "LLM返回格式错误"}
            return llm_result
        except Exception as e:
            return {"error": f"LLM审查失败: {str(e)}"}

    def _get_llm_document_summary(
        self,
        document: ParsedDocument,
        rules: List[Rule]
    ) -> str:
        if not self.prompt_builder:
            return ""
        rules_info = []
        for r in rules:
            try:
                review_type = r.review_type.value if hasattr(r.review_type, 'value') else r.review_type
                if review_type in ["llm", "both"]:
                    rules_info.append({"name": r.name, "description": r.description})
            except Exception:
                pass
        try:
            prompt = self.prompt_builder.build_document_review_prompt(document.title, document.raw_text[:5000], rules_info)
            response = self.llm_client.generate(prompt)
            summary_result = self.parser.parse(response.content)
            if not isinstance(summary_result, dict):
                summary_result = {"error": "LLM返回格式错误"}
            return summary_result.get("summary", "")
        except Exception as e:
            return f"LLM审查失败: {str(e)}"