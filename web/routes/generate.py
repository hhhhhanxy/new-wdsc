"""
Generate routes for the web application.
"""
import os
import json
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from flask import Blueprint, render_template, request, jsonify, send_file, current_app
from werkzeug.utils import secure_filename

bp = Blueprint('generate', __name__)
RUNNING_STATUSES = {'pending', 'processing', 'paused'}


class GenerationTaskCanceled(Exception):
    """Raised when a generation task is stopped by the user."""

    is_task_control = True


@bp.route('/')
def index():
    return render_template('generate.html', active_page='generate')


@bp.route('/api/templates')
def templates():
    """Return all templates and identify which ones have a source DOCX."""
    from templates.template_manager import TemplateManager

    manager = TemplateManager()
    templates = manager.list_template_dicts()
    for template in templates:
        template["can_generate"] = _has_source_docx(template)
        template["unavailable_reason"] = "" if template["can_generate"] else "缺少原始 DOCX 模板文件"
    return jsonify({"templates": templates})


@bp.route('/api/templates/<template_id>')
def template_detail(template_id):
    """Return one template with its chapter structure."""
    from templates.template_manager import TemplateManager

    manager = TemplateManager()
    template = manager.get_template(template_id)
    if not template:
        return jsonify({"error": f"模板不存在: {template_id}"}), 404
    return jsonify(manager.serialize_template(template))


@bp.route('/api/supplement-doc', methods=['POST'])
@bp.route('/api/reference-doc', methods=['POST'])
def upload_supplement_doc():
    """Upload and extract text from a DOCX supplement material file."""
    file = request.files.get('file')
    if not file or not file.filename:
        return jsonify({'error': '请选择要上传的 Word 文档'}), 400

    filename = secure_filename(file.filename)
    if not filename.lower().endswith('.docx'):
        return jsonify({'error': '当前仅支持 .docx 格式的 Word 文档'}), 400

    reference_dir = Path(current_app.config['UPLOAD_FOLDER']) / 'generation_references'
    reference_dir.mkdir(parents=True, exist_ok=True)
    saved_name = f"{uuid.uuid4().hex}_{filename}"
    saved_path = reference_dir / saved_name
    file.save(saved_path)

    try:
        extracted = _extract_docx_reference_text(saved_path)
    except Exception as exc:
        saved_path.unlink(missing_ok=True)
        return jsonify({'error': f'补充材料解析失败：{exc}'}), 400

    if not extracted.strip():
        return jsonify({'error': '补充材料未解析到可用文本'}), 400

    return jsonify({
        'filename': filename,
        'saved_path': str(saved_path),
        'text': extracted,
        'chars': len(extracted),
    })


@bp.route('/start', methods=['POST'])
def start():
    data = request.get_json()
    return _create_generation_task(data)


