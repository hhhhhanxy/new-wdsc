"""
核心工具模块 - 提供统一的类型处理和辅助函数
"""
from rules.base_rule import Rule, ReviewType
from typing import List, Callable, Any
import logging

logger = logging.getLogger(__name__)


def get_review_type(rule: Rule) -> ReviewType:
    """
    安全获取规则的 ReviewType

    Args:
        rule: 规则对象

    Returns:
        ReviewType 枚举值
    """
    if isinstance(rule.review_type, ReviewType):
        return rule.review_type

    if isinstance(rule.review_type, str):
        try:
            return ReviewType(rule.review_type.lower())
        except ValueError:
            logger.warning(f"规则 {rule.rule_id} 的 review_type 值无效: {rule.review_type}")
            return ReviewType.RULE

    # 默认返回 RULE
    return ReviewType.RULE


def filter_rules_by_review_type(
    rules: List[Rule],
    review_types: List[ReviewType]
) -> List[Rule]:
    """
    根据审查类型过滤规则

    Args:
        rules: 规则列表
        review_types: 要包含的审查类型列表

    Returns:
        过滤后的规则列表
    """
    target_types = set(review_types)
    filtered = []

    for rule in rules:
        try:
            rule_type = get_review_type(rule)
            if rule_type in target_types:
                filtered.append(rule)
        except Exception as e:
            logger.warning(f"过滤规则 {rule.rule_id} 时出错: {str(e)}")

    return filtered


def should_use_rule_check(rule: Rule) -> bool:
    """
    判断规则是否应该使用规则引擎检查

    Args:
        rule: 规则对象

    Returns:
        是否应该使用规则检查
    """
    review_type = get_review_type(rule)
    return review_type in [ReviewType.RULE, ReviewType.BOTH]


def should_use_llm_check(rule: Rule) -> bool:
    """
    判断规则是否应该使用 LLM 检查

    Args:
        rule: 规则对象

    Returns:
        是否应该使用 LLM 检查
    """
    review_type = get_review_type(rule)
    return review_type in [ReviewType.LLM, ReviewType.BOTH]


def safe_execute_rule(
    rule: Rule,
    section,
    context: dict,
    default_result=None
) -> Any:
    """
    安全执行规则检查

    Args:
        rule: 规则对象
        section: 文档章节
        context: 上下文
        default_result: 失败时的默认返回值

    Returns:
        规则检查结果或默认值
    """
    try:
        return rule.check(section, context)
    except Exception as e:
        logger.error(f"执行规则 {rule.rule_id} 时出错: {str(e)}")
        return default_result


def chunk_text(text: str, chunk_size: int, overlap: int = 100) -> List[str]:
    """
    将文本分块，支持重叠

    Args:
        text: 要分块的文本
        chunk_size: 块大小
        overlap: 重叠大小

    Returns:
        文本块列表
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)

        # 移动起始位置，考虑重叠
        start = end - overlap if end < len(text) else len(text)

    return chunks


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    截断文本到指定长度

    Args:
        text: 要截断的文本
        max_length: 最大长度
        suffix: 截断后缀

    Returns:
        截断后的文本
    """
    if len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix
