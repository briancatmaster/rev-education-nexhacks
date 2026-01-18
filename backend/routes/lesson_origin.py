from flask import Blueprint, jsonify, request
from pydantic import BaseModel, ValidationError

from services.lesson_origin_service import generate_learning_origin, generate_skill_map

lesson_origin_bp = Blueprint("lesson_origin", __name__)


class OriginRequest(BaseModel):
    background: str
    target: str


@lesson_origin_bp.route("/generate-skills", methods=["POST"])
def generate_skills():
    try:
        data = OriginRequest(**request.json)
        skills = generate_skill_map(data.background, data.target)
        return jsonify({"success": True, "skills": skills}), 200
    except ValidationError as error:
        return (
            jsonify({"success": False, "error": "Validation error", "details": error.errors()}),
            400,
        )
    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 500


@lesson_origin_bp.route("/generate-plan", methods=["POST"])
def generate_plan():
    try:
        data = OriginRequest(**request.json)
        plan = generate_learning_origin(data.background, data.target, request.json.get("skills", []))
        return jsonify({"success": True, "plan": plan}), 200
    except ValidationError as error:
        return (
            jsonify({"success": False, "error": "Validation error", "details": error.errors()}),
            400,
        )
    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 500
