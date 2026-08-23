"""Validate AI Weekly Report structured output before persistence."""

from __future__ import annotations

from services.ai.exceptions import AIInvalidOutputError
from services.ai.schemas import GeneratedWeeklyReport

REQUIRED_FIELDS = (
    "performance_summary",
    "achievements",
    "learning_progress",
    "productivity_analysis",
    "mentor_focus_suggestions",
    "recommended_next_focus",
)

MAX_FIELD_CHARS = 8000
MIN_FIELD_CHARS = 20


def validate_generated_weekly_report(
    report: GeneratedWeeklyReport,
) -> GeneratedWeeklyReport:
    data = report.model_dump()
    for field in REQUIRED_FIELDS:
        value = data.get(field)
        if not isinstance(value, str):
            raise AIInvalidOutputError(
                "AI weekly report generation could not produce a valid report. Please try again."
            )
        cleaned = value.strip()
        if len(cleaned) < MIN_FIELD_CHARS:
            raise AIInvalidOutputError(
                "AI weekly report generation could not produce a valid report. Please try again."
            )
        if len(cleaned) > MAX_FIELD_CHARS:
            raise AIInvalidOutputError(
                "AI weekly report generation could not produce a valid report. Please try again."
            )
        setattr(report, field, cleaned)

    # Official score / mentor notes must never appear as AI-controlled content.
    forbidden = {"overall_weekly_score", "additional_mentor_notes", "status"}
    extras = set(data.keys()) - set(REQUIRED_FIELDS)
    if extras & forbidden:
        raise AIInvalidOutputError(
            "AI weekly report generation could not produce a valid report. Please try again."
        )
    return report


def text_to_list(value: str) -> list[str]:
    """Convert AI free-text section into JSON list bullets for storage/UI."""
    lines = []
    for raw in value.replace("\r\n", "\n").split("\n"):
        item = raw.strip().lstrip("-•* ").strip()
        if item:
            lines.append(item)
    return lines or [value.strip()]
