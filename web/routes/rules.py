"""规则管理页面和 API 路由。"""
import json
import logging
import os
from flask import Blueprint, render_template, request, jsonify, current_app

from rules.base_rule import (
    Rule, RuleSeverity, ReviewType, RuleCategory,
)
from rules.loaders.rule_loader import RuleLoader
from config.rule_overrides import update_rule_override, load_overrides, save_overrides

logger = logging.getLogger(__name__)

bp = Blueprint("rules", __name__)

CUSTOM_SETS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                                "config", "custom_rule_sets.json")

# 规则集显示名称映射
SOURCE_DISPLAY = {
    "common": "通用规则",
    "extension": "扩展规则",
}

# 规则集排序顺序
SOURCE_ORDER = {"common": 0, "extension": 1}

def _load_custom_sets() -> dict:
    """加载自定义规则集定义。"""
    if not os.path.exists(CUSTOM_SETS_FILE):
        return {}
    try:
        with open(CUSTOM_SETS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _save_custom_sets(data: dict):
    """保存自定义规则集定义。"""
    os.makedirs(os.path.dirname(CUSTOM_SETS_FILE), exist_ok=True)
    with open(CUSTOM_SETS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _serialize_rule(rule: Rule) -> dict:
    """将 Rule 对象序列化为 JSON 安全的字典。"""
    # 判断是否为自定义规则（通过 override 创建的）
    overrides = load_overrides()
    is_custom = rule.rule_id in overrides and "name" in overrides[rule.rule_id]

    return {
        "rule_id": rule.rule_id,
        "name": rule.name,
        "description": rule.description,
        "category": rule.category.value,
        "severity": rule.severity.value,
        "enabled": rule.enabled,
        "source": rule.source,
        "review_type": rule.review_type.value,
        "doc_types": [dt.value for dt in rule.doc_types],
        "params": rule.params,
        "custom": is_custom,
        "code": rule.code,
        "logic": rule.logic,
        "standard_ref": rule.standard_ref,
    }


def _group_rules_by_source(rules: list) -> list:
    """按 source 分组规则，返回有序列表。"""
    custom_sets = _load_custom_sets()

    groups = {}
    for rule in rules:
        src = rule.source
        if src not in groups:
            display = custom_sets.get(src, {}).get("display_name") or SOURCE_DISPLAY.get(src, src)
            groups[src] = {
                "source": src,
                "display_name": display,
                "custom": src in custom_sets,
                "rules": [],
            }
        groups[src]["rules"].append(_serialize_rule(rule))

    # 添加空的自定义规则集
    for src, info in custom_sets.items():
        if src not in groups:
            groups[src] = {
                "source": src,
                "display_name": info["display_name"],
                "custom": True,
                "rules": [],
            }

    result = sorted(groups.values(), key=lambda g: SOURCE_ORDER.get(g["source"], 99))

    # 统计
    total = len(rules)
    enabled = sum(1 for r in rules if r.enabled)
    for g in result:
        g["total"] = len(g["rules"])
        g["enabled"] = sum(1 for r in g["rules"] if r["enabled"])

    return result, total, enabled


def _validate_custom_rule_definition(data: dict, require_logic: bool = True):
    logic = data.get("logic", "")
    if require_logic and not str(logic).strip():
        return "检查逻辑不能为空。请写明判定条件、检查重点或通过/不通过标准"
    return None


@bp.route("/")
def index():
    """渲染规则管理页面。"""
    rules = RuleLoader.load_all_rules("default", include_extensions=False)
    groups, total, enabled = _group_rules_by_source(rules)
    return render_template(
        "rules.html",
        active_page="rules",
        groups=groups,
        total=total,
        enabled_count=enabled,
        disabled_count=total - enabled,
        severities=[{"value": s.value, "label": {"error": "错误", "warning": "警告", "info": "信息"}.get(s.value, s.value)} for s in RuleSeverity],
        review_types=[{"value": t.value, "label": {"rule": "规则引擎", "llm": "LLM", "both": "规则+LLM"}.get(t.value, t.value)} for t in ReviewType],
    )


@bp.route("/api/profiles")
def api_profiles():
    """返回所有规则集及规则列表。"""
    rules = RuleLoader.load_all_rules("default", include_extensions=False)
    groups, total, enabled = _group_rules_by_source(rules)
    return jsonify({"groups": groups, "total": total, "enabled": enabled})


@bp.route("/api/rules/<rule_id>")
def api_get_rule(rule_id: str):
    """返回单条规则详情。"""
    rules = RuleLoader.load_all_rules("default", include_extensions=False)
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

    rules = RuleLoader.load_all_rules("default", include_extensions=False)
    existing_rule = next((r for r in rules if r.rule_id == rule_id), None)
    if existing_rule and _serialize_rule(existing_rule).get("custom"):
        if any(field in data for field in ("logic", "description", "standard_ref")):
            validation_error = _validate_custom_rule_definition({
                "logic": data.get("logic", existing_rule.logic),
            })
            if validation_error:
                return jsonify({"error": validation_error}), 400
        data.pop("review_type", None)

    result = update_rule_override(rule_id, data)
    if "error" in result:
        return jsonify(result), 400

    return jsonify(result)


@bp.route("/api/sets", methods=["POST"])
def api_create_set():
    """创建自定义规则集。"""
    data = request.get_json()
    if not data or "source" not in data or "display_name" not in data:
        return jsonify({"error": "需要 source 和 display_name 字段"}), 400

    source = data["source"].strip()
    display_name = data["display_name"].strip()
    if not source or not display_name:
        return jsonify({"error": "source 和 display_name 不能为空"}), 400

    custom_sets = _load_custom_sets()
    if source in custom_sets or source in SOURCE_DISPLAY:
        return jsonify({"error": f"规则集 '{source}' 已存在"}), 400

    custom_sets[source] = {"display_name": display_name}
    _save_custom_sets(custom_sets)

    return jsonify({"ok": True, "source": source, "display_name": display_name})


@bp.route("/api/test-rule", methods=["POST"])
def api_test_rule():
    """用样例文本试审一条规则定义。"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "请求体不能为空"}), 400

    sample_text = data.get("sample_text", "").strip()
    if not sample_text:
        return jsonify({"error": "请先输入试审文本"}), 400

    rule_payload = data.get("rule") or {}
    validation_error = _validate_custom_rule_definition(rule_payload)
    if validation_error:
        return jsonify({"error": validation_error}), 400

    try:
        from models.document import ContentType, DocumentSection
        from rules.base_rule import Rule, RuleCategory, RuleSeverity, ReviewType
        from llm.client import LLMClientFactory
        from config.settings import settings
        from core.executor import ReviewExecutor, ReviewMode

        rule = Rule(
            rule_id=rule_payload.get("rule_id") or "draft_rule",
            name=rule_payload.get("name") or "试审规则",
            description=rule_payload.get("description", ""),
            category=RuleCategory.CUSTOM,
            severity=RuleSeverity(rule_payload.get("severity", "warning")),
            source=rule_payload.get("source", "custom"),
            review_type=ReviewType.LLM,
            logic=rule_payload.get("logic", ""),
            standard_ref=rule_payload.get("standard_ref", ""),
            code=rule_payload.get("code", ""),
        )
        section = DocumentSection("sample", ContentType.PARAGRAPH, sample_text)
        llm_client = LLMClientFactory.create_client(settings.llm_provider)
        executor = ReviewExecutor(
            rule_registry=None,
            llm_client=llm_client,
            mode=ReviewMode.LLM_ONLY,
            enable_cache=False,
        )
        results = executor._get_llm_section_review(section, [rule]) or []
        return jsonify({
            "ok": True,
            "issues": [
                {
                    "rule_id": r.rule_id,
                    "rule_name": r.rule_name,
                    "severity": r.severity.value,
                    "message": r.message,
                    "suggestions": r.suggestions,
                }
                for r in results
            ],
            "passed": len(results) == 0,
        })
    except Exception as e:
        logger.exception("规则试审失败")
        return jsonify({"error": f"规则试审失败: {e}"}), 500


@bp.route("/api/sets/<source>", methods=["DELETE"])
def api_delete_set(source: str):
    """删除自定义规则集（仅限自定义的空规则集）。"""
    custom_sets = _load_custom_sets()
    if source not in custom_sets:
        return jsonify({"error": f"自定义规则集 '{source}' 不存在"}), 404

    # 检查规则集中是否还有规则
    overrides = load_overrides()
    rules_in_set = [rid for rid, ov in overrides.items()
                    if ov.get("source") == source]
    if rules_in_set:
        return jsonify({"error": f"规则集中仍有 {len(rules_in_set)} 条规则，请先删除"}), 400

    del custom_sets[source]
    _save_custom_sets(custom_sets)

    return jsonify({"ok": True, "source": source})


@bp.route("/api/rules", methods=["POST"])
def api_create_rule():
    """创建自定义规则。"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "请求体不能为空"}), 400

    rule_id = data.get("rule_id", "").strip()
    name = data.get("name", "").strip()
    source = data.get("source", "").strip()

    if not rule_id or not name or not source:
        return jsonify({"error": "rule_id, name, source 不能为空"}), 400
    validation_error = _validate_custom_rule_definition(data)
    if validation_error:
        return jsonify({"error": validation_error}), 400

    # 检查 rule_id 唯一性
    existing_rules = RuleLoader.load_all_rules("default", include_extensions=False)
    if any(r.rule_id == rule_id for r in existing_rules):
        return jsonify({"error": f"规则 ID '{rule_id}' 已存在"}), 400

    # 构建默认值
    try:
        severity = RuleSeverity(data.get("severity", "warning"))
        review_type = ReviewType.LLM
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    # 保存为 override（source 字段确保规则归属到对应规则集）
    rule_data = {
        "source": source,
        "name": name,
        "description": data.get("description", ""),
        "category": data.get("category", "custom"),
        "severity": severity.value,
        "review_type": review_type.value,
        "enabled": data.get("enabled", True),
        "code": data.get("code", ""),
        "logic": data.get("logic", ""),
        "standard_ref": data.get("standard_ref", ""),
        "params": data.get("params", {}),
    }

    overrides = load_overrides()
    overrides[rule_id] = rule_data
    save_overrides(overrides)

    return jsonify({"ok": True, "rule_id": rule_id})


@bp.route("/api/rules/<rule_id>", methods=["DELETE"])
def api_delete_rule(rule_id: str):
    """删除自定义规则（仅限通过 API 创建的）。"""
    overrides = load_overrides()
    if rule_id not in overrides:
        return jsonify({"error": f"规则 '{rule_id}' 不是自定义规则，无法删除"}), 404

    del overrides[rule_id]
    save_overrides(overrides)

    return jsonify({"ok": True, "rule_id": rule_id})
