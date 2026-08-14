"""
Route handlers for the web application.
"""
import json

from flask import Blueprint, render_template, current_app, jsonify

bp = Blueprint('index', __name__)


@bp.route('/')
def index():
    db = current_app.db
    overview = _build_company_overview(db)
    return render_template(
        'index.html',
        active_page='index',
        stats=overview['stats'],
        specialty_issue_groups=overview['specialty_issue_groups'],
        max_specialty_issues=overview['max_specialty_issues'],
    )


@bp.route('/healthz')
def healthz():
    """Lightweight health check for the local web service."""
    return jsonify({"ok": True, "service": "web"})


def _build_company_overview(db) -> dict:
    """Build company-level resource and usage statistics for the home page."""
    from templates.template_manager import TemplateManager
    from rules.loaders.rule_loader import RuleLoader
    from web.option_registry import get_specialty_groups

    templates = TemplateManager().list_template_dicts()
    reference_case_count = sum(
        len((template.get("metadata") or {}).get("reference_cases") or [])
        for template in templates
    )
    rules = RuleLoader.load_all_rules("default", include_extensions=False)

    review_total = db.count_review_tasks()
    generate_total = db.count_generate_tasks()
    review_tasks = db.get_recent_review_tasks(limit=review_total or 1)
    generate_tasks = db.get_recent_generate_tasks(limit=generate_total or 1)
    completed_reviews = [task for task in review_tasks if task.get("status") == "completed"]
    completed_generates = [task for task in generate_tasks if task.get("status") == "completed"]
    specialty_groups = get_specialty_groups("review")
    specialty_names = {
        str(specialty.get("id") or "").strip(): str(specialty.get("name") or "").strip()
        for group in specialty_groups
        for specialty in (group.get("specialties") or [])
        if str(specialty.get("id") or "").strip()
    }

    total_issues = 0
    issues_by_specialty = {}
    for task in completed_reviews:
        issues = _review_issue_count(task)
        total_issues += issues
        key = str(task.get("specialty_id") or "").strip() or "uncategorized"
        if key == "uncategorized":
            key = "actuation"
        name = str(task.get("specialty_name") or "").strip() or specialty_names.get(key) or key
        current = issues_by_specialty.setdefault(key, {"name": name, "count": 0})
        current["count"] += issues

    specialty_issue_groups = []
    for group in specialty_groups:
        items = []
        for specialty in group.get("specialties") or []:
            key = str(specialty.get("id") or "").strip()
            if not key:
                continue
            item = issues_by_specialty.get(key) or {
                "name": str(specialty.get("name") or key),
                "count": 0,
            }
            items.append(item)
        if items:
            specialty_issue_groups.append({
                "id": str(group.get("id") or ""),
                "name": str(group.get("name") or "未分组"),
                "stats": items,
            })
    all_stats = [
        item
        for group in specialty_issue_groups
        for item in group.get("stats") or []
    ]
    max_specialty_issues = max([int(item.get("count") or 0) for item in all_stats] or [0])

    return {
        "stats": {
            "template_count": len(templates),
            "rule_count": len(rules),
            "reference_case_count": reference_case_count,
            "generate_report_count": len(completed_generates),
            "review_report_count": len(completed_reviews),
            "total_issue_count": total_issues,
        },
        "specialty_issue_groups": specialty_issue_groups,
        "max_specialty_issues": max_specialty_issues,
    }


def _review_issue_count(task: dict) -> int:
    try:
        result = json.loads(task.get("result") or "{}")
    except (TypeError, json.JSONDecodeError):
        result = {}
    if isinstance(result, dict):
        try:
            return int(result.get("total_issues") or 0)
        except (TypeError, ValueError):
            return 0
    return 0
