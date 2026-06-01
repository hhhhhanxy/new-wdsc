"""
五阶段审查执行器。

按顺序执行：格式 → 完整性 → 一致性 → 标准符合性 → 追溯性
"""
import logging
from typing import List, Dict, Any, Optional, Callable

from core.executor import (
    ReviewExecutor, ReviewMode, DocumentReviewResult, SectionReviewResult,
    PhaseResult, PhasedDocumentReviewResult, _rule_prompt_description,
)
from models.document import ParsedDocument, DocumentType
from rules.base_rule import (
    Rule, RuleResult, RuleRegistry, RuleSeverity,
    ReviewType, ReviewPhase, PHASE_ORDER,
)
from core.utils import should_use_rule_check, should_use_llm_check

logger = logging.getLogger(__name__)


class PhasedReviewExecutor(ReviewExecutor):
    """五阶段顺序审查流水线。"""

    def review_document(
        self,
        document: ParsedDocument,
        rules: List[Rule] = None,
        context: Dict[str, Any] = None,
        progress_callback: Optional[Callable[[ReviewPhase, float], None]] = None,
    ) -> PhasedDocumentReviewResult:
        """
        执行五阶段审查，聚合结果。
        """
        from datetime import datetime
        start_time = datetime.now()

        rules = rules or self.rule_registry.get_enabled_rules()
        context = context or {}
        context["found_sections"] = {s.text[:50] for s in document.sections if s.text}

        doc_type = document.doc_type or document.detected_doc_type

        result = PhasedDocumentReviewResult(
            document_path=document.file_path,
            document_title=document.title,
            doc_type=doc_type,
        )

        total_phases = len(PHASE_ORDER)

        for idx, phase in enumerate(PHASE_ORDER):
            logger.info("执行审查阶段 %d/%d: %s", idx + 1, total_phases, phase.value)

            phase_result = self._execute_phase(phase, document, rules, context, doc_type)
            result.phase_results[phase] = phase_result

            # 聚合阶段结果到总结果
            for rr in phase_result.rule_results:
                # 找到或创建对应的 SectionReviewResult
                sr = next((s for s in result.section_results if s.section_id == rr.section_id), None)
                if sr is None:
                    sr = SectionReviewResult(section_id=rr.section_id or "", section_text="")
                    result.section_results.append(sr)
                sr.add_rule_result(rr)

                if not rr.passed:
                    result.total_issues += 1
                    if rr.severity == RuleSeverity.ERROR:
                        result.errors += 1
                    elif rr.severity == RuleSeverity.WARNING:
                        result.warnings += 1
                    if rr.rule_source == "LLM":
                        result.llm_issues += 1

            if progress_callback:
                progress_callback(phase, (idx + 1) / total_phases)

        # 汇总通过状态
        result.overall_passed = all(pr.passed for pr in result.phase_results)

        # LLM 文档总结
        if ReviewMode.uses_llm(self.mode):
            result.summary = self._get_llm_document_summary(document, rules)

        end_time = datetime.now()
        result.review_time = str(end_time - start_time)

        return result

    def _execute_phase(
        self,
        phase: ReviewPhase,
        document: ParsedDocument,
        rules: List[Rule],
        context: Dict[str, Any],
        doc_type: Optional[DocumentType] = None,
    ) -> PhaseResult:
        """执行单个审查阶段。"""
        phase_result = PhaseResult(phase=phase)

        # 筛选该阶段的规则
        phase_rules = [r for r in rules if r.phase == phase]
        if doc_type is not None:
            phase_rules = [r for r in phase_rules if not r.doc_types or doc_type in r.doc_types]

        if not phase_rules:
            logger.debug("阶段 %s 无适用规则，跳过", phase.value)
            return phase_result

        rule_check_rules = [r for r in phase_rules if should_use_rule_check(r)]
        llm_check_rules = [r for r in phase_rules if should_use_llm_check(r)]

        # 规则检查
        if ReviewMode.uses_rule_engine(self.mode):
            for section in document.sections:
                for rule in rule_check_rules:
                    try:
                        rr = rule.check(section, context)
                        rr.phase = phase
                        phase_result.add_rule_result(rr)
                    except Exception as e:
                        logger.debug("规则 %s 检查失败: %s", rule.rule_id, e)

                phase_result.section_count += 1

        # LLM 检查
        if ReviewMode.uses_llm(self.mode) and llm_check_rules:
            llm_results = self._get_llm_section_review_phased(document, llm_check_rules, phase)
            if llm_results:
                for rr in llm_results:
                    phase_result.add_rule_result(rr)

        return phase_result

    def _get_llm_section_review_phased(
        self,
        document: ParsedDocument,
        rules: List[Rule],
        phase: ReviewPhase,
    ) -> Optional[List[RuleResult]]:
        """对整个文档执行 LLM 阶段性审查。"""
        if not self.prompt_builder:
            return None

        rules_info = [{"name": r.name, "description": _rule_prompt_description(r)} for r in rules]
        prompt = self.prompt_builder.build_section_review_prompt(
            document.raw_text[:5000],
            rules_info,
        )

        try:
            response = self.llm_client.generate(prompt)
            llm_result = self.parser.parse(response.content)

            if not isinstance(llm_result, dict):
                return None

            results = []
            for issue in llm_result.get("issues", []):
                severity_str = issue.get("severity", "warning")
                try:
                    severity = RuleSeverity(severity_str)
                except ValueError:
                    severity = RuleSeverity.WARNING

                rr = RuleResult(
                    rule_id=issue.get("rule_id", "llm_generated"),
                    rule_name=issue.get("rule_name", "LLM 审查"),
                    passed=False,
                    severity=severity,
                    message=issue.get("description", ""),
                    section_id=issue.get("section_id"),
                    suggestions=[issue.get("suggestion", "")] if issue.get("suggestion") else [],
                    rule_source="LLM",
                    phase=phase,
                )
                results.append(rr)

            return results

        except Exception as e:
            logger.error("LLM 阶段审查失败 (%s): %s", phase.value, e)
            return None
