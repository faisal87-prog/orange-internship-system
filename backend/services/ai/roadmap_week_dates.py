"""Canonical roadmap week-boundary calculation.

Single source of truth for:
- Final AI Roadmap Prompt week windows
- Django roadmap due-date validation
- Persisted RoadmapWeek start/end dates

Each normal week is 7 consecutive calendar days (inclusive).
The final week's end is capped at the program end date.
"""

from __future__ import annotations

from datetime import date, timedelta


def week_boundaries(
    program_start: date,
    program_end: date,
    week_number: int,
    total_weeks: int,
) -> tuple[date, date]:
    """
    Return inclusive (week_start, week_end) for a roadmap week.

    week_start = program_start + (week_number - 1) * 7 days
    week_end   = min(week_start + 6 days, program_end)
    """
    if total_weeks < 1:
        raise ValueError("total_weeks must be >= 1")
    if week_number < 1:
        raise ValueError("week_number must be >= 1")

    week_start = program_start + timedelta(days=(week_number - 1) * 7)
    week_end = week_start + timedelta(days=6)
    week_end = min(week_end, program_end)
    if week_end < week_start:
        week_end = week_start
    return week_start, week_end


def compute_week_dates(
    program_start: date,
    program_end: date,
    week_number: int,
    total_weeks: int,
) -> tuple[date, date]:
    """Alias used by persistence and callers expecting this name."""
    return week_boundaries(program_start, program_end, week_number, total_weeks)


def iter_program_week_boundaries(
    program_start: date,
    program_end: date,
    duration_weeks: int,
) -> list[tuple[int, date, date]]:
    """Return [(week_number, start, end), ...] for the full program duration."""
    return [
        (week_number, *week_boundaries(program_start, program_end, week_number, duration_weeks))
        for week_number in range(1, duration_weeks + 1)
    ]


def format_authoritative_week_boundaries_block(
    *,
    program_start: date,
    program_end: date,
    duration_weeks: int,
) -> str:
    """Human-readable block injected into the Final Roadmap Generation Prompt."""
    lines = [
        "These week windows are authoritative Django calendar boundaries.",
        "Task due_date values MUST fall within the matching week window (inclusive).",
        "Do not invent alternate week start/end dates.",
        "",
    ]
    for week_number, start, end in iter_program_week_boundaries(
        program_start, program_end, duration_weeks
    ):
        lines.append(f"Week {week_number}: {start.isoformat()} → {end.isoformat()}")
    return "\n".join(lines) + "\n"
