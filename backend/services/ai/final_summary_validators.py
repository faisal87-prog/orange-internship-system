"""Validate AI Final Summary structured output before persistence."""

from __future__ import annotations

from services.ai.exceptions import AIInvalidOutputError
from services.ai.schemas import GeneratedFinalSummary

REQUIRED_FIELDS = (
    "overall_performance_summary",
    "learning_journey",
    "main_achievements",
    "goal_achievement",
    "final_performance_summary",
)

MAX_FIELD_CHARS = 8000
MIN_FIELD_CHARS = 20


def validate_generated_final_summary(
    summary: GeneratedFinalSummary,
) -> GeneratedFinalSummary:
    data = summary.model_dump()
    for field in REQUIRED_FIELDS:
        value = data.get(field)
        if not isinstance(value, str):
            raise AIInvalidOutputError(
                "AI final summary generation could not produce a valid summary. Please try again."
            )
        cleaned = value.strip()
        if len(cleaned) < MIN_FIELD_CHARS:
            raise AIInvalidOutputError(
                "AI final summary generation could not produce a valid summary. Please try again."
            )
        if len(cleaned) > MAX_FIELD_CHARS:
            raise AIInvalidOutputError(
                "AI final summary generation could not produce a valid summary. Please try again."
            )
        setattr(summary, field, cleaned)

    forbidden = {
        "final_score",
        "mentor_comments",
        "additional_notes",
        "additional_mentor_notes",
        "status",
        "strengths",
        "areas_for_improvement",
        "hiring_recommendation",
    }
    extras = set(data.keys()) - set(REQUIRED_FIELDS)
    if extras & forbidden:
        raise AIInvalidOutputError(
            "AI final summary generation could not produce a valid summary. Please try again."
        )
    return summary
