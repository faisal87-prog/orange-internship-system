"""One-off demo seed: ONLY the target Program / Interns / 20 published Roadmap tasks."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.programs.models import InternProfile, InternshipProgram
from apps.reports.models import FinalInternshipSummary, WeeklyReport
from apps.roadmaps.models import Roadmap
from apps.submissions.models import Submission
from apps.tasks.models import Task, TaskAssignment
from common.constants import RoadmapStatus, Role, TaskAssignmentStatus

PROGRAM_TITLE = "AI Internship Management Platform Development"
MENTOR_FULL_NAME = "Ahmad Mashaaleh"
INTERN_FULL_NAMES = ("Faisal Quntar", "Samir Aboud")
EXPECTED_TASK_COUNT = 20
SCORE_SEED = 20260830
SCORE_MIN = 85
SCORE_MAX = 100

WRITTEN_RESPONSE = (
    "Completed the assigned task successfully as part of the AI Internship "
    "Management Platform development. The required work was implemented, "
    "reviewed, tested, and validated according to the agreed MVP requirements."
)

MENTOR_FEEDBACK_POOL = (
    "Completed successfully. The required work was implemented and tested according to the agreed internship scope.",
    "Strong completion of the assigned work. The implementation met the expected requirements and was validated successfully.",
    "The task was completed well and the required functionality was implemented, reviewed, and tested.",
    "Good implementation and validation of the assigned work. The expected task outcome was achieved.",
    "The required work was delivered successfully with appropriate testing and alignment with the project requirements.",
    "Very good completion of the task. The work met the expected deliverable and was tested successfully.",
)


@dataclass
class InternSeedStats:
    full_name: str
    intern_id: int
    assignments_found: int = 0
    processed: int = 0
    skipped: int = 0
    scores: list[int] = field(default_factory=list)

    @property
    def average_score(self) -> float | None:
        if not self.scores:
            return None
        return round(sum(self.scores) / len(self.scores), 1)


@dataclass
class SeedContext:
    program: InternshipProgram
    mentor: User
    roadmap: Roadmap
    tasks: list[Task]
    interns: list[InternProfile]
    assignments_by_intern: dict[int, list[TaskAssignment]]


def _unique_user(*, full_name: str, role: str) -> User:
    qs = User.objects.filter(full_name=full_name, role=role)
    count = qs.count()
    if count == 0:
        raise CommandError(f"Could not find unique {role} named '{full_name}'. No data was changed.")
    if count > 1:
        raise CommandError(
            f"Multiple {role} users named '{full_name}' found ({count}). No data was changed."
        )
    return qs.get()


def _resolve_target_program() -> InternshipProgram:
    qs = InternshipProgram.objects.filter(title=PROGRAM_TITLE).select_related("mentor")
    count = qs.count()
    if count == 0:
        raise CommandError(
            f"Program '{PROGRAM_TITLE}' not found. No data was changed."
        )
    if count > 1:
        raise CommandError(
            f"Multiple programs titled '{PROGRAM_TITLE}' found ({count}). No data was changed."
        )
    return qs.get()


def _resolve_published_roadmap(program: InternshipProgram) -> Roadmap:
    qs = Roadmap.objects.filter(program_id=program.id, status=RoadmapStatus.PUBLISHED)
    count = qs.count()
    if count == 0:
        raise CommandError(
            f"No published Roadmap found for '{PROGRAM_TITLE}'. No data was changed."
        )
    if count > 1:
        raise CommandError(
            f"Multiple published Roadmaps found for '{PROGRAM_TITLE}' ({count}). "
            "No data was changed."
        )
    return qs.get()


def _resolve_roadmap_tasks(*, program: InternshipProgram, roadmap: Roadmap) -> list[Task]:
    tasks = list(
        Task.objects.filter(
            program_id=program.id,
            roadmap_week__roadmap_id=roadmap.id,
        )
        .select_related("roadmap_week")
        .order_by("roadmap_week__week_number", "display_order", "due_date", "id")
    )
    count = len(tasks)
    if count != EXPECTED_TASK_COUNT:
        raise CommandError(
            f"Expected exactly {EXPECTED_TASK_COUNT} tasks for {PROGRAM_TITLE}, "
            f"found {count}. No data was changed."
        )
    # Hard isolation: every task must belong to the target program + roadmap.
    for task in tasks:
        if task.program_id != program.id:
            raise CommandError(
                f"Task {task.id} is not scoped to target Program. No data was changed."
            )
        if task.roadmap_week_id is None or task.roadmap_week.roadmap_id != roadmap.id:
            raise CommandError(
                f"Task {task.id} is not on the target published Roadmap. No data was changed."
            )
    return tasks


def _resolve_target_interns(*, program: InternshipProgram) -> list[InternProfile]:
    resolved: list[InternProfile] = []
    for full_name in INTERN_FULL_NAMES:
        user = _unique_user(full_name=full_name, role=Role.INTERN)
        try:
            intern = InternProfile.objects.select_related("user", "program").get(user=user)
        except InternProfile.DoesNotExist as exc:
            raise CommandError(
                f"Intern profile for '{full_name}' not found. No data was changed."
            ) from exc
        if intern.program_id != program.id:
            raise CommandError(
                f"Intern '{full_name}' is not assigned to '{PROGRAM_TITLE}'. "
                "No data was changed."
            )
        resolved.append(intern)
    return resolved


def _load_target_assignments(
    *,
    program: InternshipProgram,
    roadmap: Roadmap,
    tasks: list[Task],
    interns: list[InternProfile],
) -> dict[int, list[TaskAssignment]]:
    task_ids = [task.id for task in tasks]
    intern_ids = [intern.id for intern in interns]
    by_intern: dict[int, list[TaskAssignment]] = {intern.id: [] for intern in interns}

    for intern in interns:
        for task in tasks:
            qs = TaskAssignment.objects.filter(
                task_id=task.id,
                task__program_id=program.id,
                task__roadmap_week__roadmap_id=roadmap.id,
                intern_id=intern.id,
            ).select_related("task", "intern__user")
            count = qs.count()
            if count == 0:
                raise CommandError(
                    f"Missing TaskAssignment for intern '{intern.user.full_name}' "
                    f"on task '{task.title}' (id={task.id}). No data was changed."
                )
            if count > 1:
                raise CommandError(
                    f"Duplicate TaskAssignments for intern '{intern.user.full_name}' "
                    f"on task id={task.id}. No data was changed."
                )
            assignment = qs.get()
            # Extra isolation guards
            if assignment.task_id not in task_ids:
                raise CommandError("Assignment outside target task set. No data was changed.")
            if assignment.intern_id not in intern_ids:
                raise CommandError("Assignment outside target intern set. No data was changed.")
            by_intern[intern.id].append(assignment)
    return by_intern


def _has_existing_history(assignment: TaskAssignment) -> bool:
    if Submission.objects.filter(task_assignment_id=assignment.id).exists():
        return True
    if assignment.score is not None:
        return True
    if assignment.status == TaskAssignmentStatus.COMPLETED:
        return True
    if (assignment.mentor_feedback or "").strip():
        return True
    if assignment.reviewed_at is not None:
        return True
    return False


def _aware_on_due_date(due_date, hour: int, minute: int = 0):
    naive = datetime.combine(due_date, time(hour=hour, minute=minute))
    if timezone.is_naive(naive):
        return timezone.make_aware(naive, timezone.get_current_timezone())
    return naive


def validate_and_load_targets() -> SeedContext:
    program = _resolve_target_program()
    mentor = program.mentor
    if mentor.full_name != MENTOR_FULL_NAME or mentor.role != Role.MENTOR:
        raise CommandError(
            f"Program Mentor must be '{MENTOR_FULL_NAME}'. "
            f"Found '{mentor.full_name}'. No data was changed."
        )
    # Also ensure the named mentor resolves uniquely and matches program.mentor_id
    named_mentor = _unique_user(full_name=MENTOR_FULL_NAME, role=Role.MENTOR)
    if named_mentor.id != mentor.id:
        raise CommandError(
            f"Program Mentor relationship does not match unique user '{MENTOR_FULL_NAME}'. "
            "No data was changed."
        )

    roadmap = _resolve_published_roadmap(program)
    tasks = _resolve_roadmap_tasks(program=program, roadmap=roadmap)
    interns = _resolve_target_interns(program=program)
    assignments = _load_target_assignments(
        program=program,
        roadmap=roadmap,
        tasks=tasks,
        interns=interns,
    )
    return SeedContext(
        program=program,
        mentor=mentor,
        roadmap=roadmap,
        tasks=tasks,
        interns=interns,
        assignments_by_intern=assignments,
    )


def _print_validation(stdout, style, ctx: SeedContext) -> None:
    stdout.write(style.SUCCESS("TARGET VALIDATION PASSED"))
    stdout.write("")
    stdout.write("Program:")
    stdout.write(ctx.program.title)
    stdout.write("")
    stdout.write("Mentor:")
    stdout.write(f"{ctx.mentor.full_name} (user_id={ctx.mentor.id})")
    stdout.write("")
    stdout.write("Interns:")
    for intern in ctx.interns:
        stdout.write(
            f"{intern.user.full_name} (intern_id={intern.id}, user_id={intern.user_id})"
        )
    stdout.write("")
    stdout.write("Published Roadmap:")
    stdout.write(f"{ctx.roadmap.id} / {ctx.roadmap.title}")
    stdout.write("")
    stdout.write("Tasks found:")
    stdout.write(str(len(ctx.tasks)))
    stdout.write("")
    for index, task in enumerate(ctx.tasks, start=1):
        stdout.write(f"Task {index}: {task.title} (id={task.id})")
    stdout.write("")


def process_seed(ctx: SeedContext) -> dict[str, Any]:
    """Apply writes for validated targets only. Safe to call inside atomic()."""
    rng = random.Random(SCORE_SEED)
    stats: dict[int, InternSeedStats] = {
        intern.id: InternSeedStats(
            full_name=intern.user.full_name,
            intern_id=intern.id,
            assignments_found=len(ctx.assignments_by_intern[intern.id]),
        )
        for intern in ctx.interns
    }
    target_assignment_ids = {
        assignment.id
        for assignments in ctx.assignments_by_intern.values()
        for assignment in assignments
    }
    target_task_ids = {task.id for task in ctx.tasks}
    target_intern_ids = {intern.id for intern in ctx.interns}

    weekly_before = WeeklyReport.objects.count()
    final_before = FinalInternshipSummary.objects.count()
    unrelated_assignment_touch = 0
    unrelated_task_touch = 0
    unrelated_intern_touch = 0

    for intern in ctx.interns:
        intern_stats = stats[intern.id]
        for assignment in ctx.assignments_by_intern[intern.id]:
            # Isolation asserts on every write candidate
            if assignment.id not in target_assignment_ids:
                unrelated_assignment_touch += 1
                continue
            if assignment.task_id not in target_task_ids:
                unrelated_task_touch += 1
                continue
            if assignment.intern_id not in target_intern_ids:
                unrelated_intern_touch += 1
                continue
            if assignment.task.program_id != ctx.program.id:
                unrelated_task_touch += 1
                continue

            if _has_existing_history(assignment):
                intern_stats.skipped += 1
                continue

            score = rng.randint(SCORE_MIN, SCORE_MAX)
            feedback = rng.choice(MENTOR_FEEDBACK_POOL)
            due = assignment.effective_due_date
            submitted_at = _aware_on_due_date(due, hour=10)
            reviewed_at = _aware_on_due_date(due, hour=15)

            submission = Submission.objects.create(
                task_assignment_id=assignment.id,
                version_number=1,
                written_response=WRITTEN_RESPONSE,
                external_url="",
                intern_notes="",
            )
            Submission.objects.filter(pk=submission.pk, task_assignment_id=assignment.id).update(
                submitted_at=submitted_at,
                created_at=submitted_at,
                updated_at=submitted_at,
            )

            updated = TaskAssignment.objects.filter(
                pk=assignment.id,
                task_id=assignment.task_id,
                intern_id=assignment.intern_id,
                task__program_id=ctx.program.id,
                task__roadmap_week__roadmap_id=ctx.roadmap.id,
            ).update(
                status=TaskAssignmentStatus.COMPLETED,
                score=score,
                mentor_feedback=feedback,
                reviewed_at=reviewed_at,
                completed_at=reviewed_at,
            )
            if updated != 1:
                raise CommandError(
                    f"Failed to update exactly one target assignment id={assignment.id}. "
                    "Rolling back."
                )

            intern_stats.processed += 1
            intern_stats.scores.append(score)

    weekly_after = WeeklyReport.objects.count()
    final_after = FinalInternshipSummary.objects.count()

    return {
        "stats": stats,
        "weekly_reports_created": weekly_after - weekly_before,
        "final_summaries_created": final_after - final_before,
        "unrelated_programs_modified": 0,
        "unrelated_interns_modified": unrelated_intern_touch,
        "unrelated_tasks_modified": unrelated_task_touch,
        "unrelated_assignments_modified": unrelated_assignment_touch,
        "total_target_assignments": sum(
            len(items) for items in ctx.assignments_by_intern.values()
        ),
    }


def _print_results(stdout, style, ctx: SeedContext, result: dict[str, Any]) -> None:
    stats: dict[int, InternSeedStats] = result["stats"]
    for intern in ctx.interns:
        row = stats[intern.id]
        avg = row.average_score
        stdout.write("")
        stdout.write(row.full_name)
        stdout.write(f"Assignments found: {row.assignments_found}")
        stdout.write(f"Processed: {row.processed}")
        stdout.write(f"Skipped: {row.skipped}")
        stdout.write(f"Average score: {avg if avg is not None else 'n/a'}")

    stdout.write("")
    stdout.write("Total target TaskAssignments:")
    stdout.write(str(result["total_target_assignments"]))
    stdout.write("")
    stdout.write("Unrelated Programs modified:")
    stdout.write(str(result["unrelated_programs_modified"]))
    stdout.write("Unrelated Interns modified:")
    stdout.write(str(result["unrelated_interns_modified"]))
    stdout.write("Unrelated Tasks modified:")
    stdout.write(str(result["unrelated_tasks_modified"]))
    stdout.write("Weekly Reports created:")
    stdout.write(str(result["weekly_reports_created"]))
    stdout.write("Final Summaries created:")
    stdout.write(str(result["final_summaries_created"]))

    skipped_total = sum(stats[i.id].skipped for i in ctx.interns)
    if skipped_total:
        stdout.write("")
        stdout.write(
            style.WARNING(
                f"Note: {skipped_total} assignment(s) skipped due to existing history."
            )
        )


class Command(BaseCommand):
    help = (
        "ONE-OFF seed: complete Faisal Quntar + Samir Aboud assignments for the "
        "exact 20 published tasks on 'AI Internship Management Platform Development' only."
    )

    def handle(self, *args, **options):
        # Validation phase — no writes.
        ctx = validate_and_load_targets()
        _print_validation(self.stdout, self.style, ctx)

        # Write phase — atomic, scoped.
        with transaction.atomic():
            # Re-check task count inside the transaction before writes.
            live_count = Task.objects.filter(
                program_id=ctx.program.id,
                roadmap_week__roadmap_id=ctx.roadmap.id,
            ).count()
            if live_count != EXPECTED_TASK_COUNT:
                raise CommandError(
                    f"Expected exactly {EXPECTED_TASK_COUNT} tasks for {PROGRAM_TITLE}, "
                    f"found {live_count}. No data was changed."
                )

            # Emit skip notices while processing
            for intern in ctx.interns:
                for assignment in ctx.assignments_by_intern[intern.id]:
                    if _has_existing_history(assignment):
                        self.stdout.write(
                            self.style.WARNING(
                                "SKIPPED — existing task history found: "
                                f"{intern.user.full_name} / {assignment.task.title}"
                            )
                        )

            result = process_seed(ctx)
            if result["weekly_reports_created"] != 0 or result["final_summaries_created"] != 0:
                raise CommandError(
                    "Unexpected Weekly Report or Final Summary creation detected. Rolling back."
                )
            if (
                result["unrelated_interns_modified"]
                or result["unrelated_tasks_modified"]
                or result["unrelated_assignments_modified"]
            ):
                raise CommandError(
                    "Unrelated record modification detected. Rolling back."
                )

        _print_results(self.stdout, self.style, ctx, result)
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Seed completed successfully."))
