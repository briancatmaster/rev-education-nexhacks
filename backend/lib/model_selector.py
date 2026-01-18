MODEL_TIERS = {
    "mini": [
        "google/gemini-flash-1.5-8b",
        "meta-llama/llama-3-8b-instruct",
    ],
    "balanced": [
        "anthropic/claude-sonnet-4",
        "openai/gpt-4o-mini",
    ],
    "advanced": [
        "anthropic/claude-opus-4",
        "openai/gpt-4-turbo",
    ],
    "reasoning": [
        "anthropic/claude-sonnet-4:thinking",
        "deepseek/deepseek-r1",
    ],
}


def select_model(task_type: str) -> str:
    task_model_map = {
        "simple_generation": MODEL_TIERS["mini"][0],
        "lesson_planning": MODEL_TIERS["balanced"][0],
        "curriculum_design": MODEL_TIERS["advanced"][0],
        "assessment_creation": MODEL_TIERS["balanced"][0],
        "content_research": MODEL_TIERS["reasoning"][0],
    }
    return task_model_map.get(task_type, MODEL_TIERS["balanced"][0])
