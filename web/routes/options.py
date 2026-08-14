"""Shared option APIs for model selection and professional reference cases."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

bp = Blueprint("options", __name__)


@bp.route("/api/models")
def models():
    from web.option_registry import get_model_options

    usage = request.args.get("usage", "both")
    return jsonify({"models": get_model_options(usage)})


@bp.route("/api/specialties")
def specialties():
    from web.option_registry import get_specialties, get_specialty_groups

    usage = request.args.get("usage") or None
    return jsonify({
        "specialties": get_specialties(usage),
        "groups": get_specialty_groups(usage),
    })
