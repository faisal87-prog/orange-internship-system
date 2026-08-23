"""AI Weekly Report Generator — OpenAI call #2."""

from __future__ import annotations

import json
from typing import Any

from services.ai import client as openai_client
from services.ai import config
from services.ai.exceptions import AIInvalidOutputError
from services.ai.schemas import GeneratedWeeklyReport
from services.ai.weekly_report_validators import validate_generated_weekly_report

WEEKLY_REPORT_GENERATOR_SYSTEM = """
You are an internship weekly performance report generator for mentors.
Follow the Final Weekly Report Generation Prompt exactly.
Use the canonical structured weekly context as authoritative evidence.
Do not invent activity, scores, feedback, or achievements.
Do not output overall_weekly_score or additional_mentor_notes.
Return only the six required string fields.
""".strip()


def generate_weekly_report_structure(
    *,
    context: dict[str, Any],
    final_weekly_report_generation_prompt: str,
) -> GeneratedWeeklyReport:
    """Generate the weekly report JSON using the exact previewed Final Prompt."""
    user_payload = {
        "final_weekly_report_generation_prompt": final_weekly_report_generation_prompt,
        "canonical_weekly_context": context,
        "required_fields": [
            "performance_summary",
            "achievements",
            "learning_progress",
            "productivity_analysis",
            "mentor_focus_suggestions",
            "recommended_next_focus",
        ],
    }
    messages = [
        {"role": "system", "content": WEEKLY_REPORT_GENERATOR_SYSTEM},
        {
            "role": "user",
            "content": json.dumps(user_payload, ensure_ascii=True, default=str),
        },
    ]

    last_error: Exception | None = None
    for _attempt in range(2):
        try:
            parsed = openai_client.parse_structured(
                model=config.weekly_report_model(),
                input_messages=messages,
                text_format=GeneratedWeeklyReport,
            )
            return validate_generated_weekly_report(parsed)
        except AIInvalidOutputError as exc:
            last_error = exc
            continue
    raise last_error or AIInvalidOutputError()
