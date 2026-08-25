"""Deterministic Final Summary score from APPROVED Weekly Report scores."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from apps.reports.models import WeeklyReport
from common.constants import AiContentStatus


def calculate_final_summary_score(intern, program) -> Decimal | None:
    """
    Average of APPROVED WeeklyReport.overall_weekly_score values for intern+program.

    Null weekly scores are excluded (never treated as zero).
    Returns None when no scored approved weekly reports exist.
    """
    scores = list(
        WeeklyReport.objects.filter(
            intern=intern,
            program=program,
            status=AiContentStatus.APPROVED,
            overall_weekly_score__isnull=False,
        ).values_list("overall_weekly_score", flat=True)
    )
    if not scores:
        return None
    total = sum(Decimal(int(value)) for value in scores)
    average = total / Decimal(len(scores))
    return average.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def count_scored_weekly_reports(intern, program) -> int:
    return WeeklyReport.objects.filter(
        intern=intern,
        program=program,
        status=AiContentStatus.APPROVED,
        overall_weekly_score__isnull=False,
    ).count()


def format_final_summary_score_display(score: Decimal | float | int | None) -> str:
    if score is None:
        return "No scored weeks available"
    value = Decimal(str(score)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    if value == value.to_integral_value():
        return f"{int(value)} / 100"
    return f"{value} / 100"


def refresh_final_summary_score(summary) -> Decimal | None:
    """Synchronize stored final_score from current APPROVED weekly averages."""
    score = calculate_final_summary_score(summary.intern, summary.program)
    if summary.final_score != score:
        summary.final_score = score
        summary.save(update_fields=["final_score", "updated_at"])
    return score
