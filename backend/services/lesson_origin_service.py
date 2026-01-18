import json
import uuid

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from lib.langchain_openrouter import get_llm
from lib.model_selector import select_model

ALLOWED_TYPES = {"reading", "video", "problem", "lab"}


def _normalize_plan(plan: dict) -> dict:
    plan.setdefault("id", f"plan-{uuid.uuid4().hex[:8]}")
    plan.setdefault("units", [])

    normalized_units = []
    for index, unit in enumerate(plan.get("units", [])[:5]):
        unit_id = unit.get("id") or f"unit-{index + 1}"
        lessons = []
        for lesson_index, lesson in enumerate(unit.get("lessons", [])[:6]):
            lesson_type = lesson.get("type", "reading")
            if lesson_type not in ALLOWED_TYPES:
                lesson_type = "reading"
            lessons.append(
                {
                    "id": lesson.get("id") or f"lesson-{index + 1}-{lesson_index + 1}",
                    "title": lesson.get("title", "Lesson"),
                    "type": lesson_type,
                }
            )
        normalized_units.append(
            {
                "id": unit_id,
                "title": unit.get("title", f"Unit {index + 1}"),
                "description": unit.get("description", ""),
                "lessons": lessons,
            }
        )

    plan["units"] = normalized_units
    return plan


def generate_skill_map(background: str, target: str) -> dict:
    model = select_model("lesson_planning")
    llm = get_llm(model_name=model, temperature=0.4)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are an expert curriculum designer. Output JSON only (no markdown).
Identify prerequisite skills and subskills. Do not generate lessons or sources.""",
            ),
            (
                "human",
                """Create a skill map for:
Background: {background}
Target topic: {target}

JSON shape:
{{
  "skills": [
    {{
      "id": "string",
      "name": "string",
      "description": "string",
      "subskills": ["string"]
    }}
  ]
}}

Constraints:
- 6 to 10 skills total
- Each skill has 2 to 4 subskills
- Keep names concise and academic
""",
            ),
        ]
    )

    chain = prompt | llm | StrOutputParser()
    result = chain.invoke({"background": background, "target": target})

    try:
        skill_map = json.loads(result)
    except json.JSONDecodeError:
        skill_map = {
            "skills": [
                {
                    "id": "skill-1",
                    "name": "Core math foundations",
                    "description": "Key calculus and linear algebra concepts.",
                    "subskills": ["Derivatives", "Matrix calculus", "Eigenvalues"],
                },
                {
                    "id": "skill-2",
                    "name": "Optimization basics",
                    "description": "Gradient-based learning fundamentals.",
                    "subskills": ["Gradient descent", "Loss surfaces", "Regularization"],
                },
            ]
        }

    return skill_map


def generate_learning_origin(background: str, target: str, skills: list[dict]) -> dict:
    model = select_model("lesson_planning")
    llm = get_llm(model_name=model, temperature=0.5)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are an expert curriculum designer. You sequence learning steps but do not generate sources or content.
Return JSON only, no markdown. Keep it concise and structured for a UI.""",
            ),
            (
                "human",
                """Build a lesson path JSON for:
Background: {background}
Target topic: {target}
Skill inputs: {skills}

JSON shape:
{{
  "id": "string",
  "background": "string",
  "target": "string",
  "skills": [
    {{ "id": "string", "name": "string", "level": "string" }}
  ],
  "units": [
    {{
      "id": "string",
      "title": "string",
      "description": "string",
      "lessons": [
        {{ "id": "string", "title": "string", "type": "reading|video|problem|lab" }}
      ]
    }}
  ]
}}

Constraints:
- 3 to 5 units, 3 to 6 lessons each
- No sources or problems text
- Titles should hint at embedded sources and checks for understanding
- Use short, punchy titles
""",
            ),
        ]
    )

    chain = prompt | llm | StrOutputParser()
    result = chain.invoke(
        {
            "background": background,
            "target": target,
            "skills": json.dumps(skills),
        }
    )

    try:
        plan = json.loads(result)
    except json.JSONDecodeError:
        plan = {
            "id": f"plan-{uuid.uuid4().hex[:8]}",
            "background": background,
            "target": target,
            "skills": skills,
            "units": [
                {
                    "id": "unit-1",
                    "title": "Foundational context",
                    "description": "Reframe the topic using the learner's background.",
                    "lessons": [
                        {"id": "lesson-1", "title": "Source overview", "type": "reading"},
                        {"id": "lesson-2", "title": "Concept check", "type": "problem"},
                        {"id": "lesson-3", "title": "Applied lab", "type": "lab"},
                    ],
                }
            ],
        }

    plan["background"] = background
    plan["target"] = target
    plan["skills"] = skills

    return _normalize_plan(plan)
