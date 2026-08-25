"""Assemble authoritative final-summary context for one Intern + one Program."""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from apps.programs.models import InternProfile, InternshipProgram
from apps.reports.models import WeeklyReport
from apps.roadmaps.models import Roadmap
from apps.tasks.models import TaskAssignment
from common.constants import AiContentStatus, Role, RoadmapStatus
from services.ai.context_assembler import SKILL_LEVEL_LABELS, serialize_intern
from services.ai.exceptions import AIPermissionError, AIValidationError
from services.ai.weekly_report_context import _assignment_payload, _iso_date
from services.final_summary_score import (
    calculate_final_summary_score,
    count_scored_weekly_reports,
    format_final_summary_score_display,
)


def resolve_final_summary_targets(
    *,
    mentor,
    program_id: int,
    intern_id: int,
) -> tuple[InternshipProgram, InternProfile]:
    if getattr(mentor, "role", None) != Role.MENTOR:
        raise AIPermissionError()

    try:
        program = InternshipProgram.objects.select_related("mentor").get(pk=program_id)
    except InternshipProgram.DoesNotExist as exc:
        raise AIValidationError("Program not found.") from exc
    if program.mentor_id != mentor.id:
        raise AIPermissionError()

    try:
        intern = InternProfile.objects.select_related("user", "mentor").prefetch_related(
            "skills"
        ).get(pk=intern_id)
    except InternProfile.DoesNotExist as exc:
        raise AIValidationError("Intern not found.") from exc
    if intern.program_id != program.id or intern.mentor_id != mentor.id:
        raise AIValidationError(
            "The selected intern does not belong to this program."
        )
    return program, intern


