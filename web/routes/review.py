"""
Review routes for the web application.
"""
import os
import json
import threading
import uuid
import hashlib
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, jsonify, send_file, current_app, redirect, url_for
from web.tasks import run_review_task
from web.time_utils import BEIJING_TZ, beijing_now, beijing_now_str, format_beijing_time

bp = Blueprint('review', __name__)
RUNNING_STATUSES = {'pending', 'processing', 'paused'}
STALE_RUNNING_HOURS = 2


def _current_rule_lookup():
    """构建当前前端启用规则查找表，仅用于无快照旧任务的兼容。"""
    from rules.loaders.rule_loader import RuleLoader

    rules = [
        r for r in RuleLoader.load_all_rules("default", include_extensions=False)
        if r.enabled
    ]

    by_id = {}
    by_name = {}
    for rule in rules:
        for key in (rule.rule_id, rule.code, *(getattr(rule, "aliases", []) or [])):
            if key:
                by_id[str(key)] = rule
        if rule.name:
            by_name[rule.name] = rule
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
        for key in (
            normalized.get("rule_id"),
            normalized.get("code"),
            *(normalized.get("aliases") or []),
        ):
            if key:
                by_id[str(key)] = normalized
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
    if "," in rule_set:
        sources = [item.strip() for item in rule_set.split(",") if item.strip()]
        groups = groups or []
        names = []
        for source in sources:
            group = next((g for g in groups if g.get("source") == source), None)
            names.append((group.get("display_name") if group else source) or source)
        label = "、".join(names)
        if enabled_count is not None:
            return f"{label}（启用 {enabled_count} 条）"
        return label
    if rule_set.startswith("specialty:"):
        specialty_id = rule_set.split(":", 1)[1].strip()
        try:
            from web.option_registry import get_specialty
            specialty = get_specialty(specialty_id)
        except Exception:
            specialty = None
        name = specialty.get("name") if specialty else specialty_id
        label = f"通用规则 + {name}规则"
        if enabled_count is not None:
            return f"{label}（启用 {enabled_count} 条）"
        return label

    groups = groups or []
    group = next((g for g in groups if g.get("source") == rule_set), None)
    if group:
        label = group.get("display_name") or rule_set
        if enabled_count is not None:
            return f"{label}（启用 {enabled_count} 条）"
        return label
    return rule_set


def _status_display(status: str) -> tuple[str, str]:
    labels = {
        "pending": ("等待中", "default"),
        "processing": ("审查中", "warning"),
        "paused": ("已暂停", "warning"),
        "completed": ("已完成", "success"),
        "failed": ("失败", "danger"),
        "canceled": ("已停止", "default"),
        "blocked": ("安全阻断", "danger"),
    }
    return labels.get(status or "", (status or "未知", "default"))


ISSUE_REVIEW_STATUSES = {
    "pending": "待复核",
    "confirmed": "确认问题",
    "false_positive": "误报",
    "fixed": "已整改",
}


def _issue_id(section_id: str, issue: dict, index: int) -> str:
    fingerprint = "|".join([
        str(section_id or ""),
        str(issue.get("rule_id") or ""),
        str(issue.get("rule_name") or ""),
        str(issue.get("message") or ""),
        str(index),
    ])
    return hashlib.sha1(fingerprint.encode("utf-8")).hexdigest()[:16]


def _parse_task_time(value: str):
    if not value:
        return None
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=BEIJING_TZ)
    return parsed.astimezone(BEIJING_TZ)


def _is_stale_running_task(task: dict) -> bool:
    if task.get("status") not in RUNNING_STATUSES:
        return False
    created_at = _parse_task_time(task.get("created_at"))
    if not created_at:
        return False
    return beijing_now() - created_at > timedelta(hours=STALE_RUNNING_HOURS)


