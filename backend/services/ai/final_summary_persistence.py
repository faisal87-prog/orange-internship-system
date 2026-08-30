"""Persist AI final summaries as DRAFT (update existing Draft for same intern+program)."""

from __future__ import annotations

from django.db import transaction

from apps.programs.models import InternProfile, InternshipProgram
from apps.reports.models import FinalInternshipSummary
from common.constants import AiContentStatus
from services.ai.exceptions import AIPersistenceError, AIValidationError
from services.ai.schemas import GeneratedFinalSummary
from services.ai.weekly_report_validators import text_to_list
from services.final_summary_score import refresh_final_summary_score


@transaction.atomic
def persist_generated_final_summary(
    *,
    program: InternshipProgram,
    intern: InternProfile,
    generated: GeneratedFinalSummary,
) -> FinalInternshipSummary:
    try:
        existing = (
            FinalInternshipSummary.objects.select_for_update()
            .filter(intern=intern, program=program)
            .first()
        )
        if existing and existing.status == AiContentStatus.APPROVED:
            raise AIValidationError(
                "An approved final summary already exists for this intern and program. "
                "Regeneration is not available for approved summaries."
            )

        payload = {
            "internship_introduction": generated.internship_introduction.strip(),
            "training_summary": generated.training_summary.strip(),
            "overall_performance_summary": generated.overall_performance_summary.strip(),
            "learning_journey": generated.learning_journey.strip(),
            "main_achievements": text_to_list(generated.main_achievements),
            "goal_achievement": generated.goal_achievement.strip(),
            "final_performance_summary": generated.final_performance_summary.strip(),
            "status": AiContentStatus.DRAFT,
            "generated_by_ai": True,
            "approved_by": None,
            "approved_at": None,
        }

        if existing:
            for key, value in payload.items():
                setattr(existing, key, value)
            # Preserve mentor-controlled comments/notes across regenerate.
            existing.pdf_file = None
            existing.save()
            refresh_final_summary_score(existing)
            return (
                FinalInternshipSummary.objects.select_related(
                    "intern__user", "program", "approved_by"
                ).get(pk=existing.pk)
            )

        summary = FinalInternshipSummary.objects.create(
            intern=intern,
            program=program,
            final_score=None,
            mentor_comments="",
            additional_mentor_notes="",
            **payload,
        )
        refresh_final_summary_score(summary)
        return (
            FinalInternshipSummary.objects.select_related(
                "intern__user", "program", "approved_by"
            ).get(pk=summary.pk)
        )
    except AIValidationError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise AIPersistenceError(
            "AI final summary generation succeeded but could not be saved. Please try again."
        ) from exc
