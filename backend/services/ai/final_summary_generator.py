"""AI Final Summary Generator — OpenAI call #2."""

from __future__ import annotations

import json
from typing import Any

from services.ai import client as openai_client
from services.ai import config
from services.ai.exceptions import AIInvalidOutputError
from services.ai.final_summary_validators import validate_generated_final_summary
from services.ai.schemas import GeneratedFinalSummary

FINAL_SUMMARY_GENERATOR_SYSTEM = """
You are an internship final summary generator for mentors.
Follow the Final Final-Summary Generation Prompt exactly.
Use the canonical structured final-summary context as authoritative evidence.
Do not invent activity, scores, feedback, achievements, or improvement.
Do not output final_score, mentor_comments, or additional notes.
Do not produce hiring/employment recommendations.
Return only the five required string fields.
""".strip()


def generate_final_summary_structure(
    *,
    context: dict[str, Any],
    final_final_summary_generation_prompt: str,
) -> GeneratedFinalSummary:
    """Generate the final summary JSON using the exact previewed Final Prompt."""
    user_payload = {
        "final_final_summary_generation_prompt": final_final_summary_generation_prompt,
        "canonical_final_summary_context": context,
        "required_fields": [
            "overall_performance_summary",
            "learning_journey",
            "main_achievements",
            "goal_achievement",
            "final_performance_summary",
        ],
    }
    messages = [
        {"role": "system", "content": FINAL_SUMMARY_GENERATOR_SYSTEM},
        {
            "role": "user",
            "content": json.dumps(user_payload, ensure_ascii=True, default=str),
        },
    ]

    last_error: Exception | None = None
    for _attempt in range(2):
        try:
            parsed = openai_client.parse_structured(
                model=config.final_summary_model(),
                input_messages=messages,
                text_format=GeneratedFinalSummary,
            )
            return validate_generated_final_summary(parsed)
        except AIInvalidOutputError as exc:
            last_error = exc
            continue
    raise last_error or AIInvalidOutputError()
