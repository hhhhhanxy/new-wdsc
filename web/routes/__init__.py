"""
Route handlers for the web application.
"""
from flask import Blueprint, render_template, current_app

bp = Blueprint('index', __name__)


@bp.route('/')
def index():
    db = current_app.db
    recent = db.get_recent_review_tasks(limit=5)
    completed = [t for t in recent if t['status'] == 'completed']
    processing = [t for t in recent if t['status'] == 'processing']
    pending = [t for t in recent if t['status'] == 'pending']

    stats = {
        'pending': len(pending),
        'processing': len(processing),
        'completed': len(completed),
        'pass_rate': 89,
    }
    return render_template('index.html', active_page='index', stats=stats, recent_tasks=recent)
