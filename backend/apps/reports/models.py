from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.programs.models import InternshipProgram, InternProfile
from apps.roadmaps.models import RoadmapWeek
from common.constants import AiContentStatus, Role


class WeeklyReport(models.Model):
    intern = models.ForeignKey(
        InternProfile,
        on_delete=models.CASCADE,
        related_name="weekly_reports",
    )
    program = models.ForeignKey(
        InternshipProgram,
        on_delete=models.CASCADE,
        related_name="weekly_reports",
    )
    roadmap_week = models.ForeignKey(
        RoadmapWeek,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="weekly_reports",
    )
    performance_summary = models.TextField(blank=True)
    achievements = models.JSONField(default=list, blank=True)
    learning_progress = models.TextField(blank=True)
    productivity_analysis = models.TextField(blank=True)
    mentor_focus_suggestions = models.JSONField(default=list, blank=True)
    recommended_next_focus = models.TextField(blank=True)
    overall_weekly_score = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    additional_mentor_notes = models.TextField(blank=True)
    generated_by_ai = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=AiContentStatus.CHOICES,
        default=AiContentStatus.DRAFT,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_weekly_reports",
        limit_choices_to={"role": Role.MENTOR},
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    pdf_file = models.FileField(upload_to="weekly_report_pdfs/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["intern", "roadmap_week"],
                condition=models.Q(roadmap_week__isnull=False),
                name="unique_weekly_report_intern_week",
            )
        ]
    def __str__(self):
        week = self.roadmap_week.week_number if self.roadmap_week else "?"
        return f"Week {week} report · {self.intern.user.full_name}"


class FinalInternshipSummary(models.Model):
    intern = models.ForeignKey(
        InternProfile,
        on_delete=models.CASCADE,
        related_name="final_summaries",
    )
    program = models.ForeignKey(
        InternshipProgram,
        on_delete=models.CASCADE,
        related_name="final_summaries",
    )
    overall_performance_summary = models.TextField(blank=True)
    learning_journey = models.TextField(blank=True)
    main_achievements = models.JSONField(default=list, blank=True)
    goal_achievement = models.TextField(blank=True)
    final_performance_summary = models.TextField(blank=True)
    final_score = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    mentor_comments = models.TextField(blank=True)
    additional_mentor_notes = models.TextField(blank=True)
    generated_by_ai = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=AiContentStatus.CHOICES,
        default=AiContentStatus.DRAFT,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_final_summaries",
        limit_choices_to={"role": Role.MENTOR},
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    pdf_file = models.FileField(upload_to="final_summary_pdfs/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Final internship summaries"
        constraints = [
            models.UniqueConstraint(
                fields=["intern", "program"],
                name="unique_final_summary_intern_program",
            )
        ]
    def __str__(self):
        return f"Final summary · {self.intern.user.full_name}"
