"""
文档审查执行器 - 重构版本
改进：
1. 统一 ReviewType 处理逻辑
2. 添加 LLM 调用重试机制
3. 添加缓存支持
4. 优化错误处理
5. 改进代码结构
"""
import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from models.document import ParsedDocument, DocumentSection, DocumentType
from rules.base_rule import Rule, RuleResult, RuleRegistry, RuleSeverity, ReviewType, ReviewPhase, PHASE_ORDER
from llm.client import BaseLLMClient
from llm.prompts import ReviewPromptBuilder, PromptStyle
from parsers.review_parser import ReviewResultParser

# 导入重构后的工具模块
from core.retry_utils import llm_retry, LLMRetryError, safe_execute
from core.cache import cached, generate_cache_key
from core.utils import (
    get_review_type,
    filter_rules_by_review_type,
    should_use_rule_check,
    should_use_llm_check,
    safe_execute_rule,
    truncate_text
)

logger = logging.getLogger(__name__)


@dataclass
class SectionReviewResult:
    """章节审查结果"""
    section_id: str
    section_text: str
    rule_results: List[RuleResult] = field(default_factory=list)
    passed: bool = True

    def add_rule_result(self, result: RuleResult):
        """添加规则检查结果"""
        self.rule_results.append(result)
        if not result.passed and result.severity in [RuleSeverity.ERROR, RuleSeverity.WARNING]:
            self.passed = False


@dataclass
class DocumentReviewResult:
    """文档审查结果"""
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
        """添加章节审查结果"""
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
                if rule_result.rule_source == "LLM":
                    self.llm_issues += 1


@dataclass
class PhaseResult:
    """单个审查阶段的结果。"""
    phase: ReviewPhase
    passed: bool = True
    rule_results: List[RuleResult] = field(default_factory=list)
    issues_count: int = 0
    section_count: int = 0

    def add_rule_result(self, result: RuleResult):
        self.rule_results.append(result)
        if not result.passed:
            self.issues_count += 1
            if result.severity in [RuleSeverity.ERROR, RuleSeverity.WARNING]:
                self.passed = False


@dataclass
class PhasedDocumentReviewResult(DocumentReviewResult):
    """带阶段分解的文档审查结果。"""
    phase_results: Dict[ReviewPhase, 'PhaseResult'] = field(default_factory=dict)
    doc_type: Optional[DocumentType] = None


class ReviewMode:
    """审查模式"""
    BOTH = "both"           # 规则引擎 + LLM
    RULE_ONLY = "rule_only"  # 仅规则引擎
    LLM_ONLY = "llm_only"   # 仅 LLM

    @classmethod
    def uses_rule_engine(cls, mode: str) -> bool:
        return mode in (cls.BOTH, cls.RULE_ONLY)

    @classmethod
    def uses_llm(cls, mode: str) -> bool:
        return mode in (cls.BOTH, cls.LLM_ONLY)


