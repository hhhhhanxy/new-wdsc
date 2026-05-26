"""
Generate routes for the web application.
"""
from flask import Blueprint

bp = Blueprint('generate', __name__)

@bp.route('/')
def index():
    return "Generate page - under construction"
