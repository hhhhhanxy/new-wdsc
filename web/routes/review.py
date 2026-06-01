"""
Review routes for the web application.
"""
import os
import json
import threading
import uuid
from flask import Blueprint, render_template, request, jsonify, send_file, current_app
from web.tasks import run_review_task
from web.time_utils import format_beijing_time

bp = Blueprint('review', __name__)


def _current_rule_lookup():
    """构建当前前端启用规则查找表，仅用于无快照旧任务的兼容。"""
    from rules.loaders.rule_loader import RuleLoader

    rules = [
        r for r in RuleLoader.load_all_rules("default", include_extensions=False)
        if r.enabled
    ]

    by_id = {r.rule_id: r for r in rules if r.rule_id}
    by_name = {r.name: r for r in rules if r.name}
    return by_id, by_name


def _snapshot_lookup(snapshot: dict):
    by_id = {}
    by_name = {}
    if not isinstance(snapshot, dict):
        return by_id, by_name

    for rule_id, info in snapshot.items():
        if not isinstance(info, dict):
            continue
        normalized = dict(info)
        normalized.setdefault("rule_id", rule_id)
        if normalized.get("rule_id"):
            by_id[normalized["rule_id"]] = normalized
        if normalized.get("name"):
            by_name[normalized["name"]] = normalized
    return by_id, by_name


def _rule_field(rule_info, field: str, default: str = ""):
    if not rule_info:
        return default
    if isinstance(rule_info, dict):
        return rule_info.get(field, default)
    return getattr(rule_info, field, default)


def _display_source(source: str) -> str:
    labels = {
        "RULE": "规则引擎",
        "LLM": "LLM语义审查",
        "RULE+LLM": "规则引擎+LLM",
        "BOTH": "规则引擎+LLM",
    }
    return labels.get(source or "", source or "未标明")


def _rule_set_label(rule_set: str, groups: list = None, enabled_count: int = None) -> str:
    rule_set = rule_set or "all"
    if rule_set == "all":
        if enabled_count is not None:
            return f"全部规则（启用 {enabled_count} 条）"
        return "全部规则"

    groups = groups or []
    group = next((g for g in groups if g.get("source") == rule_set), None)
    if group:
        label = group.get("display_name") or rule_set
        if enabled_count is not None:
            return f"{label}（启用 {enabled_count} 条）"
        return label
    return rule_set


@bp.route('/')
def index():
    db = current_app.db

    # 获取可用规则集列表
    from rules.loaders.rule_loader import RuleLoader
    from web.routes.rules import _group_rules_by_source
    rules = RuleLoader.load_all_rules("default", include_extensions=False)
    groups, _, _ = _group_rules_by_source(rules)
    rule_sets = [{"source": g["source"], "name": g["display_name"], "count": g["total"]} for g in groups]
    recent = []
    for task in db.get_recent_review_tasks(limit=5):
        task_data = dict(task)
        task_data["rule_set_label"] = _rule_set_label(task_data.get("rule_set"), groups)
        recent.append(task_data)

    return render_template('review.html', active_page='review', recent_tasks=recent, rule_sets=rule_sets)


@bp.route('/upload', methods=['POST'])
def upload():
    db = current_app.db

    if 'file' not in request.files:
        return jsonify({'error': '未选择文件'}), 400

    file = request.files['file']
    if not file.filename.endswith('.docx'):
        return jsonify({'error': '仅支持 .docx 格式'}), 400

    mode = 'by_rule'
    rule_set = request.form.get('rule_set', 'all')
    safe_name = os.path.basename(file.filename)
    unique_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_name)
    file.save(filepath)

    task_id = db.create_review_task(file.filename, filepath, mode, rule_set=rule_set)

    thread = threading.Thread(
        target=run_review_task,
        args=(task_id, filepath, rule_set, db)
    )
    thread.daemon = True
    thread.start()

    return jsonify({'task_id': task_id})


