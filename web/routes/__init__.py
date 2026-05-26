"""
Route handlers for the web application.
"""
from flask import Blueprint

bp = Blueprint('index', __name__)

@bp.route('/')
def index():
    return "Index page - under construction"
