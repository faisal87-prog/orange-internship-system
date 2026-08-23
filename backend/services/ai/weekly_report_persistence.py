"""Persist AI weekly reports as DRAFT (update existing Draft for same intern+week)."""

from __future__ import annotations

from django.db import transaction

from apps.programs.models import InternProfile, InternshipProgram
from apps.reports.models import WeeklyReport
from apps.roadmaps.models import RoadmapWeek
from common.constants import AiContentStatus
from services.ai.exceptions import AIPersistenceError, AIValidationError
from services.ai.schemas import GeneratedWeeklyReport
from services.ai.weekly_report_validators import text_to_list
from services.weekly_score import calculate_overall_weekly_score


@transaction.atomic
def persist_generated_weekly_report(
    *,
    program: InternshipProgram,
    intern: InternProfile,
    week: RoadmapWeek,
    generated: GeneratedWeeklyReport,
) -> WeeklyReport:
    try:
        existing = (
            WeeklyReport.objects.select_for_update()
            .filter(intern=intern, roadmap_week=week)
            .first()
        )
        if existing and existing.status == AiContentStatus.APPROVED:
            raise AIValidationError(
                "An approved weekly report already exists for this intern and week. "
                "Regeneration is not available for approved reports."
            )

        score = calculate_overall_weekly_score(intern, week)
        payload = {
            "program": program,
            "performance_summary": generated.performance_summary.strip(),
            "achievements": text_to_list(generated.achievements),
            "learning_progress": generated.learning_progress.strip(),
            "productivity_analysis": generated.productivity_analysis.strip(),
            "mentor_focus_suggestions": text_to_list(generated.mentor_focus_suggestions),
            "recommended_next_focus": generated.recommended_next_focus.strip(),
            "overall_weekly_score": score,
            "status": AiContentStatus.DRAFT,
            "generated_by_ai": True,
            "approved_by": None,
            "approved_at": None,
        }

        if existing:
            for key, value in payload.items():
                setattr(existing, key, value)
            # Preserve manual mentor notes across regenerate.
            existing.pdf_file = None
            existing.save()
            return (
                WeeklyReport.objects.select_related(
                    "intern__user", "program", "roadmap_week", "approved_by"
                ).get(pk=existing.pk)
            )

        report = WeeklyReport.objects.create(
            intern=intern,
            roadmap_week=week,
            additional_mentor_notes="",
            **payload,
        )
        return (
            WeeklyReport.objects.select_related(
                "intern__user", "program", "roadmap_week", "approved_by"
            ).get(pk=report.pk)
        )
    except AIValidationError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise AIPersistenceError(
            "AI weekly report generation succeeded but could not be saved. Please try again."
        ) from exc
