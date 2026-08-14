"""Persist validated AI roadmaps as DRAFT records (no TaskAssignments)."""

from __future__ import annotations

from datetime import date

from django.db import transaction

from apps.programs.models import InternshipProgram, InternProfile
from apps.roadmaps.models import Roadmap, RoadmapWeek
from apps.tasks.models import Task
from common.constants import RoadmapStatus, TaskSource
from services.ai.exceptions import AIPersistenceError
from services.ai.schemas import GeneratedRoadmap
from services.ai.validators import compute_week_dates


@transaction.atomic
def persist_generated_roadmap(
    *,
    program: InternshipProgram,
    assignment_scope: str,
    interns: list[InternProfile],
    generated: GeneratedRoadmap,
    created_by,
) -> Roadmap:
    try:
        roadmap = Roadmap.objects.create(
            program=program,
            title=generated.title.strip(),
            summary=generated.summary.strip(),
            assignment_scope=assignment_scope,
            number_of_weeks=generated.number_of_weeks,
            status=RoadmapStatus.DRAFT,
            generated_by_ai=True,
        )
        if assignment_scope != "PROGRAM" and interns:
            roadmap.assigned_interns.set(interns)

        for week_data in sorted(generated.weeks, key=lambda item: item.week_number):
            start_date, end_date = compute_week_dates(
                program.start_date,
                program.end_date,
                week_data.week_number,
                generated.number_of_weeks,
            )
            week = RoadmapWeek.objects.create(
                roadmap=roadmap,
                week_number=week_data.week_number,
                weekly_focus=week_data.weekly_focus.strip(),
                learning_objectives=week_data.learning_objectives,
                expected_skills_gained=week_data.expected_skills_gained,
                mentor_notes=week_data.mentor_notes or "",
                start_date=start_date,
                end_date=end_date,
                display_order=week_data.week_number,
            )
            for index, task_data in enumerate(week_data.tasks):
                Task.objects.create(
                    roadmap_week=week,
                    program=program,
                    created_by=created_by,
                    title=task_data.title.strip(),
                    description=task_data.description.strip(),
                    difficulty=task_data.difficulty,
                    estimated_time_minutes=task_data.estimated_time_minutes,
                    deliverable=task_data.deliverable.strip(),
                    success_criteria=task_data.success_criteria.strip(),
                    due_date=date.fromisoformat(task_data.due_date),
                    requirement_type=task_data.requirement_type,
                    source=TaskSource.AI_GENERATED,
                    display_order=index,
                )
        return (
            Roadmap.objects.select_related("program", "approved_by")
            .prefetch_related("weeks__tasks__resources", "assigned_interns")
            .get(pk=roadmap.pk)
        )
    except Exception as exc:  # noqa: BLE001
        raise AIPersistenceError() from exc
