"""规则管理页面和 API 路由。"""
from flask import Blueprint, render_template, request, jsonify, current_app

from rules.base_rule import (
    Rule, RuleSeverity, ReviewType, ReviewPhase, PHASE_ORDER,
    PHASE_DISPLAY_NAMES, RuleCategory,
)
from rules.loaders.rule_loader import RuleLoader
from config.rule_overrides import update_rule_override

bp = Blueprint("rules", __name__)

# 规则集显示名称映射
SOURCE_DISPLAY = {
    "common": "通用规则",
    "aviation": "航空作动系统",
    "extension": "扩展规则",
}

# 规则集排序顺序
SOURCE_ORDER = {"common": 0, "aviation": 1, "extension": 2}


def _serialize_rule(rule: Rule) -> dict:
    """将 Rule 对象序列化为 JSON 安全的字典。"""
    return {
        "rule_id": rule.rule_id,
        "name": rule.name,
        "description": rule.description,
        "category": rule.category.value,
        "severity": rule.severity.value,
        "enabled": rule.enabled,
        "source": rule.source,
        "review_type": rule.review_type.value,
        "phase": rule.phase.value,
        "phase_display": PHASE_DISPLAY_NAMES.get(rule.phase, rule.phase.value),
        "doc_types": [dt.value for dt in rule.doc_types],
        "params": rule.params,
    }


def _group_rules_by_source(rules: list) -> list:
    """按 source 分组规则，返回有序列表。"""
    groups = {}
    for rule in rules:
        src = rule.source
        if src not in groups:
            groups[src] = {
                "source": src,
                "display_name": SOURCE_DISPLAY.get(src, src),
                "rules": [],
            }
        groups[src]["rules"].append(_serialize_rule(rule))

    result = sorted(groups.values(), key=lambda g: SOURCE_ORDER.get(g["source"], 99))

    # 统计
    total = len(rules)
    enabled = sum(1 for r in rules if r.enabled)
    for g in result:
        g["total"] = len(g["rules"])
        g["enabled"] = sum(1 for r in g["rules"] if r["enabled"])

    return result, total, enabled


@bp.route("/")
def index():
    """渲染规则管理页面。"""
    rules = RuleLoader.load_all_rules("aviation", include_extensions=False)
    groups, total, enabled = _group_rules_by_source(rules)
    return render_template(
        "rules.html",
        active_page="rules",
        groups=groups,
        total=total,
        enabled_count=enabled,
        disabled_count=total - enabled,
        phases=[{"value": p.value, "label": PHASE_DISPLAY_NAMES[p]} for p in PHASE_ORDER],
        severities=[{"value": s.value, "label": {"error": "错误", "warning": "警告", "info": "信息"}.get(s.value, s.value)} for s in RuleSeverity],
        review_types=[{"value": t.value, "label": {"rule": "规则引擎", "llm": "LLM", "both": "规则+LLM"}.get(t.value, t.value)} for t in ReviewType],
    )


@bp.route("/api/profiles")
def api_profiles():
    """返回所有规则集及规则列表。"""
    rules = RuleLoader.load_all_rules("aviation", include_extensions=False)
    groups, total, enabled = _group_rules_by_source(rules)
    return jsonify({"groups": groups, "total": total, "enabled": enabled})


@bp.route("/api/rules/<rule_id>")
def api_get_rule(rule_id: str):
    """返回单条规则详情。"""
    rules = RuleLoader.load_all_rules("aviation", include_extensions=False)
    rule = next((r for r in rules if r.rule_id == rule_id), None)
    if not rule:
        return jsonify({"error": f"规则 {rule_id} 不存在"}), 404
    return jsonify(_serialize_rule(rule))


@bp.route("/api/rules/<rule_id>", methods=["PUT"])
def api_update_rule(rule_id: str):
    """更新规则属性。"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "请求体不能为空"}), 400

    # 验证枚举值
    if "severity" in data:
        try:
            RuleSeverity(data["severity"])
        except ValueError:
            return jsonify({"error": f"非法的 severity 值: {data['severity']}"}), 400

    if "review_type" in data:
        try:
            ReviewType(data["review_type"])
        except ValueError:
            return jsonify({"error": f"非法的 review_type 值: {data['review_type']}"}), 400

    if "phase" in data:
        try:
            ReviewPhase(data["phase"])
        except ValueError:
            return jsonify({"error": f"非法的 phase 值: {data['phase']}"}), 400

    result = update_rule_override(rule_id, data)
    if "error" in result:
        return jsonify(result), 400

    return jsonify(result)
