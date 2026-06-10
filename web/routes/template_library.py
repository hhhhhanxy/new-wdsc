"""Generation template library routes."""
import os
import uuid
from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, request

from templates.docx_template_parser import DocxTemplateParser
from templates.template_manager import TemplateManager

bp = Blueprint("template_library", __name__)


@bp.route("/")
def index():
    return render_template("template_library.html", active_page="template_library")


@bp.route("/api/templates")
def api_templates():
    manager = TemplateManager()
    return jsonify({"templates": manager.list_template_dicts()})


@bp.route("/api/templates/<template_id>")
def api_template_detail(template_id: str):
    manager = TemplateManager()
    template = manager.get_template(template_id)
    if not template:
        return jsonify({"error": f"模板不存在: {template_id}"}), 404
    return jsonify(manager.serialize_template(template))


@bp.route("/api/parse", methods=["POST"])
def api_parse_template():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "请上传 DOCX 模板文件"}), 400
    if not file.filename.lower().endswith(".docx"):
        return jsonify({"error": "仅支持 DOCX 模板文件"}), 400

    template_id = f"template_{uuid.uuid4().hex[:8]}"
    template_dir = Path(current_app.config["UPLOAD_FOLDER"]) / "templates" / template_id
    template_dir.mkdir(parents=True, exist_ok=True)
    path = template_dir / "source.docx"
    file.save(path)

    parsed = DocxTemplateParser().parse(str(path))
    parsed["id"] = template_id
    parsed["metadata"] = {
        "template_asset_id": template_id,
        "source_filename": file.filename,
        "source_path": os.path.relpath(path, Path(current_app.root_path).parent),
        "source_docx_path": os.path.relpath(path, Path(current_app.root_path).parent),
    }
    return jsonify(parsed)


@bp.route("/api/templates", methods=["POST"])
def api_create_template():
    data = request.get_json() or {}
    name = str(data.get("name", "")).strip()
    if not name:
        return jsonify({"error": "模板名称不能为空"}), 400
    chapters = data.get("chapters") or []
    if not chapters:
        return jsonify({"error": "模板章节不能为空"}), 400

    manager = TemplateManager()
    template = manager.create_template(
        name=name,
        description=data.get("description", ""),
        chapters=chapters,
        metadata=data.get("metadata") or {},
        source_type=data.get("source_type", "uploaded_docx"),
        template_id=data.get("id") or None,
    )
    return jsonify({"ok": True, "template": manager.serialize_template(template)})


@bp.route("/api/templates/<template_id>", methods=["PUT"])
def api_update_template(template_id: str):
    data = request.get_json() or {}
    manager = TemplateManager()
    template = manager.update_template(template_id, data)
    if not template:
        return jsonify({"error": "模板不存在或内置模板不可编辑"}), 404
    return jsonify({"ok": True, "template": manager.serialize_template(template)})


@bp.route("/api/templates/<template_id>", methods=["DELETE"])
def api_delete_template(template_id: str):
    manager = TemplateManager()
    if not manager.delete_template(template_id):
        return jsonify({"error": "模板不存在"}), 404
    return jsonify({"ok": True})
