"""
Route handlers for the web application.
"""
from flask import Blueprint, render_template, current_app, request

bp = Blueprint('index', __name__)


@bp.route('/')
def index():
    db = current_app.db
    all_recent = db.get_recent_review_tasks(limit=100)
    completed = [t for t in all_recent if t['status'] == 'completed']
    processing = [t for t in all_recent if t['status'] == 'processing']
    pending = [t for t in all_recent if t['status'] == 'pending']

    stats = {
        'pending': len(pending),
        'processing': len(processing),
        'completed': len(completed),
        'pass_rate': 89,
    }
    from web.routes.review import _recent_review_page_data
    recent_page = request.args.get("recent_page", 1, type=int)
    recent, recent_pagination = _recent_review_page_data(db, recent_page, base_url="/")
    return render_template(
        'index.html',
        active_page='index',
        stats=stats,
        recent_tasks=recent,
        recent_pagination=recent_pagination,
    )