def decorate_recent_review_tasks(tasks: list, groups: list = None) -> list:
    """为最近审查列表补充展示字段，供首页和审查页共用。"""
    decorated = []
    for task in tasks:
        item = dict(task)
        status_label, badge_class = _status_display(item.get("status"))
        item["status_label"] = status_label
        item["badge_class"] = badge_class
        item["error_preview"] = (item.get("error") or "").strip()
        item["stale"] = _is_stale_running_task(item)
        if item["stale"]:
            item["status_label"] = "已卡住"
            item["badge_class"] = "danger"
            item["error_preview"] = f"任务超过 {STALE_RUNNING_HOURS} 小时未完成，后台进程可能已退出"
        item["progress"] = int(item.get("progress") or 0)
        item["rule_set_label"] = _rule_set_label(item.get("rule_set"), groups)
        item["created_at_display"] = format_beijing_time(item.get("created_at", "") or "")
        item["completed_at_display"] = format_beijing_time(item.get("completed_at", "") or "")
        item["total_issues"] = None
        item["errors"] = None
        item["warnings"] = None
        item["passed"] = None

        result_data = item.get("result")
        if result_data:
            try:
                parsed = json.loads(result_data) if isinstance(result_data, str) else result_data
            except (TypeError, json.JSONDecodeError):
                parsed = {}
            if isinstance(parsed, dict):
                item["total_issues"] = parsed.get("total_issues")
                item["errors"] = parsed.get("errors")
                item["warnings"] = parsed.get("warnings")
                item["passed"] = parsed.get("passed")
                item["rule_set_label"] = _rule_set_label(parsed.get("rule_set") or item.get("rule_set"), groups)

        decorated.append(item)
    return decorated


@bp.route('/')
def index():
    db = current_app.db

    # 获取可用规则集列表
    from rules.loaders.rule_loader import RuleLoader
    from web.routes.rules import _group_rules_by_source
    rules = RuleLoader.load_all_rules("default", include_extensions=False)
    groups, _, _ = _group_rules_by_source(rules)
    rule_sets = [{"source": g["source"], "name": g["display_name"], "count": g["total"]} for g in groups]
    focus_task_id = request.args.get("task_id", type=int)
    initial_major_id = request.args.get("major", "")
    from web.option_registry import get_specialties, get_specialty_groups
    specialty_groups = get_specialty_groups("review")
    if not focus_task_id and not initial_major_id:
        first_specialty = next(
            (
                specialty
                for group in specialty_groups
                for specialty in (group.get("specialties") or [])
                if specialty.get("id")
            ),
            None,
        )
        if first_specialty:
            return redirect(url_for("review.index", major=first_specialty.get("id")))

    return render_template(
        'review.html',
        active_page='review',
        rule_sets=rule_sets,
        focus_task_id=focus_task_id,
        review_specialty_options=get_specialties("review"),
        review_specialty_groups=specialty_groups,
        initial_major_id=initial_major_id,
    )


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
    specialty_id = str(request.form.get('specialty_id') or '').strip()
    from web.option_registry import get_specialty, resolve_model_option
    specialty = get_specialty(specialty_id)
    if not specialty:
        return jsonify({'error': '请先选择文档所属专业'}), 400
    specialty_name = specialty.get('name') if specialty else ''
    model_option = resolve_model_option(request.form.get('model_id'), 'review')
    safe_name = os.path.basename(file.filename)
    unique_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_name)
    file.save(filepath)

    task_id = db.create_review_task(
        file.filename,
        filepath,
        mode,
        rule_set=rule_set,
        model_id=model_option.get('id'),
        model_name=model_option.get('name'),
        specialty_id=specialty_id,
        specialty_name=specialty_name,
        document_kind_name=str(request.form.get('document_kind_name') or '').strip(),
    )

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


@bp.route('/api/active')
def active_review_task():
    """Return the newest running review task for the global progress dock."""
    db = current_app.db
    tasks = db.get_recent_review_tasks(limit=max(db.count_review_tasks(), 1))
    active = next((task for task in tasks if task.get('status') in RUNNING_STATUSES), None)
    if not active:
        return jsonify({'ok': True, 'task': None})
    decorated = decorate_recent_review_tasks([active])[0]
    return jsonify({'ok': True, 'task': decorated})


