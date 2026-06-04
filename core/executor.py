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
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from openai import APIConnectionError, APITimeoutError, RateLimitError

from models.document import ParsedDocument, DocumentSection, DocumentType
from rules.base_rule import Rule, RuleResult, RuleRegistry, RuleSeverity, ReviewType, ReviewPhase, RuleScope, PHASE_ORDER
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


def _rule_prompt_description(rule: Rule) -> str:
    """把用户维护的规则定义整理为 LLM 可执行的审查说明。"""
    parts = [rule.description or ""]
    if rule.logic:
        parts.append(f"检查逻辑：{rule.logic}")
    if rule.standard_ref:
        parts.append(f"依据：{rule.standard_ref}")
    if rule.code:
        parts.append(f"编号：{rule.code}")
    return "\n".join(part for part in parts if part)


def _rule_prompt_info(rule: Rule) -> dict:
    return {
        "rule_id": rule.rule_id,
        "code": rule.code,
        "name": rule.name,
        "severity": rule.severity.value,
        "description": _rule_prompt_description(rule),
    }


def _normalize_rule_key(value: Any) -> str:
    return str(value or "").strip()


def _build_rule_lookup(rules: List[Rule]) -> Dict[str, Rule]:
    lookup: Dict[str, Rule] = {}
    for rule in rules:
        keys = [rule.rule_id, rule.name, rule.code]
        keys.extend(getattr(rule, "aliases", []) or [])
        for key in keys:
            normalized = _normalize_rule_key(key)
            if normalized:
                lookup.setdefault(normalized, rule)
    return lookup


def _rules_cache_signature(rules: List[Rule]) -> str:
    payload = [
        {
            "id": r.rule_id,
            "name": r.name,
            "review_type": r.review_type.value,
            "description": r.description,
            "logic": r.logic,
            "standard_ref": r.standard_ref,
            "scope": getattr(getattr(r, "scope", RuleScope.ALL), "value", getattr(r, "scope", "all")),
            "target_headings": getattr(r, "target_headings", []),
            "required_elements": getattr(r, "required_elements", []),
            "params": getattr(r, "params", {}),
        }
        for r in rules
    ]
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


SECTION_SCOPE_KEYWORDS = {
    RuleScope.COVER: ("封面", "文件名称", "文件编号", "产品名称", "型号", "密级"),
    RuleScope.SIGNATURE: ("签署", "签字", "签署页", "编制", "校对", "审核", "批准", "会签", "审签"),
    RuleScope.PREFACE: ("前言", "概述", "简介", "总则", "引言"),
}


def _section_head_text(section: DocumentSection) -> str:
    heading_text = str(section.metadata.get("heading_text", "") or "")
    section_text = section.text.strip()
    head = "\n".join(section_text.splitlines()[:2])
    return f"{heading_text}\n{head}"


def _has_scope_keyword(section: DocumentSection, scope: RuleScope) -> bool:
    text = _section_head_text(section)
    return any(keyword in text for keyword in SECTION_SCOPE_KEYWORDS.get(scope, ()))


def _section_scope(section: DocumentSection, context: Dict[str, Any]) -> RuleScope:
    metadata_region = section.metadata.get("region")
    if metadata_region:
        try:
            return RuleScope(metadata_region)
        except ValueError:
            pass
    index = int(context.get("section_index", 0) or 0)
    for scope in (RuleScope.COVER, RuleScope.SIGNATURE, RuleScope.PREFACE):
        if _has_scope_keyword(section, scope):
            return scope
    if index == 0:
        return RuleScope.COVER
    return RuleScope.BODY


def _rule_target_keywords(rule: Rule) -> List[str]:
    return [str(item).strip() for item in getattr(rule, "target_headings", []) if str(item).strip()]


def _section_matches_rule_targets(rule: Rule, section: DocumentSection) -> bool:
    keywords = _rule_target_keywords(rule)
    if not keywords:
        return True
    haystack = f"{section.metadata.get('heading_text', '')}\n{section.text}"
    return any(keyword in haystack for keyword in keywords)


def _rule_applies_to_section(rule: Rule, section: DocumentSection, context: Dict[str, Any]) -> bool:
    scope = getattr(rule, "scope", RuleScope.ALL)
    if isinstance(scope, str):
        try:
            scope = RuleScope(scope)
        except ValueError:
            scope = RuleScope.ALL
    if scope in (RuleScope.COVER, RuleScope.SIGNATURE, RuleScope.PREFACE, RuleScope.BODY):
        if _section_scope(section, context) != scope:
            return False
    if not _section_matches_rule_targets(rule, section):
        return False
    matched_rule_ids = context.get("matched_rule_ids")
    if isinstance(matched_rule_ids, set) and _rule_target_keywords(rule):
        matched_rule_ids.add(rule.rule_id)
    return True