@bp.route('/status/<int:task_id>')
def status(task_id):
    task = current_app.db.get_review_task(task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    return jsonify(dict(task))


@bp.route('/report/<int:task_id>')
def report(task_id):
    db = current_app.db
    task = db.get_review_task(task_id)
    if not task or task['status'] != 'completed':
        return '报告未就绪', 404

    from reporters.base_reporter import ReporterFactory
    from core.executor import DocumentReviewResult, SectionReviewResult
    from rules.base_rule import RuleResult, RuleSeverity

    result_data = json.loads(task['result']) if isinstance(task['result'], str) else task['result']
    snapshot_by_id, snapshot_by_name = _snapshot_lookup(result_data.get("rule_snapshot", {}))
    current_by_id, current_by_name = _current_rule_lookup()
    has_snapshot = bool(snapshot_by_id or snapshot_by_name)

    result = DocumentReviewResult(
        document_path=task['filepath'],
        document_title=task['filename'],
        overall_passed=True,
        total_issues=0,
        errors=0,
        warnings=0,
        summary=result_data.get('summary', ''),
    )
    review_time = result_data.get('review_time', '') or task.get('completed_at', '') or ''
    result.review_time = format_beijing_time(review_time)
    result.completed_at = format_beijing_time(task.get('completed_at', '') or '')
    result.review_duration = result_data.get('review_duration', '')
    result.llm_issues = 0

    for sec in result_data.get('sections', []):
        sr = SectionReviewResult(
            section_id=sec['section_id'],
            section_text=sec['section_text'],
            passed=sec['passed'],
        )
        for issue in sec.get('issues', []):
            matched_rule = (
                snapshot_by_id.get(issue.get('rule_id', ''))
                or snapshot_by_name.get(issue.get('rule_name', ''))
            )
            if not matched_rule and not has_snapshot:
                matched_rule = (
                    current_by_id.get(issue.get('rule_id', ''))
                    or current_by_name.get(issue.get('rule_name', ''))
                )
            if not matched_rule:
                continue
            rule_id = issue.get('rule_id') or _rule_field(matched_rule, 'rule_id')
            rule_name = issue.get('rule_name') or _rule_field(matched_rule, 'name')
            rule_code = issue.get('rule_code') or _rule_field(matched_rule, 'code')
            rule_reference = (
                issue.get('rule_reference')
                or issue.get('standard_ref')
                or _rule_field(matched_rule, 'standard_ref')
            )
            rule_logic = issue.get('rule_logic') or _rule_field(matched_rule, 'logic')
            review_type = _rule_field(matched_rule, 'review_type', '')
            rule_source = issue.get('rule_source') or ('LLM' if review_type == 'llm' else 'RULE')
            rr = RuleResult(
                rule_id=rule_id,
                rule_name=rule_name,
                passed=False,
                severity=RuleSeverity(issue.get('severity', 'warning')),
                message=issue.get('message', ''),
                section_id=sec['section_id'],
                suggestions=issue.get('suggestions', []),
                rule_source=rule_source,
                rule_reference=rule_reference,
            )
            rr.details["rule_code"] = rule_code
            rr.details["rule_logic"] = rule_logic
            rr.details["source_label"] = _display_source(rule_source)
            sr.rule_results.append(rr)
            result.total_issues += 1
            if rr.severity == RuleSeverity.ERROR:
                result.errors += 1
            elif rr.severity == RuleSeverity.WARNING:
                result.warnings += 1
            if rr.rule_source == "LLM":
                result.llm_issues += 1
            if rr.severity in (RuleSeverity.ERROR, RuleSeverity.WARNING):
                sr.passed = False
                result.overall_passed = False
        result.section_results.append(sr)
    raw_rule_set = result_data.get('rule_set') or task.get('rule_set') or 'all'
    snapshot_count = len(snapshot_by_id) if has_snapshot else None
    from rules.loaders.rule_loader import RuleLoader
    from web.routes.rules import _group_rules_by_source
    groups, _, _ = _group_rules_by_source(RuleLoader.load_all_rules("default", include_extensions=False))
    result.rule_set = _rule_set_label(raw_rule_set, groups, snapshot_count)

    output_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'reports')
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f'review_report_{task_id}.docx')

    reporter = ReporterFactory.create_reporter('docx')
    reporter.save(result, output_path)

    return send_file(output_path, as_attachment=True, download_name=f'审查报告_{task["filename"]}')