@bp.route('/api/issues/<int:task_id>/<issue_id>/status', methods=['POST'])
def update_issue_status(task_id, issue_id):
    db = current_app.db
    task = db.get_review_task(task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    if task.get('status') != 'completed':
        return jsonify({'error': '只有已完成的审查任务可以更新问题复核状态'}), 400

    data = request.get_json(silent=True) or {}
    review_status = str(data.get('review_status') or '').strip()
    if review_status not in ISSUE_REVIEW_STATUSES:
        return jsonify({'error': '复核状态不支持'}), 400
    issue_key = data.get('issue_key') if isinstance(data.get('issue_key'), dict) else {}

    try:
        result_data = json.loads(task.get('result') or '{}')
    except (TypeError, json.JSONDecodeError):
        return jsonify({'error': '审查结果不可解析'}), 400

    matched = False
    matched_issue_id = issue_id
    for sec in result_data.get('sections', []):
        section_id = sec.get('section_id', '')
        for index, issue in enumerate(sec.get('issues', []), start=1):
            current_issue_id = issue.get('issue_id') or _issue_id(section_id, issue, index)
            issue.setdefault('issue_id', current_issue_id)
            issue.setdefault('review_status', 'pending')
            key_matches = (
                str(issue_key.get('section_id') or '') == str(section_id or '')
                and int(issue_key.get('issue_index') or 0) == index
                and str(issue_key.get('rule_id') or '') == str(issue.get('rule_id') or '')
                and str(issue_key.get('message') or '') == str(issue.get('message') or '')
            )
            if current_issue_id == issue_id or key_matches:
                issue['review_status'] = review_status
                matched = True
                matched_issue_id = current_issue_id
                break
        if matched:
            break

    if not matched:
        return jsonify({'error': '问题不存在或已变化'}), 404

    db.update_review_task(
        task_id,
        result=json.dumps(result_data, ensure_ascii=False),
    )
    return jsonify({
        'ok': True,
        'issue_id': matched_issue_id,
        'review_status': review_status,
        'review_status_label': ISSUE_REVIEW_STATUSES[review_status],
    })


@bp.route('/pause/<int:task_id>', methods=['POST'])
def pause(task_id):
    db = current_app.db
    task = db.get_review_task(task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    if task.get('status') != 'processing':
        return jsonify({'error': '只有审查中的任务可以暂停'}), 400
    db.update_review_task(task_id, status='paused')
    return jsonify({'ok': True, 'status': 'paused'})


@bp.route('/resume/<int:task_id>', methods=['POST'])
def resume(task_id):
    db = current_app.db
    task = db.get_review_task(task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    if task.get('status') != 'paused':
        return jsonify({'error': '只有已暂停的任务可以继续'}), 400
    db.update_review_task(task_id, status='processing')
    return jsonify({'ok': True, 'status': 'processing'})


@bp.route('/cancel/<int:task_id>', methods=['POST'])
def cancel(task_id):
    db = current_app.db
    task = db.get_review_task(task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    if task.get('status') not in RUNNING_STATUSES:
        return jsonify({'error': '只有等待中、审查中或已暂停的任务可以停止'}), 400
    db.update_review_task(
        task_id,
        status='canceled',
        error='用户手动停止审查',
        progress_stage='canceled',
        progress_message='用户手动停止审查',
        completed_at=beijing_now_str(),
    )
    return jsonify({'ok': True, 'status': 'canceled'})


@bp.route('/delete/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    db = current_app.db
    task = db.get_review_task(task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    stopped = False
    if task.get('status') in RUNNING_STATUSES:
        db.update_review_task(
            task_id,
            status='canceled',
            error='删除记录时自动停止审查',
            progress_stage='canceled',
            progress_message='删除记录时自动停止审查',
            completed_at=beijing_now_str(),
        )
        stopped = True
    deleted = db.delete_review_task(task_id)
    return jsonify({'ok': True, 'deleted': deleted, 'stopped': stopped})


@bp.route('/delete-all', methods=['DELETE'])
def delete_all_tasks():
    db = current_app.db
    all_tasks = db.get_recent_review_tasks(limit=max(db.count_review_tasks(), 1))
    delete_ids = [
        task['id'] for task in all_tasks
        if task.get('status') not in RUNNING_STATUSES or _is_stale_running_task(task)
    ]
    deleted = sum(db.delete_review_task(task_id) for task_id in delete_ids)
    remaining = db.count_review_tasks()
    return jsonify({'ok': True, 'deleted': deleted, 'remaining': remaining})


@bp.route('/delete-stale', methods=['DELETE'])
def delete_stale_tasks():
    db = current_app.db
    all_tasks = db.get_recent_review_tasks(limit=max(db.count_review_tasks(), 1))
    stale_ids = [task['id'] for task in all_tasks if _is_stale_running_task(task)]
    deleted = sum(db.delete_review_task(task_id) for task_id in stale_ids)
    return jsonify({'ok': True, 'deleted': deleted})


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
            rr.details["review_status"] = issue.get("review_status", "pending")
            rr.details["review_status_label"] = ISSUE_REVIEW_STATUSES.get(
                issue.get("review_status", "pending"),
                "待复核",
            )
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
