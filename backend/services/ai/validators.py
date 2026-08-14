"""Validate AI roadmap structured output against business rules."""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from services.ai.exceptions import AIInvalidOutputError
from services.ai.schemas import GeneratedRoadmap

VALID_DIFFICULTIES = {"EASY", "MEDIUM", "HARD"}
VALID_REQUIREMENTS = {"REQUIRED", "OPTIONAL"}
STATUS_TITLE_PREFIX_RE = re.compile(
    r"^(?:DRAFT|PUBLISHED|ARCHIVED)\b[\s\-—–:|]*",
    re.IGNORECASE,
)
ASSIGNEE_HINT_RE = re.compile(
    r"\b(assignee|assigned to|\(lead\)|as lead|task owner|owned by)\b",
    re.IGNORECASE,
)


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except Exception as exc:  # noqa: BLE001
        raise AIInvalidOutputError(
            "AI roadmap generation could not produce a valid roadmap. Please try again."
        ) from exc


def sanitize_roadmap_title(title: str) -> str:
    """Strip lifecycle/status prefixes; status is owned by Django/UI."""
    cleaned = (title or "").strip()
    while True:
        updated = STATUS_TITLE_PREFIX_RE.sub("", cleaned).strip(" -—–:|")
        if updated == cleaned:
            break
        cleaned = updated
    # Reject titles that still lead with a bare status token after cleanup attempts.
    if re.match(r"^(DRAFT|PUBLISHED|ARCHIVED)\b", cleaned, re.IGNORECASE):
        raise AIInvalidOutputError(
            "AI roadmap generation could not produce a valid roadmap. Please try again."
        )
    if not cleaned:
        raise AIInvalidOutputError(
            "AI roadmap generation could not produce a valid roadmap. Please try again."
        )
    return cleaned


def week_boundaries(program_start: date, program_end: date, week_number: int, total_weeks: int):
    """Deterministic week window used for due-date validation."""
    if total_weeks < 1:
        raise AIInvalidOutputError()
    span_days = max((program_end - program_start).days, 0)
    week_length = max(span_days // total_weeks, 1)
    start = program_start + timedelta(days=(week_number - 1) * week_length)
    if week_number == total_weeks:
        end = program_end
    else:
        end = min(program_start + timedelta(days=week_number * week_length - 1), program_end)
    if end < start:
        end = start
    return start, end


def _reject_program_named_assignees(roadmap: GeneratedRoadmap, context: dict[str, Any]) -> None:
    if context.get("roadmap_scope") != "PROGRAM":
        return
    intern_names = [
        (item.get("full_name") or "").strip()
        for item in context.get("interns") or []
        if (item.get("full_name") or "").strip()
    ]
    if not intern_names:
        return
    for week in roadmap.weeks:
        for task in week.tasks:
            blob = f"{task.title}\n{task.description}"
            if not ASSIGNEE_HINT_RE.search(blob):
                # Still reject explicit "Name (lead)" patterns with known intern names.
                lowered = blob.lower()
                for name in intern_names:
                    if f"{name.lower()} (lead)" in lowered or f"{name.lower()}(lead)" in lowered:
                        raise AIInvalidOutputError(
                            "AI roadmap generation could not produce a valid roadmap. Please try again."
                        )
                continue
            lowered = blob.lower()
            for name in intern_names:
                if name.lower() in lowered:
                    raise AIInvalidOutputError(
                        "AI roadmap generation could not produce a valid roadmap. Please try again."
                    )


def _reject_obvious_duplicate_tasks(roadmap: GeneratedRoadmap) -> None:
    seen: set[str] = set()
    for week in roadmap.weeks:
        for task in week.tasks:
            key = re.sub(r"\s+", " ", task.title.strip().lower())
            if key in seen:
                raise AIInvalidOutputError(
                    "AI roadmap generation could not produce a valid roadmap. Please try again."
                )
            seen.add(key)


def validate_generated_roadmap(
    roadmap: GeneratedRoadmap,
    *,
    context: dict[str, Any],
) -> GeneratedRoadmap:
    program = context["program"]
    duration_weeks = int(program["duration_weeks"])
    program_start = _parse_date(program["start_date"])
    program_end = _parse_date(program["end_date"])

    cleaned_title = sanitize_roadmap_title(roadmap.title)
    roadmap = roadmap.model_copy(update={"title": cleaned_title})

    if roadmap.number_of_weeks != duration_weeks:
        raise AIInvalidOutputError(
            "AI roadmap generation could not produce a valid roadmap. Please try again."
        )
    if not roadmap.title.strip() or not roadmap.summary.strip():
        raise AIInvalidOutputError()
    if len(roadmap.weeks) != duration_weeks:
        raise AIInvalidOutputError()

    seen_weeks: set[int] = set()
    for week in roadmap.weeks:
        if week.week_number in seen_weeks:
            raise AIInvalidOutputError()
        seen_weeks.add(week.week_number)
        if week.week_number < 1 or week.week_number > duration_weeks:
            raise AIInvalidOutputError()
        if not week.weekly_focus.strip():
            raise AIInvalidOutputError()
        if not week.learning_objectives or not all(
            isinstance(item, str) and item.strip() for item in week.learning_objectives
        ):
            raise AIInvalidOutputError()
        if not week.expected_skills_gained or not all(
            isinstance(item, str) and item.strip() for item in week.expected_skills_gained
        ):
            raise AIInvalidOutputError()
        if not week.tasks:
            raise AIInvalidOutputError()

        week_start, week_end = week_boundaries(
            program_start, program_end, week.week_number, duration_weeks
        )
        for task in week.tasks:
            if not task.title.strip() or not task.description.strip():
                raise AIInvalidOutputError()
            if task.difficulty not in VALID_DIFFICULTIES:
                raise AIInvalidOutputError()
            if task.requirement_type not in VALID_REQUIREMENTS:
                raise AIInvalidOutputError()
            if task.estimated_time_minutes <= 0:
                raise AIInvalidOutputError()
            if not task.deliverable.strip() or not task.success_criteria.strip():
                raise AIInvalidOutputError()
            due = _parse_date(task.due_date)
            if due < program_start or due > program_end:
                raise AIInvalidOutputError()
            if due < week_start or due > week_end:
                raise AIInvalidOutputError()

    expected = set(range(1, duration_weeks + 1))
    if seen_weeks != expected:
        raise AIInvalidOutputError()

    _reject_program_named_assignees(roadmap, context)
    _reject_obvious_duplicate_tasks(roadmap)

    return roadmap


def compute_week_dates(
    program_start: date,
    program_end: date,
    week_number: int,
    total_weeks: int,
) -> tuple[date, date]:
    return week_boundaries(program_start, program_end, week_number, total_weeks)
