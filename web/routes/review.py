"""
Review routes for the web application.
"""
import os
import json
import threading
import uuid
from flask import Blueprint, render_template, request, jsonify, send_file, current_app
from web.tasks import run_review_task

bp = Blueprint('review', __name__)


@bp.route('/')
def index():
    db = current_app.db
    recent = db.get_recent_review_tasks(limit=5)

    # 获取可用规则集列表
    from rules.loaders.rule_loader import RuleLoader
    from web.routes.rules import _group_rules_by_source
    rules = RuleLoader.load_all_rules("aviation", include_extensions=False)
    groups, _, _ = _group_rules_by_source(rules)
    rule_sets = [{"source": g["source"], "name": g["display_name"], "count": g["total"]} for g in groups]

    return render_template('review.html', active_page='review', recent_tasks=recent, rule_sets=rule_sets)


@bp.route('/upload', methods=['POST'])
def upload():
    db = current_app.db

    if 'file' not in request.files:
        return jsonify({'error': '未选择文件'}), 400

    file = request.files['file']
    if not file.filename.endswith('.docx'):
        return jsonify({'error': '仅支持 .docx 格式'}), 400

    mode = request.form.get('mode', 'both')
    doc_type = request.form.get('doc_type', 'auto')
    rule_set = request.form.get('rule_set', 'all')
    safe_name = os.path.basename(file.filename)
    unique_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_name)
    file.save(filepath)

    task_id = db.create_review_task(file.filename, filepath, mode)

    thread = threading.Thread(
        target=run_review_task,
        args=(task_id, filepath, mode, doc_type, rule_set, db)
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

    result = DocumentReviewResult(
        document_path=task['filepath'],
        document_title=task['filename'],
        overall_passed=result_data.get('passed', True),
        total_issues=result_data.get('total_issues', 0),
        errors=result_data.get('errors', 0),
        warnings=result_data.get('warnings', 0),
        summary=result_data.get('summary', ''),
    )

    for sec in result_data.get('sections', []):
        sr = SectionReviewResult(
            section_id=sec['section_id'],
            section_text=sec['section_text'],
            passed=sec['passed'],
        )
        for issue in sec.get('issues', []):
            rr = RuleResult(
                rule_id="",
                rule_name=issue.get('rule_name', ''),
                passed=False,
                severity=RuleSeverity(issue.get('severity', 'warning')),
                message=issue.get('message', ''),
                section_id=sec['section_id'],
                suggestions=issue.get('suggestions', []),
                rule_source=issue.get('rule_source', 'RULE'),
            )
            sr.rule_results.append(rr)
        result.section_results.append(sr)

    output_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'reports')
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f'review_report_{task_id}.docx')

    reporter = ReporterFactory.create_reporter('docx')
    reporter.save(result, output_path)

    return send_file(output_path, as_attachment=True, download_name=f'审查报告_{task["filename"]}')
