"""Validate AI roadmap structured output against business rules."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from services.ai.exceptions import AIInvalidOutputError
from services.ai.logging_utils import log_roadmap_failure
from services.ai.roadmap_week_dates import week_boundaries as _canonical_week_boundaries
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


def _invalid(
    *,
    reason: str,
    path: str | None = None,
    expected: Any = None,
    received: Any = None,
    program_id: Any = None,
    week_number: Any = None,
    task_number: Any = None,
    task_title: str | None = None,
    fragment: Any = None,
) -> AIInvalidOutputError:
    return AIInvalidOutputError(
        reason=reason,
        path=path,
        expected=expected,
        received=received,
        program_id=program_id,
        week_number=week_number,
        task_number=task_number,
        task_title=task_title,
        fragment=fragment,
        error_type="RoadmapValidationError",
    )


def _raise_invalid(**kwargs: Any) -> None:
    raise _invalid(**kwargs)


def _parse_date(value: str, *, path: str, program_id: Any = None) -> date:
    try:
        return date.fromisoformat(value)
    except Exception as exc:  # noqa: BLE001
        raise _invalid(
            reason="Invalid date format (expected YYYY-MM-DD)",
            path=path,
            expected="YYYY-MM-DD ISO date",
            received=value,
            program_id=program_id,
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
        _raise_invalid(
            reason="Roadmap title still starts with a lifecycle status token after sanitization",
            path="title",
            expected="Title without DRAFT/PUBLISHED/ARCHIVED prefix",
            received=title,
        )
    if not cleaned:
        _raise_invalid(
            reason="Roadmap title is empty after sanitization",
            path="title",
            expected="Non-empty title",
            received=title,
        )
    return cleaned


def week_boundaries(program_start: date, program_end: date, week_number: int, total_weeks: int):
    """Deterministic week window used for due-date validation (canonical 7-day weeks)."""
    try:
        return _canonical_week_boundaries(
            program_start, program_end, week_number, total_weeks
        )
    except ValueError as exc:
        raise _invalid(
            reason=str(exc),
            path="number_of_weeks" if "total_weeks" in str(exc) else "week_number",
            expected=">= 1",
            received=total_weeks if "total_weeks" in str(exc) else week_number,
        ) from exc


def _reject_program_named_assignees(roadmap: GeneratedRoadmap, context: dict[str, Any]) -> None:
    if context.get("roadmap_scope") != "PROGRAM":
        return
    program_id = (context.get("program") or {}).get("id")
    intern_names = [
        (item.get("full_name") or "").strip()
        for item in context.get("interns") or []
        if (item.get("full_name") or "").strip()
    ]
    if not intern_names:
        return
    for week_index, week in enumerate(roadmap.weeks):
        for task_index, task in enumerate(week.tasks):
            blob = f"{task.title}\n{task.description}"
            path = f"weeks[{week_index}].tasks[{task_index}]"
            if not ASSIGNEE_HINT_RE.search(blob):
                # Still reject explicit "Name (lead)" patterns with known intern names.
                lowered = blob.lower()
                for name in intern_names:
                    if f"{name.lower()} (lead)" in lowered or f"{name.lower()}(lead)" in lowered:
                        _raise_invalid(
                            reason="Program-scope roadmap must not name intern assignees in tasks",
                            path=path,
                            expected="Task text without named intern assignees",
                            received=f"{task.title} / mentions {name} (lead)",
                            program_id=program_id,
                            week_number=week.week_number,
                            task_number=task_index + 1,
                            task_title=task.title,
                            fragment={"title": task.title, "description": task.description[:200]},
                        )
                continue
            lowered = blob.lower()
            for name in intern_names:
                if name.lower() in lowered:
                    _raise_invalid(
                        reason="Program-scope roadmap must not name intern assignees in tasks",
                        path=path,
                        expected="Task text without named intern assignees",
                        received=f"{task.title} / mentions {name}",
                        program_id=program_id,
                        week_number=week.week_number,
                        task_number=task_index + 1,
                        task_title=task.title,
                        fragment={"title": task.title, "description": task.description[:200]},
                    )


def _reject_obvious_duplicate_tasks(roadmap: GeneratedRoadmap, *, program_id: Any = None) -> None:
    seen: dict[str, str] = {}
    for week_index, week in enumerate(roadmap.weeks):
        for task_index, task in enumerate(week.tasks):
            key = re.sub(r"\s+", " ", task.title.strip().lower())
            if key in seen:
                _raise_invalid(
                    reason="Duplicate task title across roadmap",
                    path=f"weeks[{week_index}].tasks[{task_index}].title",
                    expected="Unique task titles",
                    received=task.title,
                    program_id=program_id,
                    week_number=week.week_number,
                    task_number=task_index + 1,
                    task_title=task.title,
                    fragment={"duplicate_of": seen[key], "title": task.title},
                )
            seen[key] = f"weeks[?].tasks / first seen as {task.title}"


def validate_generated_roadmap(
    roadmap: GeneratedRoadmap,
    *,
    context: dict[str, Any],
) -> GeneratedRoadmap:
    program = context["program"]
    program_id = program.get("id")
    duration_weeks = int(program["duration_weeks"])
    program_start = _parse_date(
        program["start_date"], path="program.start_date", program_id=program_id
    )
    program_end = _parse_date(
        program["end_date"], path="program.end_date", program_id=program_id
    )

    try:
        cleaned_title = sanitize_roadmap_title(roadmap.title)
        roadmap = roadmap.model_copy(update={"title": cleaned_title})

        if roadmap.number_of_weeks != duration_weeks:
            _raise_invalid(
                reason="Expected number_of_weeks to match program duration_weeks",
                path="number_of_weeks",
                expected=duration_weeks,
                received=roadmap.number_of_weeks,
                program_id=program_id,
            )
        if not roadmap.title.strip() or not roadmap.summary.strip():
            _raise_invalid(
                reason="Roadmap title and summary are required",
                path="title" if not roadmap.title.strip() else "summary",
                expected="Non-empty title and summary",
                received={
                    "title": roadmap.title,
                    "summary": (roadmap.summary or "")[:120],
                },
                program_id=program_id,
            )
        if len(roadmap.weeks) != duration_weeks:
            _raise_invalid(
                reason=f"Expected exactly {duration_weeks} weeks",
                path="weeks",
                expected=duration_weeks,
                received=len(roadmap.weeks),
                program_id=program_id,
            )

        seen_weeks: set[int] = set()
        for week_index, week in enumerate(roadmap.weeks):
            week_path = f"weeks[{week_index}]"
            if week.week_number in seen_weeks:
                _raise_invalid(
                    reason="Duplicate week_number",
                    path=f"{week_path}.week_number",
                    expected="Unique week_number values",
                    received=week.week_number,
                    program_id=program_id,
                    week_number=week.week_number,
                )
            seen_weeks.add(week.week_number)
            if week.week_number < 1 or week.week_number > duration_weeks:
                _raise_invalid(
                    reason="week_number out of allowed range",
                    path=f"{week_path}.week_number",
                    expected=f"1 through {duration_weeks}",
                    received=week.week_number,
                    program_id=program_id,
                    week_number=week.week_number,
                )
            if not week.weekly_focus.strip():
                _raise_invalid(
                    reason="weekly_focus is required",
                    path=f"{week_path}.weekly_focus",
                    expected="Non-empty weekly_focus",
                    received=week.weekly_focus,
                    program_id=program_id,
                    week_number=week.week_number,
                )
            if not week.learning_objectives or not all(
                isinstance(item, str) and item.strip() for item in week.learning_objectives
            ):
                _raise_invalid(
                    reason="learning_objectives must be a non-empty list of strings",
                    path=f"{week_path}.learning_objectives",
                    expected="Non-empty list[str]",
                    received=week.learning_objectives,
                    program_id=program_id,
                    week_number=week.week_number,
                )
            if not week.expected_skills_gained or not all(
                isinstance(item, str) and item.strip() for item in week.expected_skills_gained
            ):
                _raise_invalid(
                    reason="expected_skills_gained must be a non-empty list of strings",
                    path=f"{week_path}.expected_skills_gained",
                    expected="Non-empty list[str]",
                    received=week.expected_skills_gained,
                    program_id=program_id,
                    week_number=week.week_number,
                )
            if not week.tasks:
                _raise_invalid(
                    reason="Each week must include at least one task",
                    path=f"{week_path}.tasks",
                    expected="Non-empty tasks list",
                    received=[],
                    program_id=program_id,
                    week_number=week.week_number,
                )

            week_start, week_end = week_boundaries(
                program_start, program_end, week.week_number, duration_weeks
            )
            for task_index, task in enumerate(week.tasks):
                task_path = f"{week_path}.tasks[{task_index}]"
                if not task.title.strip() or not task.description.strip():
                    _raise_invalid(
                        reason="Task title and description are required",
                        path=task_path,
                        expected="Non-empty title and description",
                        received={
                            "title": task.title,
                            "description": (task.description or "")[:120],
                        },
                        program_id=program_id,
                        week_number=week.week_number,
                        task_number=task_index + 1,
                        task_title=task.title,
                    )
                if task.difficulty not in VALID_DIFFICULTIES:
                    _raise_invalid(
                        reason="Invalid task difficulty",
                        path=f"{task_path}.difficulty",
                        expected="EASY | MEDIUM | HARD",
                        received=task.difficulty,
                        program_id=program_id,
                        week_number=week.week_number,
                        task_number=task_index + 1,
                        task_title=task.title,
                    )
                if task.requirement_type not in VALID_REQUIREMENTS:
                    _raise_invalid(
                        reason="Invalid task requirement_type",
                        path=f"{task_path}.requirement_type",
                        expected="REQUIRED | OPTIONAL",
                        received=task.requirement_type,
                        program_id=program_id,
                        week_number=week.week_number,
                        task_number=task_index + 1,
                        task_title=task.title,
                    )
                if task.estimated_time_minutes <= 0:
                    _raise_invalid(
                        reason="estimated_time_minutes must be > 0",
                        path=f"{task_path}.estimated_time_minutes",
                        expected="> 0",
                        received=task.estimated_time_minutes,
                        program_id=program_id,
                        week_number=week.week_number,
                        task_number=task_index + 1,
                        task_title=task.title,
                    )
                if not task.deliverable.strip() or not task.success_criteria.strip():
                    _raise_invalid(
                        reason="Task deliverable and success_criteria are required",
                        path=task_path,
                        expected="Non-empty deliverable and success_criteria",
                        received={
                            "deliverable": task.deliverable,
                            "success_criteria": task.success_criteria,
                        },
                        program_id=program_id,
                        week_number=week.week_number,
                        task_number=task_index + 1,
                        task_title=task.title,
                    )
                due = _parse_date(
                    task.due_date,
                    path=f"{task_path}.due_date",
                    program_id=program_id,
                )
                if due < program_start or due > program_end:
                    _raise_invalid(
                        reason="Task due date outside program date range",
                        path=f"{task_path}.due_date",
                        expected=f"{program_start.isoformat()} through {program_end.isoformat()}",
                        received=due.isoformat(),
                        program_id=program_id,
                        week_number=week.week_number,
                        task_number=task_index + 1,
                        task_title=task.title,
                    )
                if due < week_start or due > week_end:
                    _raise_invalid(
                        reason="Task due date outside week range",
                        path=f"{task_path}.due_date",
                        expected=f"{week_start.isoformat()} through {week_end.isoformat()}",
                        received=due.isoformat(),
                        program_id=program_id,
                        week_number=week.week_number,
                        task_number=task_index + 1,
                        task_title=task.title,
                    )

        expected = set(range(1, duration_weeks + 1))
        if seen_weeks != expected:
            _raise_invalid(
                reason="Week numbers must cover every week from 1..duration_weeks",
                path="weeks.week_number",
                expected=sorted(expected),
                received=sorted(seen_weeks),
                program_id=program_id,
            )

        _reject_program_named_assignees(roadmap, context)
        _reject_obvious_duplicate_tasks(roadmap, program_id=program_id)
    except AIInvalidOutputError as exc:
        # Ensure program_id is attached when available, then log once at validation layer.
        if exc.program_id is None and program_id is not None:
            exc.program_id = program_id
            exc.diagnostic = exc._build_diagnostic()
        log_roadmap_failure("ROADMAP_VALIDATION_FAILED", exc=exc, program_id=program_id)
        raise

    return roadmap


def compute_week_dates(
    program_start: date,
    program_end: date,
    week_number: int,
    total_weeks: int,
) -> tuple[date, date]:
    return week_boundaries(program_start, program_end, week_number, total_weeks)
