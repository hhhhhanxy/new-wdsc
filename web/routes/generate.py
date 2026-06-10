"""
Generate routes for the web application.
"""
import os
import json
import threading
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, send_file, current_app

bp = Blueprint('generate', __name__)


@bp.route('/')
def index():
    return render_template('generate.html', active_page='generate')


@bp.route('/api/templates')
def templates():
    """Return templates that can generate by filling a saved source DOCX."""
    from templates.template_manager import TemplateManager

    manager = TemplateManager()
    return jsonify({
        "templates": [
            template for template in manager.list_template_dicts()
            if _has_source_docx(template)
        ]
    })


@bp.route('/api/templates/<template_id>')
def template_detail(template_id):
    """Return one template with its chapter structure."""
    from templates.template_manager import TemplateManager

    manager = TemplateManager()
    template = manager.get_template(template_id)
    if not template:
        return jsonify({"error": f"模板不存在: {template_id}"}), 404
    return jsonify(manager.serialize_template(template))


@bp.route('/start', methods=['POST'])
def start():
    db = current_app.db
    data = request.get_json()
    if not data or not data.get('title'):
        return jsonify({'error': '请输入文档标题'}), 400
    if not data.get('template_id'):
        return jsonify({'error': '请选择文档模板'}), 400

    from templates.template_manager import TemplateManager

    manager = TemplateManager()
    template = manager.get_template(data['template_id'])
    if not template:
        return jsonify({'error': f"模板不存在: {data['template_id']}"}), 400

    inputs = data.get('inputs') or {}
    if not str(inputs.get('product_name', '')).strip():
        return jsonify({'error': '请输入产品名称'}), 400
    template_dict = manager.serialize_template(template)
    if not _has_source_docx(template_dict):
        return jsonify({'error': '该模板没有原始 DOCX 文件，请先在生成模板库中上传模板'}), 400

    params = {
        'title': data['title'],
        'template_id': template.template_id,
        'template_name': template.name,
        'inputs': inputs,
        'auto_review': False,
        'review_result': {
            'reserved': True,
            'message': '生成后自动审查功能已预留，当前版本暂不执行。',
        },
    }

    task_id = db.create_generate_task(
        doc_type=template.doc_type.value if template.doc_type else template.template_id,
        template_name=template.name,
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


@bp.route('/api/recent')
def recent():
    """Return recent generation task records."""
    page_size = 5
    page = request.args.get('page', 1, type=int)
    total = current_app.db.count_generate_tasks()
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(max(page, 1), total_pages)
    offset = (page - 1) * page_size
    tasks = [
        _decorate_generate_task(task)
        for task in current_app.db.get_recent_generate_tasks(limit=page_size, offset=offset)
    ]
    return jsonify({
        'tasks': tasks,
        'pagination': {
            'page': page,
            'page_size': page_size,
            'total': total,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages,
            'start': offset + 1 if total else 0,
            'end': min(offset + len(tasks), total),
        },
    })


@bp.route('/download/<int:task_id>')
def download(task_id):
    task = current_app.db.get_generate_task(task_id)
    if not task or task['status'] != 'completed':
        return '文件未就绪', 404

    result_path = task.get('result_path')
    if result_path and os.path.exists(result_path):
        return send_file(result_path, as_attachment=True)

    return '文件不存在', 404


@bp.route('/delete/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    task = current_app.db.get_generate_task(task_id)
    if not task:
        return jsonify({'error': '生成记录不存在'}), 404
    if task.get('status') in ('pending', 'processing'):
        return jsonify({'error': '生成任务仍在执行，完成或失败后再删除'}), 400
    deleted = current_app.db.delete_generate_task(task_id)
    return jsonify({'ok': True, 'deleted': deleted})


def run_generate_task(task_id, data, upload_folder, db):
    """Execute document generation task."""
    try:
        db.update_generate_task(
            task_id,
            progress=5,
            status='processing',
            progress_stage='prepare',
            progress_message='正在准备生成任务',
        )

        from core.pipeline import generate_document_only
        from config.settings import settings
        from llm.client import LLMClientFactory

        db.update_generate_task(
            task_id,
            progress=15,
            progress_stage='prepare',
            progress_message='模板文件已就绪',
        )

        template_id = data.get('template_id')
        inputs = data.get('inputs') or {}

        db.update_generate_task(
            task_id,
            progress=18,
            progress_stage='llm',
            progress_message=f'正在初始化大模型客户端：{settings.llm_model}',
        )
        llm_client = LLMClientFactory.create_client(settings.llm_provider)

        def update_chapter_progress(current, total, chapter):
            percent = 20 + int((current - 1) / max(total, 1) * 75)
            title = f"{getattr(chapter, 'number', '')} {getattr(chapter, 'title', '')}".strip()
            db.update_generate_task(
                task_id,
                progress=max(20, min(percent, 95)),
                progress_stage='filling',
                progress_message=f"正在处理章节 {current}/{total}：{title}",
                current_section=current,
                total_sections=total,
            )

        output_dir = os.path.join(upload_folder, 'generated')
        result = generate_document_only(
            doc_type=template_id,
            title=data.get('title', ''),
            params={
                "template_id": template_id,
                "inputs": inputs,
                "doc_type": template_id,
                "generator": "template_docx",
            },
            llm_client=llm_client,
            output_dir=output_dir,
            progress_callback=update_chapter_progress,
        )

        if result.error:
            raise RuntimeError(result.error)

        db.update_generate_task(
            task_id,
            progress=100,
            status='completed',
            progress_stage='completed',
            progress_message='文档生成完成，自动审查暂未执行',
            result_path=result.generated_path,
            error=None,
            completed_at=datetime.now().isoformat(timespec='seconds'),
        )

        task = db.get_generate_task(task_id)
        if task:
            params_data = json.loads(task['params']) if isinstance(task['params'], str) else task['params']
            params_data['review_result'] = {
                'reserved': True,
                'message': '生成后自动审查功能已预留，当前版本暂不执行。',
                'executed': False,
            }
            cursor = db.conn.cursor()
            cursor.execute(
                'UPDATE generate_tasks SET params = ? WHERE id = ?',
                (json.dumps(params_data, ensure_ascii=False), task_id)
            )
            db.conn.commit()

    except Exception as e:
        import traceback
        traceback.print_exc()
        db.update_generate_task(
            task_id,
            status='failed',
            error=str(e),
            progress_stage='failed',
            progress_message='生成失败',
            completed_at=datetime.now().isoformat(timespec='seconds'),
        )


def _has_source_docx(template: dict) -> bool:
    metadata = template.get("metadata") or {}
    return bool(metadata.get("source_docx_path") or metadata.get("source_path"))


def _decorate_generate_task(task: dict) -> dict:
    labels = {
        'pending': ('等待中', 'warning'),
        'processing': ('生成中', 'info'),
        'generated': ('已生成', 'success'),
        'completed': ('已完成', 'success'),
        'failed': ('失败', 'danger'),
        'review_failed': ('审查未通过', 'danger'),
        'canceled': ('已停止', 'default'),
    }
    label, badge_class = labels.get(task.get('status'), (task.get('status') or '未知', 'default'))
    decorated = dict(task)
    decorated['status_label'] = label
    decorated['badge_class'] = badge_class
    return decorated
