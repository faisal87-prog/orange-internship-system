"""AI Roadmap Generator — OpenAI call #2."""

from __future__ import annotations

import json
from typing import Any

from services.ai import client as openai_client
from services.ai import config
from services.ai.exceptions import AIInvalidOutputError
from services.ai.schemas import GeneratedRoadmap
from services.ai.validators import validate_generated_roadmap

ROADMAP_GENERATOR_SYSTEM = """
You are an internship roadmap generator.
Generate a complete structured learning roadmap for mentors to review.
The application will save it as a Draft separately — do NOT put DRAFT/PUBLISHED/
ARCHIVED in the roadmap title.

Follow the Final Roadmap Generation Prompt exactly.
Also use the canonical structured context (including extracted reference material)
as authoritative source data.
Do not invent unavailable facts or unsupported technologies.
Do not create scores, mentor feedback, or task assignment statuses.
Use difficulty values EASY, MEDIUM, or HARD only.
Use requirement_type values REQUIRED or OPTIONAL only.
Produce multiple meaningful tasks for each week (at least one; prefer several).
Respect program start/end dates and duration_weeks exactly.
""".strip()


def generate_roadmap_structure(
    *,
    context: dict[str, Any],
    final_roadmap_generation_prompt: str,
) -> GeneratedRoadmap:
    """
    Call OpenAI to generate the roadmap JSON using the exact previewed Final Prompt.

    Retries once on invalid structured/business output using the same prompt.
    """
    user_payload = {
        "final_roadmap_generation_prompt": final_roadmap_generation_prompt,
        "canonical_context": context,
        "output_requirements": {
            "roadmap_fields": ["title", "summary", "number_of_weeks", "weeks"],
            "week_fields": [
                "week_number",
                "weekly_focus",
                "learning_objectives",
                "expected_skills_gained",
                "mentor_notes",
                "tasks",
            ],
            "task_fields": [
                "title",
                "description",
                "difficulty",
                "estimated_time_minutes",
                "deliverable",
                "success_criteria",
                "due_date",
                "requirement_type",
            ],
            "title_must_not_include": ["DRAFT", "PUBLISHED", "ARCHIVED"],
            "program_scope_forbids_named_assignees": context.get("roadmap_scope")
            == "PROGRAM",
        },
    }
    messages = [
        {"role": "system", "content": ROADMAP_GENERATOR_SYSTEM},
        {
            "role": "user",
            "content": json.dumps(user_payload, ensure_ascii=True, default=str),
        },
    ]

    last_error: Exception | None = None
    for _attempt in range(2):
        try:
            parsed = openai_client.parse_structured(
                model=config.roadmap_model(),
                input_messages=messages,
                text_format=GeneratedRoadmap,
            )
            return validate_generated_roadmap(parsed, context=context)
        except AIInvalidOutputError as exc:
            last_error = exc
            continue
    raise last_error or AIInvalidOutputError()