def assemble_final_summary_context(
    *,
    program: InternshipProgram,
    intern: InternProfile,
) -> dict[str, Any]:
    today = timezone.localdate()

    roadmaps = list(
        Roadmap.objects.filter(program=program)
        .prefetch_related("weeks")
        .order_by("-status", "-created_at")
    )
    published = [item for item in roadmaps if item.status == RoadmapStatus.PUBLISHED]
    primary_roadmap = published[0] if published else (roadmaps[0] if roadmaps else None)

    weeks_payload: list[dict[str, Any]] = []
    if primary_roadmap:
        for week in primary_roadmap.weeks.all().order_by("week_number"):
            weeks_payload.append(
                {
                    "id": week.id,
                    "week_number": week.week_number,
                    "weekly_focus": week.weekly_focus,
                    "learning_objectives": week.learning_objectives or [],
                    "expected_skills_gained": week.expected_skills_gained or [],
                    "mentor_notes": week.mentor_notes or "",
                    "start_date": _iso_date(week.start_date),
                    "end_date": _iso_date(week.end_date),
                }
            )

    assignments = (
        TaskAssignment.objects.filter(
            intern=intern,
            task__program=program,
        )
        .select_related("task", "task__roadmap_week", "task__program")
        .prefetch_related("task__resources", "submissions__files")
        .order_by(
            "task__roadmap_week__week_number",
            "task__display_order",
            "task__id",
        )
    )
    task_payloads = []
    for assignment in assignments:
        payload = _assignment_payload(assignment=assignment, today=today)
        week = assignment.task.roadmap_week
        payload["week_number"] = week.week_number if week else None
        payload["week_id"] = week.id if week else None
        task_payloads.append(payload)

    scored = [item["score"] for item in task_payloads if item["score"] is not None]
    approved_weekly = (
        WeeklyReport.objects.filter(
            intern=intern,
            program=program,
            status=AiContentStatus.APPROVED,
        )
        .select_related("roadmap_week")
        .order_by("roadmap_week__week_number", "id")
    )
    weekly_payloads = []
    for report in approved_weekly:
        weekly_payloads.append(
            {
                "id": report.id,
                "week_number": (
                    report.roadmap_week.week_number if report.roadmap_week else None
                ),
                "performance_summary": report.performance_summary or "",
                "achievements": report.achievements or [],
                "learning_progress": report.learning_progress or "",
                "productivity_analysis": report.productivity_analysis or "",
                "mentor_focus_suggestions": report.mentor_focus_suggestions or [],
                "recommended_next_focus": report.recommended_next_focus or "",
                "overall_weekly_score": report.overall_weekly_score,
                "additional_mentor_notes": report.additional_mentor_notes or "",
            }
        )

    unavailable: list[str] = []
    if not primary_roadmap:
        unavailable.append("No roadmap is available for this program.")
    elif primary_roadmap.status != RoadmapStatus.PUBLISHED:
        unavailable.append(
            "No published roadmap is available; using the latest available roadmap as context."
        )
    if not task_payloads:
        unavailable.append("No tasks are assigned to this intern for this program.")
    if not scored:
        unavailable.append("No scored tasks are available for this intern.")
    if not weekly_payloads:
        unavailable.append("No approved weekly reports are available for this intern.")
    if not any(item["submission_count"] for item in task_payloads):
        unavailable.append("No submissions exist for this intern in this program.")

    final_score = calculate_final_summary_score(intern, program)
    scored_weekly_count = count_scored_weekly_reports(intern, program)
    if final_score is None:
        unavailable.append("No scored approved weekly reports are available for Final Score.")

    return {
        "program": {
            "id": program.id,
            "title": program.title,
            "description": program.description,
            "role": program.role,
            "department": program.department,
            "start_date": _iso_date(program.start_date),
            "end_date": _iso_date(program.end_date),
            "duration_weeks": program.duration_weeks,
            "weekly_hours": program.weekly_hours,
            "goals": program.goals or "",
            "skills_needed": program.skills_needed or [],
            "skills_to_develop": program.skills_to_develop or [],
            "expected_outcome": program.expected_outcome or "",
            "final_project": program.final_project or "",
            "additional_instructions": program.additional_instructions or "",
        },
        "intern": serialize_intern(intern),
        "roadmap": (
            {
                "id": primary_roadmap.id,
                "title": primary_roadmap.title,
                "summary": primary_roadmap.summary,
                "status": primary_roadmap.status,
                "assignment_scope": primary_roadmap.assignment_scope,
                "number_of_weeks": primary_roadmap.number_of_weeks,
            }
            if primary_roadmap
            else None
        ),
        "weeks": weeks_payload,
        "tasks": task_payloads,
        "weekly_reports": weekly_payloads,
        "score_context": {
            "scored_task_count": len(scored),
            "score_values": scored,
            "approved_weekly_scores": [
                item["overall_weekly_score"]
                for item in weekly_payloads
                if item["overall_weekly_score"] is not None
            ],
            "django_final_score": (
                float(final_score) if final_score is not None else None
            ),
            "django_final_score_display": format_final_summary_score_display(final_score),
            "scored_weekly_report_count": scored_weekly_count,
            "note": (
                "Task and weekly scores are supporting evidence only. "
                "The official Final Score is Django-calculated as the average of "
                "APPROVED Weekly Report overall_weekly_score values (nulls excluded). "
                "AI must not invent or override the official Final Score."
            ),
        },
        "summary_rules": {
            "analyze_only_selected_intern": True,
            "analyze_full_internship": True,
            "do_not_invent_activity": True,
            "do_not_fabricate_scores": True,
            "do_not_invent_final_score": True,
            "final_score_is_django_calculated": True,
            "do_not_treat_unscored_as_zero": True,
            "needs_revision_is_not_automatic_failure": True,
            "do_not_compare_against_other_interns": True,
            "do_not_make_hiring_recommendations": True,
            "approved_weekly_reports_are_supporting_only": True,
            "underlying_task_records_are_authoritative": True,
            "mentor_comments_and_notes_are_manual": True,
            "generate_only_five_sections": True,
        },
        "unavailable_data": unavailable,
        "skill_level_labels": SKILL_LEVEL_LABELS,
    }
