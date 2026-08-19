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
        specialty_resource_groups=overview['specialty_resource_groups'],
    )


@bp.route('/healthz')
def healthz():
    """Lightweight health check for the local web service."""
    return jsonify({"ok": True, "service": "web"})


def _build_company_overview(db) -> dict:
    """Build company-level resource and usage statistics for the home page."""
    from templates.template_manager import TemplateManager
    from rules.loaders.rule_loader import RuleLoader
    from web.routes.rules import _rule_set_meta
    from web.option_registry import get_reference_cases, get_specialty_groups

    templates = TemplateManager().list_template_dicts()
    reference_case_count = 0
    rules = RuleLoader.load_all_rules("default", include_extensions=False)
    template_counts = {}
    case_counts = {}
    for template in templates:
        metadata = template.get("metadata") or {}
        specialty_id = str(metadata.get("specialty_id") or "").strip()
        if not specialty_id:
            continue
        template_counts[specialty_id] = template_counts.get(specialty_id, 0) + 1
    rule_counts = {}
    for rule in rules:
        source_meta = _rule_set_meta(getattr(rule, "source", "") or "")
        specialty_id = str(source_meta.get("specialty_id") or "").strip()
        if specialty_id:
            rule_counts[specialty_id] = rule_counts.get(specialty_id, 0) + 1

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
            specialty_cases = get_reference_cases(key)
            reference_case_count += len(specialty_cases)
            case_counts[key] = len(specialty_cases)
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
    specialty_resource_groups = []
    for group in specialty_groups:
        resources = []
        for specialty in group.get("specialties") or []:
            key = str(specialty.get("id") or "").strip()
            if not key:
                continue
            resources.append({
                "name": str(specialty.get("name") or key),
                "template_count": template_counts.get(key, 0),
                "rule_count": rule_counts.get(key, 0),
                "case_count": case_counts.get(key, 0),
            })
        if resources:
            specialty_resource_groups.append({
                "id": str(group.get("id") or ""),
                "name": str(group.get("name") or "未分组"),
                "resources": resources,
            })

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
        "specialty_resource_groups": specialty_resource_groups,
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
