"""
Route handlers for the web application.
"""
from flask import Blueprint, render_template, current_app, jsonify

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
    return render_template(
        'index.html',
        active_page='index',
        stats=stats,
    )


@bp.route('/healthz')
def healthz():
    """Lightweight health check for the local web service."""
    return jsonify({"ok": True, "service": "web"})
