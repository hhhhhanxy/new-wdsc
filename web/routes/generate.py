"""
Generate routes for the web application.
"""
import os
import json
import threading
from flask import Blueprint, render_template, request, jsonify, send_file, current_app

bp = Blueprint('generate', __name__)


@bp.route('/')
def index():
    return render_template('generate.html', active_page='generate')


@bp.route('/start', methods=['POST'])
def start():
    db = current_app.db
    data = request.get_json()
    if not data or not data.get('title'):
        return jsonify({'error': '请输入文档标题'}), 400

    params = {
        'title': data['title'],
        'description': data.get('description', ''),
        'technical_params': data.get('technical_params', ''),
        'generation_definition': data.get('generation_definition', ''),
    }

    task_id = db.create_generate_task(
        doc_type=data.get('doc_type', 'design_report'),
        template_name=data.get('template_name', ''),
        params=params
    )

    thread = threading.Thread(
        target=run_generate_task,
        args=(task_id, data, current_app.config['UPLOAD_FOLDER'], db)
    )
    thread.daemon = True
    thread.start()

    return jsonify({'task_id': task_id})


@bp.route('/status/<int:task_id>')
def status(task_id):
    task = current_app.db.get_generate_task(task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    return jsonify(dict(task))


@bp.route('/download/<int:task_id>')
def download(task_id):
    task = current_app.db.get_generate_task(task_id)
    if not task or task['status'] not in ('completed', 'review_failed'):
        return '文件未就绪', 404

    result_path = task.get('result_path')
    if result_path and os.path.exists(result_path):
        return send_file(result_path, as_attachment=True)

    return '文件不存在', 404


def run_generate_task(task_id, data, upload_folder, db):
    """Execute document generation task with review-generate closed loop."""
    try:
        db.update_generate_task(task_id, progress=10, status='processing')

        from llm.client import LLMClientFactory
        from config.settings import settings
        from rules.base_rule import RuleRegistry
        from rules.loaders.rule_loader import RuleLoader
        from core.pipeline import generate_and_review

        llm_client = LLMClientFactory.create_client(settings.llm_provider)
        db.update_generate_task(task_id, progress=20)

        # Load rules for review
        rules = RuleLoader.load_all_rules(profile="default")
        registry = RuleRegistry()
        for rule in rules:
            registry.register(rule)

        doc_type = data.get('doc_type', 'custom_document')

        db.update_generate_task(task_id, progress=30)

        output_dir = os.path.join(upload_folder, 'generated')
        result = generate_and_review(
            doc_type=doc_type,
            title=data.get('title', ''),
            params={
                "description": data.get('description', ''),
                "technical_params": data.get('technical_params', ''),
                "generation_definition": data.get('generation_definition', ''),
                "doc_type": doc_type,
                "generator": "user_defined_docx",
            },
            llm_client=llm_client,
            rule_registry=registry,
            output_dir=output_dir,
        )

        # Build review summary for storage
        review_summary = {}
        if result.review_result:
            rr = result.review_result
            review_summary = {
                "passed": rr.overall_passed,
                "total_issues": rr.total_issues,
                "errors": rr.errors,
                "warnings": rr.warnings,
                "phases": {
                    phase.value: {"passed": pr.passed, "issues": pr.issues_count}
                    for phase, pr in rr.phase_results.items()
                },
            }

        db.update_generate_task(
            task_id,
            progress=100,
            status='completed' if result.passed_review else 'review_failed',
            result_path=result.generated_path,
            error=None if result.passed_review else "生成文档未通过审查，请查看审查报告",
        )

        # Store review result separately
        if review_summary:
            db.update_generate_task(
                task_id,
                result_path=result.generated_path or "",
            )
            # Add review data to a separate field if possible
            import json
            task = db.get_generate_task(task_id)
            if task:
                params_data = json.loads(task['params']) if isinstance(task['params'], str) else task['params']
                params_data['review_result'] = review_summary
                cursor = db.conn.cursor()
                cursor.execute(
                    'UPDATE generate_tasks SET params = ? WHERE id = ?',
                    (json.dumps(params_data), task_id)
                )
                db.conn.commit()

    except Exception as e:
        import traceback
        traceback.print_exc()
        db.update_generate_task(task_id, status='failed', error=str(e))
