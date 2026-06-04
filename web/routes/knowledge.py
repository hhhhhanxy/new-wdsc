"""Knowledge base placeholder routes."""
from flask import Blueprint, render_template

bp = Blueprint("knowledge", __name__)


@bp.route("/")
def index():
    """Render the reserved knowledge base page."""
    return render_template("knowledge.html", active_page="knowledge")