@bp.route('/status/<int:task_id>')
def status(task_id):
    task = current_app.db.get_generate_task(task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    return jsonify(dict(task))


@bp.route('/pause/<int:task_id>', methods=['POST'])
def pause(task_id):
    db = current_app.db
    task = db.get_generate_task(task_id)
    if not task:
        return jsonify({'error': '生成任务不存在'}), 404
    if task.get('status') != 'processing':
        return jsonify({'error': '只有生成中的任务可以暂停'}), 400
    db.update_generate_task(
        task_id,
        status='paused',
        progress_stage='paused',
        progress_message='生成已暂停，点击继续后恢复',
    )
    return jsonify({'ok': True, 'status': 'paused', 'progress': task.get('progress', 0)})


@bp.route('/resume/<int:task_id>', methods=['POST'])
def resume(task_id):
    db = current_app.db
    task = db.get_generate_task(task_id)
    if not task:
        return jsonify({'error': '生成任务不存在'}), 404
    if task.get('status') != 'paused':
        return jsonify({'error': '只有已暂停的生成任务可以继续'}), 400
    db.update_generate_task(
        task_id,
        status='processing',
        progress_stage='filling',
        progress_message='正在恢复文档生成',
    )
    return jsonify({'ok': True, 'status': 'processing', 'progress': task.get('progress', 0)})


@bp.route('/cancel/<int:task_id>', methods=['POST'])
def cancel(task_id):
    db = current_app.db
    task = db.get_generate_task(task_id)
    if not task:
        return jsonify({'error': '生成任务不存在'}), 404
    if task.get('status') not in RUNNING_STATUSES:
        return jsonify({'error': '只有等待中、生成中或已暂停的任务可以停止'}), 400
    db.update_generate_task(
        task_id,
        status='canceled',
        progress_stage='canceled',
        progress_message='用户手动停止生成',
        error='用户手动停止生成任务',
        completed_at=datetime.now().isoformat(timespec='seconds'),
    )
    return jsonify({'ok': True, 'status': 'canceled', 'progress': task.get('progress', 0)})


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


@bp.route('/rerun/<int:task_id>', methods=['POST'])
def rerun(task_id):
    task = current_app.db.get_generate_task(task_id)
    if not task:
        return jsonify({'error': '生成记录不存在'}), 404
    if task.get('status') in RUNNING_STATUSES:
        return jsonify({'error': '该生成任务仍在执行，不能重新生成'}), 400
    try:
        params_data = json.loads(task.get('params') or '{}')
    except (TypeError, json.JSONDecodeError):
        return jsonify({'error': '原始生成参数不可用，不能重新生成'}), 400
    template_id = params_data.get('template_id') or task.get('doc_type')
    title = params_data.get('title') or f"{task.get('template_name') or '生成文档'}_重新生成"
    inputs = params_data.get('inputs') or {}
    rerun_data = {
        'template_id': template_id,
        'title': title,
        'inputs': inputs,
        'rerun_from': task_id,
    }
    return _create_generation_task(rerun_data)


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
    if task.get('status') in RUNNING_STATUSES:
        return jsonify({'error': '生成任务仍在执行，完成或失败后再删除'}), 400
    deleted = current_app.db.delete_generate_task(task_id)
    return jsonify({'ok': True, 'deleted': deleted})


def _create_generation_task(data: dict):
    db = current_app.db
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
    dynamic_values = inputs.get('dynamic_fields') or {}
    missing_dynamic = [
        field.label
        for field in template.input_fields
        if field.required and not str(dynamic_values.get(field.key, '')).strip()
    ]
    if missing_dynamic:
        return jsonify({'error': f"请填写模板必填项：{'、'.join(missing_dynamic)}"}), 400
    inputs['dynamic_field_definitions'] = [
        {
            'key': field.key,
            'label': field.label,
            'chapter_keys': field.chapter_keys,
            'placeholder_tokens': field.placeholder_tokens,
        }
        for field in template.input_fields
    ]
    data['inputs'] = inputs
    template_dict = manager.serialize_template(template)
    if not _has_source_docx(template_dict):
        return jsonify({'error': '该模板没有原始 DOCX 文件，请先在生成模板库中上传模板'}), 400

    params = {
        'title': data['title'],
        'template_id': template.template_id,
        'template_name': template.name,
        'template_version': (template.metadata or {}).get('version', 1),
        'inputs': inputs,
        'rerun_from': data.get('rerun_from'),
        'auto_review': False,
        'review_result': {
            'reserved': True,
            'message': '生成后自动审查功能已预留，当前版本暂不执行。',
        },
    }

    new_task_id = db.create_generate_task(
        doc_type=template.doc_type.value if template.doc_type else template.template_id,
        template_name=template.name,
        params=params
    )

    thread = threading.Thread(
        target=run_generate_task,
        args=(new_task_id, data, current_app.config['UPLOAD_FOLDER'], db)
    )
    thread.daemon = True
    thread.start()

    return jsonify({'task_id': new_task_id, 'rerun_from': data.get('rerun_from')})


def run_generate_task(task_id, data, upload_folder, db):
    """Execute document generation task."""
    try:
        _wait_if_generation_paused(db, task_id)
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
        generation_mode = str(inputs.get('generation_mode') or 'smart')

        llm_client = None
        if generation_mode == 'smart':
            db.update_generate_task(
                task_id,
                progress=18,
                progress_stage='llm',
                progress_message=f'正在初始化大模型客户端：{settings.llm_model}',
            )
            llm_client = LLMClientFactory.create_client(settings.llm_provider)
        else:
            db.update_generate_task(
                task_id,
                progress=18,
                progress_stage='prepare',
                progress_message='已选择模板填充模式，本次不调用大模型',
            )

        def update_chapter_progress(current, total, chapter):
            _wait_if_generation_paused(db, task_id)
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
            control_callback=lambda: _wait_if_generation_paused(db, task_id),
        )

        if result.error:
            raise RuntimeError(result.error)

        _wait_if_generation_paused(db, task_id)
        task = db.get_generate_task(task_id)
        if task:
            params_data = json.loads(task['params']) if isinstance(task['params'], str) else task['params']
            params_data['quality_result'] = result.quality_result
            params_data['generation_meta'] = result.generation_meta
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

        _wait_if_generation_paused(db, task_id)
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

    except GenerationTaskCanceled as e:
        task = db.get_generate_task(task_id)
        if task and task.get('status') != 'canceled':
            db.update_generate_task(
                task_id,
                status='canceled',
                error=str(e),
                progress_stage='canceled',
                progress_message=str(e),
                completed_at=datetime.now().isoformat(timespec='seconds'),
            )

    except Exception as e:
        import traceback
        traceback.print_exc()
        task = db.get_generate_task(task_id)
        if not task or task.get('status') == 'canceled':
            return
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


def _wait_if_generation_paused(db, task_id: int):
    """Block the worker while paused and stop it cooperatively when canceled."""
    while True:
        task = db.get_generate_task(task_id)
        if not task:
            raise GenerationTaskCanceled("生成任务已删除")
        status = task.get('status')
        if status == 'canceled':
            raise GenerationTaskCanceled("生成任务已停止")
        if status != 'paused':
            return
        time.sleep(1)


def _extract_docx_reference_text(path: Path, max_chars: int = 12000) -> str:
    from docx import Document

    doc = Document(str(path))
    parts = []
    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if text:
            parts.append(text)
    for table_index, table in enumerate(doc.tables, start=1):
        rows = []
        for row in table.rows:
            cells = [cell.text.strip().replace('\n', ' ') for cell in row.cells]
            if any(cells):
                rows.append(' | '.join(cells))
        if rows:
            parts.append(f"表格{table_index}：\n" + "\n".join(rows))
    text = "\n".join(parts)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n...（补充材料内容较长，已截取前12000字）"
    return text


def _decorate_generate_task(task: dict) -> dict:
    labels = {
        'pending': ('等待中', 'warning'),
        'processing': ('生成中', 'info'),
        'paused': ('已暂停', 'warning'),
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
