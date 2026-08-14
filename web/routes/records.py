"""Unified task records page."""
import json
import os
from flask import Blueprint, current_app, render_template, request

from web.time_utils import format_beijing_time

bp = Blueprint("records", __name__)

PAGE_SIZE = 10
RUNNING_STATUSES = {"pending", "processing", "paused"}


def _review_groups():
    from rules.loaders.rule_loader import RuleLoader
    from web.routes.rules import _group_rules_by_source

    rules = RuleLoader.load_all_rules("default", include_extensions=False)
    groups, _, _ = _group_rules_by_source(rules)
    return groups


def _review_items(db):
    from web.routes.review import decorate_recent_review_tasks

    total = db.count_review_tasks()
    groups = _review_groups()
    tasks = decorate_recent_review_tasks(db.get_recent_review_tasks(limit=total or 1), groups)
    items = []
    for task in tasks:
        is_running = task.get("status") in RUNNING_STATUSES and not task.get("stale")
        items.append({
            "kind": "review",
            "kind_label": "文档审查",
            "id": task.get("id"),
            "name": task.get("filename") or "未命名审查文档",
            "source": task.get("rule_set_label") or "全部规则",
            "model_name": task.get("model_name") or "系统默认",
            "specialty_name": task.get("specialty_name") or "",
            "document_kind_name": task.get("document_kind_name") or "",
            "source_generate_task_id": task.get("source_generate_task_id"),
            "reference_case_names": [],
            "status": task.get("status"),
            "status_label": task.get("status_label") or "未知",
            "badge_class": task.get("badge_class") or "default",
            "progress": int(task.get("progress") or 0),
            "progress_message": task.get("progress_message") or task.get("error_preview") or "",
            "created_at": task.get("created_at") or "",
            "created_at_display": task.get("created_at_display") or format_beijing_time(task.get("created_at") or ""),
            "completed_at_display": task.get("completed_at_display") or format_beijing_time(task.get("completed_at") or ""),
            "summary": _review_summary(task),
            "is_running": is_running,
            "is_paused": task.get("status") == "paused",
            "stale": bool(task.get("stale")),
            "can_download": task.get("status") == "completed",
            "can_delete": task.get("status") not in RUNNING_STATUSES or bool(task.get("stale")),
        })
    return items


def _generate_items(db):
    from web.routes.generate import _decorate_generate_task

    total = db.count_generate_tasks()
    tasks = [_decorate_generate_task(task) for task in db.get_recent_generate_tasks(limit=total or 1)]
    items = []
    for task in tasks:
        result_path = task.get("result_path") or ""
        filename = os.path.basename(result_path) if result_path else (task.get("template_name") or "未命名生成文档")
        is_running = task.get("status") in RUNNING_STATUSES
        items.append({
            "kind": "generate",
            "kind_label": "文档生成",
            "id": task.get("id"),
            "name": filename,
            "source": task.get("template_name") or task.get("doc_type") or "生成模板",
            "model_name": task.get("model_name") or "系统默认",
            "specialty_name": task.get("specialty_name") or "",
            "document_kind_name": task.get("document_kind_name") or "",
            "reference_case_names": _reference_case_names(task.get("reference_cases")),
            "status": task.get("status"),
            "status_label": task.get("status_label") or "未知",
            "badge_class": task.get("badge_class") or "default",
            "progress": int(task.get("progress") or 0),
            "progress_message": task.get("progress_message") or task.get("error") or "",
            "created_at": task.get("created_at") or "",
            "created_at_display": format_beijing_time(task.get("created_at") or ""),
            "completed_at_display": format_beijing_time(task.get("completed_at") or ""),
            "summary": task.get("error") or task.get("progress_message") or "",
            "is_running": is_running,
            "is_paused": task.get("status") == "paused",
            "stale": False,
            "can_download": task.get("status") == "completed" and bool(result_path),
            "can_delete": task.get("status") not in RUNNING_STATUSES,
        })
    return items


def _reference_case_names(raw):
    try:
        cases = json.loads(raw or "[]") if isinstance(raw, str) else (raw or [])
    except (TypeError, json.JSONDecodeError):
        cases = []
    return [
        str(item.get("name") or item.get("id"))
        for item in cases
        if isinstance(item, dict) and (item.get("name") or item.get("id"))
    ]


def _review_summary(task):
    if task.get("status") == "completed":
        total = task.get("total_issues")
        errors = task.get("errors")
        warnings = task.get("warnings")
        if total is not None:
            return f"共 {total} 个问题，错误 {errors or 0} 个，警告 {warnings or 0} 个"
    return task.get("error_preview") or task.get("progress_message") or ""


def _match_status(item, status_filter):
    if status_filter == "all":
        return True
    if status_filter == "running":
        return item["status"] in RUNNING_STATUSES and not item.get("stale")
    if status_filter == "finished":
        return item["status"] not in RUNNING_STATUSES
    if status_filter == "stale":
        return bool(item.get("stale"))
    return item["status"] == status_filter


@bp.route("/")
def index():
    db = current_app.db
    type_filter = request.args.get("type", "all")
    status_filter = request.args.get("status", "all")
    keyword = (request.args.get("q") or "").strip()
    page = max(1, request.args.get("page", 1, type=int))

    review_items = _review_items(db)
    generate_items = _generate_items(db)
    stats_items = review_items + generate_items

    items = []
    if type_filter in {"all", "review"}:
        items.extend(review_items)
    if type_filter in {"all", "generate"}:
        items.extend(generate_items)

    if keyword:
        lowered = keyword.lower()
        items = [
            item for item in items
            if lowered in (item["name"] or "").lower()
            or lowered in (item["source"] or "").lower()
            or lowered in (item.get("model_name") or "").lower()
            or lowered in (item.get("specialty_name") or "").lower()
            or lowered in (item.get("document_kind_name") or "").lower()
            or any(lowered in name.lower() for name in item.get("reference_case_names") or [])
            or lowered in (item["status_label"] or "").lower()
        ]

    items = [item for item in items if _match_status(item, status_filter)]
    items.sort(key=lambda item: item.get("created_at") or "", reverse=True)

    total = len(items)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(page, total_pages)
    start_index = (page - 1) * PAGE_SIZE
    page_items = items[start_index:start_index + PAGE_SIZE]

    stats = {
        "all": len(stats_items),
        "review": db.count_review_tasks(),
        "generate": db.count_generate_tasks(),
        "running": sum(1 for item in stats_items if item["status"] in RUNNING_STATUSES and not item.get("stale")),
    }
    pagination = {
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "start": start_index + 1 if total else 0,
        "end": min(start_index + len(page_items), total),
        "has_prev": page > 1,
        "has_next": page < total_pages,
    }
    return render_template(
        "records.html",
        active_page="records",
        records=page_items,
        stats=stats,
        pagination=pagination,
        filters={"type": type_filter, "status": status_filter, "q": keyword},
    )
