"""Deterministic week-performance metrics for Weekly Reports and Final Summaries.

No AI involvement — Django/system data only.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from django.db.models import Prefetch

from apps.programs.models import InternProfile, InternshipProgram
from apps.reports.models import WeeklyReport
from apps.roadmaps.models import Roadmap, RoadmapWeek
from apps.submissions.models import Submission
from apps.tasks.models import TaskAssignment
from common.constants import AiContentStatus, RoadmapStatus, TaskAssignmentStatus


def _submission_date(submission: Submission) -> date | None:
    submitted_at = submission.submitted_at
    if submitted_at is None:
        return None
    if isinstance(submitted_at, datetime):
        return submitted_at.date()
    return submitted_at


def _is_assignment_on_time(assignment: TaskAssignment) -> bool:
    """True when the latest submission was on/before the effective due date."""
    submissions = list(assignment.submissions.all())
    if not submissions:
        return False
    latest = max(submissions, key=lambda item: item.version_number)
    submitted_on = _submission_date(latest)
    if submitted_on is None:
        return False
    due = assignment.effective_due_date
    if due is None:
        return True
    return submitted_on <= due


def _assignments_for_week(*, intern: InternProfile, week: RoadmapWeek):
    return (
        TaskAssignment.objects.filter(intern=intern, task__roadmap_week=week)
        .select_related("task")
        .prefetch_related(
            Prefetch(
                "submissions",
                queryset=Submission.objects.order_by("version_number"),
            )
        )
    )


def compute_week_task_metrics(*, intern: InternProfile, week: RoadmapWeek) -> dict[str, int]:
    assignments = list(_assignments_for_week(intern=intern, week=week))
    total_tasks = len(assignments)
    completed_tasks = sum(
        1 for item in assignments if item.status == TaskAssignmentStatus.COMPLETED
    )
    needs_revision = sum(
        1 for item in assignments if item.status == TaskAssignmentStatus.NEEDS_REVISION
    )
    on_time_tasks = sum(1 for item in assignments if _is_assignment_on_time(item))
    return {
        "completed_tasks": completed_tasks,
        "total_tasks": total_tasks,
        "needs_revision": needs_revision,
        "on_time_tasks": on_time_tasks,
    }


def _approved_weekly_scores_map(
    *,
    intern: InternProfile,
    program: InternshipProgram,
) -> dict[int, int | None]:
    rows = WeeklyReport.objects.filter(
        intern=intern,
        program=program,
        status=AiContentStatus.APPROVED,
        roadmap_week__isnull=False,
    ).select_related("roadmap_week")
    result: dict[int, int | None] = {}
    for report in rows:
        week_number = report.roadmap_week.week_number
        result[week_number] = report.overall_weekly_score
    return result


def _resolve_program_weeks(*, program: InternshipProgram) -> list[RoadmapWeek]:
    published = (
        Roadmap.objects.filter(program=program, status=RoadmapStatus.PUBLISHED)
        .order_by("-created_at")
        .first()
    )
    roadmap = published
    if roadmap is None:
        roadmap = (
            Roadmap.objects.filter(program=program).order_by("-created_at").first()
        )
    if roadmap is None:
        return []
    return list(roadmap.weeks.all().order_by("week_number"))


def _delta(current: int | None, previous: int | None) -> int | None:
    if current is None or previous is None:
        return None
    return current - previous


def build_weekly_report_comparison(
    *,
    intern: InternProfile,
    program: InternshipProgram,
    current_week: RoadmapWeek | None,
    current_weekly_score: int | None = None,
) -> dict[str, Any]:
    """
    Build Metric × Weeks comparison for a Weekly Report.

    Includes Week 1 through the current week. Change compares current vs
    immediately previous week only.
    """
    if current_week is None:
        return {
            "current_week_number": None,
            "has_previous_weeks": False,
            "weeks": [],
            "change": None,
            "message": "No previous week available for comparison.",
        }

    roadmap = current_week.roadmap
    weeks = list(
        RoadmapWeek.objects.filter(
            roadmap=roadmap,
            week_number__lte=current_week.week_number,
        ).order_by("week_number")
    )
    approved_scores = _approved_weekly_scores_map(intern=intern, program=program)

    week_rows: list[dict[str, Any]] = []
    for week in weeks:
        metrics = compute_week_task_metrics(intern=intern, week=week)
        if week.id == current_week.id:
            weekly_score = current_weekly_score
        else:
            weekly_score = approved_scores.get(week.week_number)
        week_rows.append(
            {
                "week_number": week.week_number,
                "weekly_score": weekly_score,
                "completed_tasks": metrics["completed_tasks"],
                "total_tasks": metrics["total_tasks"],
                "needs_revision": metrics["needs_revision"],
                "on_time_tasks": metrics["on_time_tasks"],
            }
        )

    has_previous = len(week_rows) >= 2
    change = None
    if has_previous:
        previous = week_rows[-2]
        current = week_rows[-1]
        change = {
            "weekly_score": _delta(current["weekly_score"], previous["weekly_score"]),
            "completed_tasks": _delta(
                current["completed_tasks"], previous["completed_tasks"]
            ),
            "needs_revision": _delta(
                current["needs_revision"], previous["needs_revision"]
            ),
            "on_time_tasks": _delta(
                current["on_time_tasks"], previous["on_time_tasks"]
            ),
        }

    return {
        "current_week_number": current_week.week_number,
        "has_previous_weeks": has_previous,
        "weeks": week_rows,
        "change": change,
        "message": (
            None
            if has_previous
            else "No previous week available for comparison."
        ),
    }


def build_final_summary_week_performance(
    *,
    intern: InternProfile,
    program: InternshipProgram,
) -> dict[str, Any]:
    """All program roadmap weeks with score / completion / needs-revision / focus."""
    weeks = _resolve_program_weeks(program=program)
    approved_scores = _approved_weekly_scores_map(intern=intern, program=program)
    rows: list[dict[str, Any]] = []
    for week in weeks:
        metrics = compute_week_task_metrics(intern=intern, week=week)
        rows.append(
            {
                "week_number": week.week_number,
                "weekly_score": approved_scores.get(week.week_number),
                "completed_tasks": metrics["completed_tasks"],
                "total_tasks": metrics["total_tasks"],
                "needs_revision": metrics["needs_revision"],
                "main_focus": (week.weekly_focus or "").strip() or None,
            }
        )
    return {
        "weeks": rows,
    }


def format_signed_change(value: int | None) -> str:
    if value is None:
        return "—"
    if value > 0:
        return f"+{value}"
    return str(value)


def format_completed_tasks(completed: int, total: int) -> str:
    return f"{completed}/{total}"