class ReviewExecutor:
    """文档审查执行器 - 重构版本"""

    def __init__(
        self,
        rule_registry: RuleRegistry,
        llm_client: Optional[BaseLLMClient] = None,
        mode: str = ReviewMode.BOTH,
        enable_cache: bool = None,
        enable_retry: bool = None,
        prompt_style: PromptStyle = PromptStyle.STANDARD,
        enable_cot: bool = None,
        enable_few_shot: bool = None,
        enable_domain_knowledge: bool = True
    ):
        """
        初始化审查执行器

        Args:
            rule_registry: 规则注册表
            llm_client: LLM 客户端
            mode: 审查模式 (both/rule_only/llm_only)
            enable_cache: 是否启用缓存（默认从配置读取）
            enable_retry: 是否启用重试（默认从配置读取）
            prompt_style: Prompt 风格（STANDARD/COT/FEW_SHOT/STRICT）
            enable_cot: 是否启用思维链（默认从配置或 prompt_style 推断）
            enable_few_shot: 是否启用少样本示例（默认从配置或 prompt_style 推断）
            enable_domain_knowledge: 是否注入领域知识
        """
        from config.settings import settings

        self.rule_registry = rule_registry
        self.llm_client = llm_client
        self.mode = mode
        self.enable_cache = enable_cache if enable_cache is not None else settings.cache_enabled
        self.enable_retry = enable_retry if enable_retry is not None else settings.retry_enabled

        # Prompt 配置
        self.enable_cot = enable_cot if enable_cot is not None else (
            prompt_style == PromptStyle.COT or settings.is_dev
        )
        self.enable_few_shot = enable_few_shot if enable_few_shot is not None else (
            prompt_style == PromptStyle.FEW_SHOT or settings.is_prod
        )

        # 初始化辅助组件
        self.prompt_builder = ReviewPromptBuilder(
            style=prompt_style,
            enable_cot=self.enable_cot,
            enable_few_shot=self.enable_few_shot,
            enable_domain_knowledge=enable_domain_knowledge
        ) if llm_client and ReviewMode.uses_llm(mode) else None
        self.parser = ReviewResultParser()

        logger.info(
            f"审查执行器初始化完成 - "
            f"模式: {self.mode}, "
            f"缓存: {self.enable_cache}, "
            f"重试: {self.enable_retry}, "
            f"Prompt风格: {prompt_style.value}, "
            f"CoT: {self.enable_cot}, "
            f"Few-Shot: {self.enable_few_shot}"
        )

    def review_document(
        self,
        document: ParsedDocument,
        rules: List[Rule] = None,
        context: Dict[str, Any] = None
    ) -> DocumentReviewResult:
        """
        审查文档

        Args:
            document: 文档对象
            rules: 规则列表（默认使用所有启用的规则）
            context: 上下文信息

        Returns:
            文档审查结果
        """
        start_time = datetime.now()

        # 获取要使用的规则
        rules = rules or self.rule_registry.get_enabled_rules()
        context = context or {}
        context["found_sections"] = {s.text[:50] for s in document.sections if s.text}

        logger.info(f"开始审查文档: {document.title}, 共 {len(document.sections)} 个章节, {len(rules)} 条规则")

        # 初始化结果
        result = DocumentReviewResult(
            document_path=document.file_path,
            document_title=document.title
        )

        # 逐个审查章节
        for idx, section in enumerate(document.sections):
            logger.debug(f"审查章节 {idx + 1}/{len(document.sections)}: {section.section_id}")
            section_result = self._review_section(section, rules, context)
            result.add_section_result(section_result)

        # LLM 文档总结
        if ReviewMode.uses_llm(self.mode):
            result.summary = self._get_llm_document_summary(document, rules)

        # 计算耗时
        end_time = datetime.now()
        result.review_time = str(end_time - start_time)

        logger.info(f"文档审查完成 - 耗时: {result.review_time}, 问题数: {result.total_issues}")

        return result

    def _review_section(
        self,
        section: DocumentSection,
        rules: List[Rule],
        context: Dict[str, Any]
    ) -> SectionReviewResult:
        """
        审查单个章节

        mode 控制引擎选择（与规则 review_type 无关）:
        - rule_only: 所有规则走规则引擎
        - llm_only:  所有规则走 LLM
        - both:      所有规则走规则引擎 + LLM

        Args:
            section: 文档章节
            rules: 规则列表
            context: 上下文信息

        Returns:
            章节审查结果
        """
        result = SectionReviewResult(
            section_id=section.section_id,
            section_text=section.text
        )

        uses_rules = ReviewMode.uses_rule_engine(self.mode)
        uses_llm = ReviewMode.uses_llm(self.mode)

        # 1. 规则引擎检查 — rule_only / both 模式
        if uses_rules:
            for rule in rules:
                rule_result = safe_execute_rule(
                    rule,
                    section,
                    context,
                    default_result=RuleResult(
                        rule_id=rule.rule_id,
                        rule_name=rule.name,
                        passed=True,
                        severity=rule.severity,
                        message="规则检查失败，默认通过"
                    )
                )
                result.add_rule_result(rule_result)

        # 2. LLM 检查 — llm_only / both 模式
        if uses_llm and section.text.strip():
            llm_results = self._get_llm_section_review(section, rules)
            if llm_results:
                for llm_result in llm_results:
                    result.add_rule_result(llm_result)

        return result

    @llm_retry(retry_on=(ConnectionError, TimeoutError, json.JSONDecodeError, LLMRetryError))
    def _get_llm_section_review(
        self,
        section: DocumentSection,
        rules: List[Rule]
    ) -> Optional[List[RuleResult]]:
        """
        使用 LLM 审查章节

        Args:
            section: 文档章节
            rules: 规则列表

        Returns:
            LLM 检查结果列表
        """
        if not self.prompt_builder:
            return None

        # 检查缓存
        if self.enable_cache:
            cache_key = generate_cache_key("llm_section", section.section_id, section.text[:200])
            from core.cache import get_cache
            cached_result = get_cache().get(cache_key)
            if cached_result is not None:
                logger.debug(f"LLM 章节审查缓存命中: {section.section_id}")
                return cached_result

        # 构建 prompt
        rules_info = [{"name": r.name, "description": r.description} for r in rules]
        prompt = self.prompt_builder.build_section_review_prompt(section.text, rules_info)

        # 调用 LLM
        response = self.llm_client.generate(prompt)
        llm_result = self.parser.parse(response.content)

        if not isinstance(llm_result, dict):
            logger.warning(f"LLM 返回格式错误: {section.section_id}")
            return None

        # 转换为 RuleResult 列表
        results = []
        for issue in llm_result.get("issues", []):
            rule_id = issue.get("rule_id", "llm_generated")
            rule_name = issue.get("rule_name", "LLM 审查")
            severity_str = issue.get("severity", "warning")

            try:
                severity = RuleSeverity(severity_str)
            except ValueError:
                severity = RuleSeverity.WARNING

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
            results.append(rule_result)

        # 存入缓存
        if self.enable_cache:
            from core.cache import get_cache
            get_cache().set(cache_key, results)

        return results

    @llm_retry(retry_on=(ConnectionError, TimeoutError, json.JSONDecodeError, LLMRetryError))
    def _get_llm_document_summary(
        self,
        document: ParsedDocument,
        rules: List[Rule]
    ) -> str:
        """
        使用 LLM 生成文档总结

        Args:
            document: 文档对象
            rules: 规则列表

        Returns:
            文档总结
        """
        if not self.prompt_builder:
            return ""

        # 检查缓存
        if self.enable_cache:
            cache_key = generate_cache_key("llm_summary", document.title, document.raw_text[:500])
            from core.cache import get_cache
            cached_summary = get_cache().get(cache_key)
            if cached_summary is not None:
                logger.debug("LLM 文档总结缓存命中")
                return cached_summary

        # 获取 LLM 规则
        llm_rules = filter_rules_by_review_type(
            rules,
            [ReviewType.LLM, ReviewType.BOTH]
        )

        if not llm_rules:
            return ""

        # 构建 prompt
        rules_info = [{"name": r.name, "description": r.description} for r in llm_rules]
        prompt = self.prompt_builder.build_document_review_prompt(
            document.title,
            truncate_text(document.raw_text, 5000),
            rules_info
        )

        # 调用 LLM
        response = self.llm_client.generate(prompt)
        summary_result = self.parser.parse(response.content)

        if not isinstance(summary_result, dict):
            logger.warning("LLM 文档总结返回格式错误")
            return ""

        summary = summary_result.get("summary", "")

        # 存入缓存
        if self.enable_cache:
            from core.cache import get_cache
            get_cache().set(cache_key, summary)

        return summary

    def clear_cache(self):
        """清空缓存"""
        from core.cache import clear_cache
        clear_cache()
        logger.info("审查执行器缓存已清空")
