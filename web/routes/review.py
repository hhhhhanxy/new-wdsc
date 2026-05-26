"""
Review routes for the web application.
"""
from flask import Blueprint

bp = Blueprint('review', __name__)

@bp.route('/')
def index():
    return "Review page - under construction"
