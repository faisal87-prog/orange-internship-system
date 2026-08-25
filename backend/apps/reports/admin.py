from django.contrib import admin

from apps.reports.models import FinalInternshipSummary, WeeklyReport


@admin.register(WeeklyReport)
class WeeklyReportAdmin(admin.ModelAdmin):
    list_display = ("intern", "program", "status", "overall_weekly_score", "approved_at")
    list_filter = ("status",)
    search_fields = ("intern__user__full_name", "program__title")


@admin.register(FinalInternshipSummary)
class FinalInternshipSummaryAdmin(admin.ModelAdmin):
    list_display = (
        "intern",
        "program",
        "status",
        "final_score",
        "generated_by_ai",
        "approved_at",
    )
    list_filter = ("status", "generated_by_ai")
    search_fields = ("intern__user__full_name", "program__title")
    readonly_fields = (
        "overall_performance_summary",
        "learning_journey",
        "main_achievements",
        "goal_achievement",
        "final_performance_summary",
        "final_score",
        "mentor_comments",
        "additional_mentor_notes",
        "generated_by_ai",
        "status",
        "approved_by",
        "approved_at",
        "pdf_file",
        "created_at",
        "updated_at",
    )
