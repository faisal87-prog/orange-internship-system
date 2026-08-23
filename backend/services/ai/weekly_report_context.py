"""Assemble authoritative weekly-report context for one Intern + one RoadmapWeek."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from django.utils import timezone

from apps.programs.models import InternProfile, InternshipProgram
from apps.roadmaps.models import Roadmap, RoadmapWeek
from apps.submissions.models import Submission
from apps.tasks.models import TaskAssignment
from common.constants import Role, RoadmapStatus, TaskAssignmentStatus
from services.ai.context_assembler import SKILL_LEVEL_LABELS, serialize_intern
from services.ai.exceptions import AIPermissionError, AIValidationError
from services.weekly_score import calculate_overall_weekly_score


def _iso_date(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _iso_dt(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def resolve_weekly_report_targets(
    *,
    mentor,
    program_id: int,
    intern_id: int,
    roadmap_week_id: int,
) -> tuple[InternshipProgram, InternProfile, RoadmapWeek, Roadmap]:
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

    try:
        week = RoadmapWeek.objects.select_related("roadmap", "roadmap__program").get(
            pk=roadmap_week_id
        )
    except RoadmapWeek.DoesNotExist as exc:
        raise AIValidationError("Roadmap week not found.") from exc

    roadmap = week.roadmap
    if roadmap.program_id != program.id:
        raise AIValidationError(
            "The selected week does not belong to this program."
        )
    if roadmap.status != RoadmapStatus.PUBLISHED:
        raise AIValidationError(
            "Weekly reports can only be generated from a published roadmap week."
        )

    return program, intern, week, roadmap


def _serialize_submission(submission: Submission) -> dict[str, Any]:
    files = [
        {
            "original_file_name": item.original_file_name,
            "file_type": item.file_type,
            "file_size": item.file_size,
            "uploaded_at": _iso_dt(item.uploaded_at),
        }
        for item in submission.files.all()
    ]
    return {
        "version_number": submission.version_number,
        "submitted_at": _iso_dt(submission.submitted_at),
        "written_response": submission.written_response or "",
        "intern_notes": submission.intern_notes or "",
        "external_url": submission.external_url or None,
        "files": files,
    }


def _assignment_payload(
    *,
    assignment: TaskAssignment,
    today: date,
) -> dict[str, Any]:
    task = assignment.task
    due = assignment.effective_due_date
    submissions = [
        _serialize_submission(item)
        for item in assignment.submissions.all().order_by("version_number")
    ]
    latest = submissions[-1] if submissions else None
    latest_submitted_at = None
    if latest and latest.get("submitted_at"):
        latest_submitted_at = datetime.fromisoformat(latest["submitted_at"])

    is_completed = assignment.status == TaskAssignmentStatus.COMPLETED
    is_needs_revision = assignment.status == TaskAssignmentStatus.NEEDS_REVISION
    is_late = False
    if latest_submitted_at and due:
        is_late = latest_submitted_at.date() > due
    is_overdue = bool(
        due
        and today > due
        and assignment.status
        not in {TaskAssignmentStatus.COMPLETED, TaskAssignmentStatus.SUBMITTED}
    )

    resources = [
        {
            "title": resource.title,
            "resource_type": resource.resource_type,
            "external_url": resource.external_url or None,
            "has_file": bool(resource.file),
        }
        for resource in task.resources.all()
    ]

    return {
        "assignment_id": assignment.id,
        "task_id": task.id,
        "title": task.title,
        "description": task.description,
        "requirement_type": task.requirement_type,
        "difficulty": task.difficulty,
        "estimated_time_minutes": task.estimated_time_minutes,
        "due_date": _iso_date(due),
        "deliverable": task.deliverable or "",
        "success_criteria": task.success_criteria or "",
        "source": task.source,
        "status": assignment.status,
        "is_completed": is_completed,
        "is_needs_revision": is_needs_revision,
        "score": assignment.score,
        "mentor_feedback": assignment.mentor_feedback or "",
        "reviewed_at": _iso_dt(assignment.reviewed_at),
        "completed_at": _iso_dt(assignment.completed_at),
        "is_late": is_late,
        "is_overdue": is_overdue,
        "due_date_passed": bool(due and today > due),
        "submission_count": len(submissions),
        "submissions": submissions,
        "resources": resources,
    }


def assemble_weekly_report_context(
    *,
    program: InternshipProgram,
    intern: InternProfile,
    week: RoadmapWeek,
    roadmap: Roadmap,
) -> dict[str, Any]:
    today = timezone.localdate()
    assignments = (
        TaskAssignment.objects.filter(
            intern=intern,
            task__roadmap_week=week,
        )
        .select_related("task", "task__program")
        .prefetch_related(
            "task__resources",
            "submissions__files",
        )
        .order_by("task__display_order", "task__id")
    )
    task_payloads = [
        _assignment_payload(assignment=item, today=today) for item in assignments
    ]
    scored = [item["score"] for item in task_payloads if item["score"] is not None]
    weekly_score = calculate_overall_weekly_score(intern, week)

    unavailable: list[str] = []
    if not task_payloads:
        unavailable.append("No tasks are assigned to this intern for the selected week.")
    if weekly_score is None:
        unavailable.append("No scored tasks are available for this week.")
    if not any(item["submission_count"] for item in task_payloads):
        unavailable.append("No submissions exist for this intern in the selected week.")

    return {
        "program": {
            "id": program.id,
            "title": program.title,
            "description": program.description,
            "role": program.role,
            "department": program.department,
            "start_date": _iso_date(program.start_date),
            "end_date": _iso_date(program.end_date),
            "goals": program.goals or "",
            "skills_to_develop": program.skills_to_develop or [],
            "expected_outcome": program.expected_outcome or "",
            "final_project": program.final_project or "",
            "weekly_hours": program.weekly_hours,
        },
        "intern": serialize_intern(intern),
        "roadmap": {
            "id": roadmap.id,
            "title": roadmap.title,
            "summary": roadmap.summary,
            "status": roadmap.status,
            "assignment_scope": roadmap.assignment_scope,
            "number_of_weeks": roadmap.number_of_weeks,
        },
        "week": {
            "id": week.id,
            "week_number": week.week_number,
            "weekly_focus": week.weekly_focus,
            "learning_objectives": week.learning_objectives or [],
            "expected_skills_gained": week.expected_skills_gained or [],
            "mentor_notes": week.mentor_notes or "",
            "start_date": _iso_date(week.start_date),
            "end_date": _iso_date(week.end_date),
        },
        "tasks": task_payloads,
        "weekly_score": {
            "overall_weekly_score": weekly_score,
            "scored_task_count": len(scored),
            "score_values": scored,
            "display": (
                f"{weekly_score} / 100"
                if weekly_score is not None
                else "No scored tasks available for this week."
            ),
            "calculation_note": (
                "Average of scored TaskAssignments only. "
                "Unscored tasks, including Needs Revision without a score, "
                "are excluded and never treated as zero."
            ),
        },
        "report_rules": {
            "analyze_only_selected_intern_and_week": True,
            "do_not_invent_activity": True,
            "do_not_fabricate_scores": True,
            "do_not_treat_unscored_as_zero": True,
            "needs_revision_is_not_automatic_failure": True,
            "do_not_compare_against_other_interns": True,
            "do_not_make_hiring_recommendations": True,
            "do_not_modify_roadmap_or_tasks": True,
            "additional_mentor_notes_are_manual": True,
            "overall_weekly_score_is_django_calculated": True,
        },
        "unavailable_data": unavailable,
        "skill_level_labels": SKILL_LEVEL_LABELS,
    }
