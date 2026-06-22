"""规则管理页面和 API 路由。"""
import json
import logging
import os
import re
import uuid
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from flask import Blueprint, render_template, request, jsonify, current_app, send_file

from rules.base_rule import (
    Rule, RuleSeverity, ReviewType, RuleCategory, RuleScope,
)
from rules.loaders.rule_loader import RuleLoader
from config.rule_overrides import update_rule_override, load_overrides, save_overrides
from rules.rule_importer import (
    RuleImportError, build_issue_workbook, parse_rule_workbook, validate_import_rows,
)
from web.time_utils import beijing_now_str

logger = logging.getLogger(__name__)

bp = Blueprint("rules", __name__)

CUSTOM_SETS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                                "config", "custom_rule_sets.json")
RULE_IMPORT_TEMPLATE = Path(__file__).resolve().parents[2] / "web" / "static" / "files" / "审查规则导入模板.xlsx"
RULE_IMPORT_BATCHES_FILE = Path(__file__).resolve().parents[2] / "config" / "rule_import_batches.json"

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


def _load_import_batches() -> list[dict]:
    if not RULE_IMPORT_BATCHES_FILE.exists():
        return []
    try:
        data = json.loads(RULE_IMPORT_BATCHES_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_import_batches(batches: list[dict]):
    RULE_IMPORT_BATCHES_FILE.parent.mkdir(parents=True, exist_ok=True)
    RULE_IMPORT_BATCHES_FILE.write_text(
        json.dumps(batches, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


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
        "aliases": rule.aliases,
        "scope": rule.scope.value if hasattr(rule.scope, "value") else str(rule.scope or "all"),
        "target_headings": rule.target_headings,
        "required_elements": rule.required_elements,
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
    review_type = data.get("review_type")
    params = _normalize_rule_params(data.get("params") or {})
    data["params"] = params
    if review_type in ("rule", "both") and params.get("check_type") == "table_field_regex":
        labels = _normalize_list(params.get("field_labels"))
        pattern = str(params.get("pattern", "") or "").strip()
        if not labels:
            return "规则引擎检查需要填写字段名称"
        if not pattern:
            return "规则引擎检查需要填写匹配格式"
        try:
            re.compile(pattern)
        except re.error as exc:
            return f"匹配格式不是有效正则表达式: {exc}"
    return None


def _plain_param_value(value):
    if isinstance(value, dict) and "value" in value:
        return value.get("value")
    return value


def _escape_regex_literal(value: str) -> str:
    return re.sub(r"([.*+?^${}()|[\]\\])", r"\\\1", str(value or ""))


def _build_match_pattern(match_mode: str, match_value: str) -> str:
    escaped = _escape_regex_literal(str(match_value or "").strip())
    if not escaped:
        return ""
    if match_mode == "starts_with":
        return f"^{escaped}.+"
    if match_mode == "ends_with":
        return f"^.+{escaped}$"
    if match_mode == "contains":
        return f"^.*{escaped}.*$"
    if match_mode == "equals":
        return f"^{escaped}$"
    return escaped


def _normalize_rule_params(params: dict) -> dict:
    if not isinstance(params, dict):
        return {}
    normalized = {key: _plain_param_value(value) for key, value in params.items()}
    if normalized.get("check_type") == "table_field_regex":
        normalized["field_labels"] = _normalize_list(normalized.get("field_labels"))
        match_mode = str(normalized.get("match_mode", "") or "").strip()
        match_value = str(normalized.get("match_value", "") or "").strip()
        if match_mode and match_value:
            normalized["pattern"] = _build_match_pattern(match_mode, match_value)
    return normalized


def _normalize_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        raw_items = value
    else:
        raw_items = re.split(r"[,，;；\n]+", str(value))
    return [str(item).strip() for item in raw_items if str(item).strip()]


def _make_rule_id(data: dict, existing_ids: set) -> str:
    """为用户创建的规则生成内部唯一 ID，不暴露给用户填写。"""
    base_text = str(data.get("code") or data.get("name") or "").strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "_", base_text).strip("_")
    if not slug:
        slug = f"rule_{uuid.uuid4().hex[:8]}"
    if not slug.startswith("rule_"):
        slug = f"rule_{slug}"

    candidate = slug
    counter = 2
    while candidate in existing_ids:
        candidate = f"{slug}_{counter}"
        counter += 1
    return candidate


def _make_copied_rule_id(source_rule_id: str, target_source: str, existing_ids: set) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", f"rule_{target_source}_{source_rule_id}".lower()).strip("_")
    if not base:
        base = f"rule_{target_source}_{uuid.uuid4().hex[:8]}"
    candidate = base
    counter = 2
    while candidate in existing_ids:
        candidate = f"{base}_{counter}"
        counter += 1
    return candidate


def _rule_set_exists(source: str) -> bool:
    if source in SOURCE_DISPLAY or source in _load_custom_sets():
        return True
    return any(rule.source == source for rule in RuleLoader.load_all_rules("default", include_extensions=False))


def _build_custom_rule_data(payload: dict) -> dict:
    params = _normalize_rule_params(payload.get("params") or {})
    return {
        "source": payload["source"],
        "name": payload["name"].strip(),
        "description": payload.get("description", "").strip(),
        "category": "custom",
        "severity": RuleSeverity(payload.get("severity", "warning")).value,
        "review_type": ReviewType(payload.get("review_type", "llm")).value,
        "enabled": bool(payload.get("enabled", True)),
        "code": payload["code"].strip(),
        "logic": payload.get("logic", "").strip(),
        "standard_ref": payload.get("standard_ref", "").strip(),
        "aliases": [value for value in (payload.get("code", "").strip(), payload.get("name", "").strip()) if value],
        "params": params,
        "scope": RuleScope(payload.get("scope", "all")).value,
        "target_headings": _normalize_list(payload.get("target_headings")),
        "required_elements": _normalize_list(payload.get("required_elements")),
    }


def _copied_rule_data(rule: dict, target_source: str) -> dict:
    params = _normalize_rule_params(rule.get("params") or {})
    code = str(rule.get("code") or rule.get("rule_id") or "").strip()
    name = str(rule.get("name") or rule.get("rule_id") or "").strip()
    aliases = rule.get("aliases") or []
    merged_aliases = list(dict.fromkeys([value for value in [*aliases, code, name] if value]))
    return {
        "source": target_source,
        "name": name,
        "description": str(rule.get("description") or "").strip(),
        "category": "custom",
        "severity": RuleSeverity(rule.get("severity", "warning")).value,
        "review_type": ReviewType(rule.get("review_type", "llm")).value,
        "enabled": bool(rule.get("enabled", True)),
        "code": code,
        "logic": str(rule.get("logic") or "").strip(),
        "standard_ref": str(rule.get("standard_ref") or "").strip(),
        "aliases": merged_aliases,
        "params": params,
        "scope": RuleScope(rule.get("scope", "all")).value,
        "target_headings": _normalize_list(rule.get("target_headings")),
        "required_elements": _normalize_list(rule.get("required_elements")),
    }


def _existing_rules_by_code() -> dict[str, dict]:
    result = {}
    for rule in RuleLoader.load_all_rules("default", include_extensions=False):
        code = (rule.code or "").strip()
        if not code:
            continue
        serialized = _serialize_rule(rule)
        serialized["rule_id"] = rule.rule_id
        result[code.lower()] = serialized
    return result


def _prepare_rule_import(source: str):
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        raise RuleImportError("请选择需要导入的 Excel 文件")
    if not uploaded.filename.lower().endswith(".xlsx"):
        raise RuleImportError("仅支持 .xlsx 格式的 Excel 文件")
    file_bytes = uploaded.read()
    if not file_bytes:
        raise RuleImportError("上传的 Excel 文件为空")
    if len(file_bytes) > 10 * 1024 * 1024:
        raise RuleImportError("Excel 文件不能超过 10MB")
    rows = parse_rule_workbook(file_bytes)
    if not rows:
        raise RuleImportError("Excel 中没有可导入的规则")
    if len(rows) > 1000:
        raise RuleImportError("单次最多导入 1000 条规则")
    duplicate_mode = request.form.get("duplicate_mode", "reject")
    if duplicate_mode not in {"reject", "skip", "update"}:
        raise RuleImportError("重复规则处理方式无效")
    rows = validate_import_rows(
        rows,
        source,
        _existing_rules_by_code(),
        _validate_custom_rule_definition,
        duplicate_mode=duplicate_mode,
    )
    return uploaded.filename, duplicate_mode, rows


def _import_preview(rows: list) -> dict:
    row_results = [row.to_dict() for row in rows]
    error_count = sum(1 for row in rows if row.errors)
    warning_count = sum(1 for row in rows if row.warnings)
    create_count = sum(1 for row in rows if not row.errors and row.action == "create")
    update_count = sum(1 for row in rows if not row.errors and row.action == "update")
    skip_count = sum(1 for row in rows if not row.errors and row.action == "skip")
    return {
        "ok": error_count == 0,
        "total": len(rows),
        "valid_count": create_count + update_count,
        "create_count": create_count,
        "update_count": update_count,
        "skip_count": skip_count,
        "warning_count": warning_count,
        "error_count": error_count,
        "rows": row_results,
    }


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
    if "scope" in data:
        try:
            RuleScope(data["scope"])
        except ValueError:
            return jsonify({"error": f"非法的 scope 值: {data['scope']}"}), 400

    rules = RuleLoader.load_all_rules("default", include_extensions=False)
    existing_rule = next((r for r in rules if r.rule_id == rule_id), None)
    if existing_rule and _serialize_rule(existing_rule).get("custom"):
        if "name" in data and not str(data.get("name", "")).strip():
            return jsonify({"error": "规则名称不能为空"}), 400
        if any(field in data for field in ("logic", "description", "standard_ref", "review_type", "params")):
            validation_payload = {
                "logic": data.get("logic", existing_rule.logic),
                "review_type": data.get("review_type", existing_rule.review_type.value),
                "params": data.get("params", existing_rule.params),
            }
            validation_error = _validate_custom_rule_definition(validation_payload)
            if validation_error:
                return jsonify({"error": validation_error}), 400
            if "params" in data:
                data["params"] = validation_payload["params"]
    else:
        data.pop("name", None)
        data.pop("description", None)

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


@bp.route("/api/sets/<source>/copy", methods=["POST"])
def api_copy_set(source: str):
    """复制一个规则集为新的自定义规则集。"""
    rules = RuleLoader.load_all_rules("default", include_extensions=False)
    groups, _, _ = _group_rules_by_source(rules)
    source_group = next((g for g in groups if g["source"] == source), None)
    if not source_group:
        return jsonify({"error": f"规则集 '{source}' 不存在"}), 404

    data = request.get_json() or {}
    target_source = str(data.get("target_source") or "").strip()
    display_name = str(data.get("display_name") or "").strip()
    if not target_source or not display_name:
        return jsonify({"error": "需要填写新规则集标识和显示名称"}), 400
    if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]{1,40}", target_source):
        return jsonify({"error": "规则集标识需以字母开头，仅包含字母、数字和下划线，长度 2-41"}), 400

    custom_sets = _load_custom_sets()
    if target_source in custom_sets or target_source in SOURCE_DISPLAY or any(g["source"] == target_source for g in groups):
        return jsonify({"error": f"规则集 '{target_source}' 已存在"}), 400

    overrides = load_overrides()
    existing_ids = {rule.rule_id for rule in rules} | set(overrides)
    copied_count = 0
    for rule in source_group.get("rules", []):
        new_rule_id = _make_copied_rule_id(rule.get("rule_id", ""), target_source, existing_ids)
        existing_ids.add(new_rule_id)
        overrides[new_rule_id] = _copied_rule_data(rule, target_source)
        copied_count += 1

    custom_sets[target_source] = {
        "display_name": display_name,
        "copied_from": source,
        "copied_at": beijing_now_str(),
    }
    _save_custom_sets(custom_sets)
    save_overrides(overrides)

    return jsonify({
        "ok": True,
        "source": target_source,
        "display_name": display_name,
        "copied_from": source,
        "copied_count": copied_count,
    })


@bp.route("/api/sets/<source>/export")
def api_export_set(source: str):
    """导出规则集 JSON 包。"""
    rules = RuleLoader.load_all_rules("default", include_extensions=False)
    groups, _, _ = _group_rules_by_source(rules)
    group = next((g for g in groups if g["source"] == source), None)
    if not group:
        return jsonify({"error": f"规则集 '{source}' 不存在"}), 404
    payload = {
        "exported_at": beijing_now_str(),
        "source": group["source"],
        "display_name": group["display_name"],
        "custom": group["custom"],
        "total": group["total"],
        "enabled": group["enabled"],
        "rules": group["rules"],
    }
    filename = f"{source}_rules_export.json"
    return send_file(
        BytesIO(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")),
        as_attachment=True,
        download_name=filename,
        mimetype="application/json",
    )


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
            rule_id="draft_rule",
            name=rule_payload.get("name") or "试审规则",
            description=rule_payload.get("description", ""),
            category=RuleCategory.CUSTOM,
            severity=RuleSeverity(rule_payload.get("severity", "warning")),
            source=rule_payload.get("source", "custom"),
            review_type=ReviewType(rule_payload.get("review_type", "llm")),
            logic=rule_payload.get("logic", ""),
            standard_ref=rule_payload.get("standard_ref", ""),
            code=rule_payload.get("code", ""),
            params=rule_payload.get("params", {}),
            scope=RuleScope(rule_payload.get("scope", "all")),
            target_headings=_normalize_list(rule_payload.get("target_headings")),
            required_elements=_normalize_list(rule_payload.get("required_elements")),
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


@bp.route("/api/import-template")
def api_download_import_template():
    """下载面向用户的规则批量导入模板。"""
    if not RULE_IMPORT_TEMPLATE.exists():
        return jsonify({"error": "导入模板不存在，请联系管理员"}), 404
    return send_file(
        RULE_IMPORT_TEMPLATE,
        as_attachment=True,
        download_name="审查规则导入模板.xlsx",
    )


@bp.route("/api/sets/<source>/import", methods=["POST"])
def api_import_rules(source: str):
    """预检查或批量导入当前规则集的 Excel 规则。"""
    if not _rule_set_exists(source):
        return jsonify({"error": f"规则集 '{source}' 不存在，请先创建规则集"}), 404

    try:
        filename, duplicate_mode, rows = _prepare_rule_import(source)
    except RuleImportError as exc:
        return jsonify({"error": str(exc)}), 400
    preview = _import_preview(rows)

    commit = str(request.form.get("commit", "")).lower() in {"1", "true", "yes"}
    if not commit:
        return jsonify(preview)
    partial = str(request.form.get("partial", "")).lower() in {"1", "true", "yes"}
    if preview["error_count"] and not partial:
        return jsonify({
            **preview,
            "error": "文件中仍有错误；可修正后重试，或选择仅导入通过项",
        }), 400
    if preview["valid_count"] == 0:
        return jsonify({**preview, "error": "没有可导入或更新的规则"}), 400

    existing_rules = RuleLoader.load_all_rules("default", include_extensions=False)
    overrides = load_overrides()
    existing_ids = {rule.rule_id for rule in existing_rules} | set(overrides)
    created = {}
    updated = {}
    for row in rows:
        if row.errors or row.action == "skip":
            continue
        payload = row.payload or {}
        rule_data = _build_custom_rule_data(payload)
        if row.action == "update":
            rule_id = row.existing_rule_id
            previous = deepcopy(overrides.get(rule_id))
            if previous is None:
                continue
            updated[rule_id] = {"before": previous, "after": deepcopy(rule_data)}
            overrides[rule_id] = rule_data
        else:
            rule_id = _make_rule_id(payload, existing_ids)
            existing_ids.add(rule_id)
            created[rule_id] = deepcopy(rule_data)
            overrides[rule_id] = rule_data
    save_overrides(overrides)

    batch_id = uuid.uuid4().hex
    batch = {
        "batch_id": batch_id,
        "source": source,
        "filename": filename,
        "created_at": beijing_now_str(),
        "status": "active",
        "duplicate_mode": duplicate_mode,
        "partial": partial,
        "total": preview["total"],
        "created_count": len(created),
        "updated_count": len(updated),
        "skipped_count": preview["skip_count"],
        "error_count": preview["error_count"],
        "warning_count": preview["warning_count"],
        "created": created,
        "updated": updated,
    }
    batches = _load_import_batches()
    batches.insert(0, batch)
    _save_import_batches(batches[:200])

    return jsonify({
        **preview,
        "batch_id": batch_id,
        "imported_count": len(created) + len(updated),
        "created_count": len(created),
        "updated_count": len(updated),
    })


@bp.route("/api/sets/<source>/import-issues", methods=["POST"])
def api_download_import_issues(source: str):
    """Download invalid and warning rows as a correction workbook."""
    if not _rule_set_exists(source):
        return jsonify({"error": f"规则集 '{source}' 不存在"}), 404
    try:
        _, _, rows = _prepare_rule_import(source)
    except RuleImportError as exc:
        return jsonify({"error": str(exc)}), 400
    workbook = build_issue_workbook(rows)
    return send_file(
        BytesIO(workbook),
        as_attachment=True,
        download_name="规则导入问题清单.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.route("/api/sets/<source>/import-batches")
def api_import_batches(source: str):
    batches = [
        {
            key: value for key, value in batch.items()
            if key not in {"created", "updated"}
        }
        for batch in _load_import_batches()
        if batch.get("source") == source
    ]
    return jsonify({"batches": batches[:20]})


@bp.route("/api/import-batches/<batch_id>/rollback", methods=["POST"])
def api_rollback_import_batch(batch_id: str):
    batches = _load_import_batches()
    batch = next((item for item in batches if item.get("batch_id") == batch_id), None)
    if not batch:
        return jsonify({"error": "导入批次不存在"}), 404
    if batch.get("status") != "active":
        return jsonify({"error": "该导入批次已经撤销"}), 400

    overrides = load_overrides()
    conflicts = []
    for rule_id, imported_value in batch.get("created", {}).items():
        if overrides.get(rule_id) != imported_value:
            conflicts.append(rule_id)
    for rule_id, snapshot in batch.get("updated", {}).items():
        if overrides.get(rule_id) != snapshot.get("after"):
            conflicts.append(rule_id)
    if conflicts:
        return jsonify({
            "error": "批次中的规则已被再次修改，不能整批撤销",
            "conflicts": conflicts,
        }), 409

    for rule_id in batch.get("created", {}):
        overrides.pop(rule_id, None)
    for rule_id, snapshot in batch.get("updated", {}).items():
        overrides[rule_id] = snapshot.get("before", {})
    save_overrides(overrides)

    batch["status"] = "rolled_back"
    batch["rolled_back_at"] = beijing_now_str()
    _save_import_batches(batches)
    return jsonify({
        "ok": True,
        "removed_count": len(batch.get("created", {})),
        "restored_count": len(batch.get("updated", {})),
    })


@bp.route("/api/rules", methods=["POST"])
def api_create_rule():
    """创建自定义规则。"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "请求体不能为空"}), 400

    name = data.get("name", "").strip()
    code = data.get("code", "").strip()
    source = data.get("source", "").strip()

    if not code or not name or not source:
        return jsonify({"error": "编号、规则名称和所属规则集不能为空"}), 400
    validation_error = _validate_custom_rule_definition(data)
    if validation_error:
        return jsonify({"error": validation_error}), 400

    existing_rules = RuleLoader.load_all_rules("default", include_extensions=False)
    if any((r.code or "").strip() == code for r in existing_rules):
        return jsonify({"error": f"编号 '{code}' 已存在"}), 400
    existing_ids = {r.rule_id for r in existing_rules}
    rule_id = _make_rule_id(data, existing_ids)

    try:
        rule_data = _build_custom_rule_data(data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

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
