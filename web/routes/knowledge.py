"""Knowledge base routes."""
from flask import Blueprint, redirect, render_template, url_for

bp = Blueprint("knowledge", __name__)


@bp.route("/")
def index():
    """Redirect to the visible knowledge base entry."""
    return redirect(url_for("knowledge.external"))


@bp.route("/external/")
def external():
    """Render the reserved external knowledge base page."""
    from web.option_registry import get_specialty_groups

    return render_template(
        "knowledge_external.html",
        active_page="knowledge_external",
        specialty_groups=get_specialty_groups("generate"),
    )