def _missing_required_elements(rule: Rule, section: DocumentSection) -> List[str]:
    elements = [str(item).strip() for item in getattr(rule, "required_elements", []) if str(item).strip()]
    if not elements:
        return []
    return [element for element in elements if element not in section.text]


def _param_value(params: Dict[str, Any], key: str, default: Any = None) -> Any:
    value = params.get(key, default)
    if isinstance(value, dict) and "value" in value:
        return value.get("value", default)
    return value


def _normalize_list_param(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in re.split(r"[,，;；\n]+", value) if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _table_cells(section: DocumentSection) -> List[Dict[str, Any]]:
    cells = section.metadata.get("table_cells", [])
    return cells if isinstance(cells, list) else []


def _candidate_table_values(cells: List[Dict[str, Any]], label_cell: Dict[str, Any]) -> List[str]:
    row = int(label_cell.get("row", -1))
    col = int(label_cell.get("col", -1))
    values = []
    same_row = sorted(
        [cell for cell in cells if int(cell.get("row", -1)) == row and int(cell.get("col", -1)) > col],
        key=lambda item: int(item.get("col", 0)),
    )
    below = sorted(
        [cell for cell in cells if int(cell.get("col", -1)) == col and int(cell.get("row", -1)) > row],
        key=lambda item: int(item.get("row", 0)),
    )
    for cell in [*same_row, *below]:
        text = str(cell.get("text", "")).strip()
        if text:
            values.append(text)
    return values


def _same_cell_table_values(text: str, field_labels: List[str]) -> List[str]:
    values = []
    for label in field_labels:
        if label not in text:
            continue
        remainder = text.replace(label, "", 1)
        remainder = re.sub(r"^[\s:：\-—_]+", "", remainder).strip()
        if remainder:
            values.append(remainder)
    return values


def _run_table_field_regex_check(rule: Rule, section: DocumentSection) -> Optional[RuleResult]:
    params = getattr(rule, "params", {}) or {}
    check_type = str(_param_value(params, "check_type", "") or "").strip()
    if check_type != "table_field_regex":
        return None

    field_labels = _normalize_list_param(_param_value(params, "field_labels", []))
    pattern_text = str(_param_value(params, "pattern", "") or "").strip()
    if not field_labels or not pattern_text:
        return RuleResult(
            rule_id=rule.rule_id,
            rule_name=rule.name,
            passed=False,
            severity=rule.severity,
            message="表格字段正则检查参数不完整：需要 field_labels 和 pattern",
            section_id=section.section_id,
            suggestions=["请在规则参数中配置字段名 field_labels 和格式正则 pattern"],
            rule_source="RULE",
            rule_reference=rule.standard_ref,
        )

    try:
        pattern = re.compile(pattern_text)
    except re.error as exc:
        return RuleResult(
            rule_id=rule.rule_id,
            rule_name=rule.name,
            passed=False,
            severity=rule.severity,
            message=f"表格字段正则表达式无效: {exc}",
            section_id=section.section_id,
            suggestions=["请检查规则参数 pattern 的正则表达式写法"],
            rule_source="RULE",
            rule_reference=rule.standard_ref,
        )

    cells = _table_cells(section)
    if not cells:
        return RuleResult(
            rule_id=rule.rule_id,
            rule_name=rule.name,
            passed=False,
            severity=rule.severity,
            message="未在目标范围内找到可定位的表格单元格",
            section_id=section.section_id,
            suggestions=["请确认规则审查范围是否设置为封面，且目标字段位于 Word 表格中"],
            rule_source="RULE",
            rule_reference=rule.standard_ref,
        )

    matched_labels = []
    checked_values = []
    for cell in cells:
        text = str(cell.get("text", "")).strip()
        if not text:
            continue
        if any(label in text for label in field_labels):
            matched_labels.append(text)
            values = [*_same_cell_table_values(text, field_labels), *_candidate_table_values(cells, cell)]
            checked_values.extend(values)
            for value in values:
                normalized_value = re.sub(r"\s+", "", value)
                if pattern.fullmatch(normalized_value):
                    return RuleResult(
                        rule_id=rule.rule_id,
                        rule_name=rule.name,
                        passed=True,
                        severity=rule.severity,
                        message=f"字段“{text}”值“{value}”符合格式要求",
                        section_id=section.section_id,
                        details={"field": text, "value": value, "pattern": pattern_text},
                        rule_source="RULE",
                        rule_reference=rule.standard_ref,
                    )

    if not matched_labels:
        return RuleResult(
            rule_id=rule.rule_id,
            rule_name=rule.name,
            passed=False,
            severity=rule.severity,
            message=f"未找到目标表格字段: {'、'.join(field_labels)}",
            section_id=section.section_id,
            suggestions=[f"请在封面表格中补充字段: {label}" for label in field_labels],
            rule_source="RULE",
            rule_reference=rule.standard_ref,
        )

    return RuleResult(
        rule_id=rule.rule_id,
        rule_name=rule.name,
        passed=False,
        severity=rule.severity,
        message=f"字段“{' / '.join(matched_labels)}”对应值不符合格式要求，期望值以 -AB 结尾，例如 123-AB、POI-AB、XXX-AB",
        section_id=section.section_id,
        suggestions=["请将阶段标识填写为以 -AB 结尾的格式，例如 123-AB、POI-AB、XXX-AB"],
        details={"fields": matched_labels, "checked_values": checked_values, "pattern": pattern_text},
        rule_source="RULE",
        rule_reference=rule.standard_ref,
    )


def _run_configured_rule_check(rule: Rule, section: DocumentSection) -> Optional[RuleResult]:
    return _run_table_field_regex_check(rule, section)


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
        enable_domain_knowledge: bool = False
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
        self.enable_cot = enable_cot if enable_cot is not None else (prompt_style == PromptStyle.COT)
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
        context["matched_rule_ids"] = set()

        logger.info(f"开始审查文档: {document.title}, 共 {len(document.sections)} 个章节, {len(rules)} 条规则")

        # 初始化结果
        result = DocumentReviewResult(
            document_path=document.file_path,
            document_title=document.title
        )

        # 逐个审查章节
        total_sections = len(document.sections)
        for idx, section in enumerate(document.sections):
            pause_callback = context.get("pause_callback")
            if callable(pause_callback):
                pause_callback()
            logger.info(f"审查章节 {idx + 1}/{total_sections}: {section.section_id}")
            section_context = dict(context)
            section_context["section_index"] = idx
            section_context["total_sections"] = total_sections
            section_result = self._review_section(section, rules, section_context)
            result.add_section_result(section_result)
            progress_callback = context.get("progress_callback")
            if callable(progress_callback):
                progress_callback(idx + 1, total_sections)

        missing_target_result = self._build_missing_target_section_result(rules, context["matched_rule_ids"])
        if missing_target_result:
            result.add_section_result(missing_target_result)

        # LLM 文档总结会额外增加一次网络调用，默认用本地统计生成简短总结。
        if ReviewMode.uses_llm(self.mode) and context.get("llm_summary_enabled", False):
            pause_callback = context.get("pause_callback")
            if callable(pause_callback):
                pause_callback()
            logger.info("生成文档审查总结")
            result.summary = self._get_llm_document_summary(document, rules)
        else:
            result.summary = self._build_local_summary(result)

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

        mode 控制可用引擎，规则自身的 review_type 控制该规则走哪个引擎：
        - rule:      仅规则引擎
        - llm:       仅 LLM
        - both:      规则引擎 + LLM

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
        scoped_rules = [r for r in rules if _rule_applies_to_section(r, section, context)]
        rule_check_rules = [r for r in scoped_rules if should_use_rule_check(r)]
        llm_check_rules = [r for r in scoped_rules if should_use_llm_check(r)]

        # 1. 规则引擎检查
        if uses_rules:
            for rule in rule_check_rules:
                rule_result = _run_configured_rule_check(rule, section)
                if rule_result is None:
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

        llm_rules_after_element_check = []
        for rule in llm_check_rules:
            missing_elements = _missing_required_elements(rule, section)
            if missing_elements:
                result.add_rule_result(RuleResult(
                    rule_id=rule.rule_id,
                    rule_name=rule.name,
                    passed=False,
                    severity=rule.severity,
                    message=f"目标章节缺少必需要素: {', '.join(missing_elements)}",
                    section_id=section.section_id,
                    suggestions=[f"请在目标章节补充要素: {element}" for element in missing_elements],
                    rule_source="RULE",
                    rule_reference=rule.standard_ref,
                ))
            else:
                llm_rules_after_element_check.append(rule)

        # 2. LLM 检查
        if uses_llm and llm_rules_after_element_check and section.text.strip():
            try:
                llm_results = self._get_llm_section_review(section, llm_rules_after_element_check)
            except Exception as e:
                logger.warning("LLM 章节审查失败，已降级为提示并继续任务: %s - %s", section.section_id, str(e))
                llm_results = [
                    RuleResult(
                        rule_id=rule.rule_id,
                        rule_name=rule.name,
                        passed=False,
                        severity=RuleSeverity.WARNING,
                        message=f"LLM审查调用失败，未能完成该规则检查：{str(e)}",
                        section_id=section.section_id,
                        suggestions=["请检查大模型服务/API Key/网络连接后重新审查该文档"],
                        rule_source="LLM",
                        rule_reference=rule.standard_ref,
                    )
                    for rule in llm_rules_after_element_check
                ]
            if llm_results:
                for llm_result in llm_results:
                    result.add_rule_result(llm_result)

        return result

    def _build_missing_target_section_result(
        self,
        rules: List[Rule],
        matched_rule_ids: set,
    ) -> Optional[SectionReviewResult]:
        missing_rules = [
            rule for rule in rules
            if rule.enabled and _rule_target_keywords(rule) and rule.rule_id not in matched_rule_ids
        ]
        if not missing_rules:
            return None
        result = SectionReviewResult(section_id="document_structure", section_text="文档结构定位")
        for rule in missing_rules:
            keywords = "、".join(_rule_target_keywords(rule))
            result.add_rule_result(RuleResult(
                rule_id=rule.rule_id,
                rule_name=rule.name,
                passed=False,
                severity=rule.severity,
                message=f"未找到规则要求的目标章节: {keywords}",
                section_id="document_structure",
                suggestions=[f"请补充或调整章节标题，使其包含以下关键词之一: {keywords}"],
                rule_source="RULE",
                rule_reference=rule.standard_ref,
            ))
        return result

    @llm_retry(retry_on=(ConnectionError, TimeoutError, json.JSONDecodeError, LLMRetryError, APIConnectionError, APITimeoutError, RateLimitError))
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
            cache_key = generate_cache_key("llm_section", section.text, _rules_cache_signature(rules))
            from core.cache import get_cache
            cached_result = get_cache().get(cache_key)
            if cached_result is not None:
                logger.debug(f"LLM 章节审查缓存命中: {section.section_id}")
                return cached_result

        # 构建 prompt
        rules_info = [_rule_prompt_info(r) for r in rules]
        prompt = self.prompt_builder.build_section_review_prompt(section.text, rules_info)

        # 调用 LLM
        response = self.llm_client.generate(prompt, system_prompt=self.prompt_builder.get_system_prompt())
        llm_result = self.parser.parse(response.content)

        if not isinstance(llm_result, dict):
            logger.warning(f"LLM 返回格式错误: {section.section_id}")
            return None

        # 转换为 RuleResult 列表
        results = []
        rule_lookup = _build_rule_lookup(rules)
        for issue in llm_result.get("issues", []):
            rule_id = _normalize_rule_key(issue.get("rule_id", "llm_generated"))
            rule_name = _normalize_rule_key(issue.get("rule_name", "LLM 审查"))
            rule_code = _normalize_rule_key(issue.get("rule_code") or issue.get("code"))
            matched_rule = (
                rule_lookup.get(rule_id)
                or rule_lookup.get(rule_name)
                or rule_lookup.get(rule_code)
            )
            if not matched_rule:
                logger.warning("LLM 返回了未在本次启用规则中的问题，已忽略: %s/%s", rule_id, rule_name)
                continue
            rule_id = matched_rule.rule_id
            rule_name = matched_rule.name
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
                rule_source="LLM",
                rule_reference=matched_rule.standard_ref if matched_rule else None,
            )
            results.append(rule_result)

        # 存入缓存
        if self.enable_cache:
            from core.cache import get_cache
            get_cache().set(cache_key, results)

        return results

    @llm_retry(retry_on=(ConnectionError, TimeoutError, json.JSONDecodeError, LLMRetryError, APIConnectionError, APITimeoutError, RateLimitError))
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
            cache_key = generate_cache_key("llm_summary", document.title, document.raw_text[:500], _rules_cache_signature(rules))
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
        rules_info = [_rule_prompt_info(r) for r in llm_rules]
        prompt = self.prompt_builder.build_document_review_prompt(
            document.title,
            truncate_text(document.raw_text, 5000),
            rules_info
        )

        # 调用 LLM
        response = self.llm_client.generate(prompt, system_prompt=self.prompt_builder.get_system_prompt())
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

    def _build_local_summary(self, result: DocumentReviewResult) -> str:
        """根据已完成的规则结果生成轻量总结，避免额外 LLM 请求。"""
        if result.total_issues == 0:
            return "审查完成，未发现不符合项。"
        return (
            f"审查完成，共发现 {result.total_issues} 个问题，"
            f"其中错误 {result.errors} 个、警告 {result.warnings} 个。"
        )

    def clear_cache(self):
        """清空缓存"""
        from core.cache import clear_cache
        clear_cache()
        logger.info("审查执行器缓存已清空")
