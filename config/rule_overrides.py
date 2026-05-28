"""规则覆盖持久化模块。

将运行时对规则属性的修改保存到 config/rule_overrides.json，
启动时加载并 merge 到默认规则上。
"""
import json
import logging
import os
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

OVERRIDES_FILE = os.path.join(os.path.dirname(__file__), "rule_overrides.json")

VALID_OVERRIDE_FIELDS = {"enabled", "severity", "review_type", "phase", "params"}


def load_overrides() -> Dict[str, Dict[str, Any]]:
    """从 JSON 文件加载规则覆盖配置。"""
    if not os.path.exists(OVERRIDES_FILE):
        return {}
    try:
        with open(OVERRIDES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            logger.warning("rule_overrides.json 格式错误，忽略")
            return {}
        return data
    except (json.JSONDecodeError, IOError) as e:
        logger.warning("加载 rule_overrides.json 失败: %s", e)
        return {}


def save_overrides(overrides: Dict[str, Dict[str, Any]]):
    """保存规则覆盖配置到 JSON 文件。"""
    os.makedirs(os.path.dirname(OVERRIDES_FILE), exist_ok=True)
    with open(OVERRIDES_FILE, "w", encoding="utf-8") as f:
        json.dump(overrides, f, ensure_ascii=False, indent=2)
    logger.info("规则覆盖已保存到 %s", OVERRIDES_FILE)


def apply_overrides(rules: List) -> List:
    """将 override 配置 merge 到规则列表上。"""
    overrides = load_overrides()

    if not overrides:
        return rules

    for rule in rules:
        rule_overrides = overrides.get(rule.rule_id)
        if not rule_overrides:
            continue

        for field_name, value in rule_overrides.items():
            if field_name not in VALID_OVERRIDE_FIELDS:
                logger.debug("忽略未知字段 %s.%s", rule.rule_id, field_name)
                continue

            if field_name == "severity":
                from rules.base_rule import RuleSeverity
                try:
                    value = RuleSeverity(value)
                except ValueError:
                    logger.warning("非法 severity 值 %s for %s，跳过", value, rule.rule_id)
                    continue
            elif field_name == "review_type":
                from rules.base_rule import ReviewType
                try:
                    value = ReviewType(value)
                except ValueError:
                    logger.warning("非法 review_type 值 %s for %s，跳过", value, rule.rule_id)
                    continue
            elif field_name == "phase":
                from rules.base_rule import ReviewPhase
                try:
                    value = ReviewPhase(value)
                except ValueError:
                    logger.warning("非法 phase 值 %s for %s，跳过", value, rule.rule_id)
                    continue

            try:
                setattr(rule, field_name, value)
            except AttributeError:
                logger.warning("无法设置字段 %s.%s", rule.rule_id, field_name)

    return rules


def update_rule_override(rule_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """更新单条规则的 override 并保存。只存储被修改的字段。"""
    # 过滤掉非法字段
    filtered = {k: v for k, v in updates.items() if k in VALID_OVERRIDE_FIELDS}
    if not filtered:
        return {"error": "没有有效的更新字段"}

    # 序列化枚举值
    for key in ("severity", "review_type", "phase"):
        if key in filtered and hasattr(filtered[key], "value"):
            filtered[key] = filtered[key].value

    # 序列化 params 中的枚举值
    if "params" in filtered and isinstance(filtered["params"], dict):
        serialized_params = {}
        for pk, pv in filtered["params"].items():
            if isinstance(pv, dict) and "value" in pv:
                serialized_params[pk] = pv
            else:
                serialized_params[pk] = {"value": pv}
        filtered["params"] = serialized_params

    overrides = load_overrides()
    if rule_id not in overrides:
        overrides[rule_id] = {}
    overrides[rule_id].update(filtered)
    save_overrides(overrides)

    return {"ok": True, "rule_id": rule_id, "updated_fields": list(filtered.keys())}
