from django.utils import timezone
from rest_framework import serializers

from apps.reports.models import FinalInternshipSummary, WeeklyReport
from common.constants import AiContentStatus, Role
from services.final_summary_score import (
    count_scored_weekly_reports,
    refresh_final_summary_score,
)
from services.pdf import generate_final_summary_pdf, generate_weekly_report_pdf
from services.week_performance import (
    build_final_summary_week_performance,
    build_weekly_report_comparison,
)
from services.weekly_score import calculate_overall_weekly_score


class WeeklyReportSerializer(serializers.ModelSerializer):
    intern_name = serializers.CharField(source="intern.user.full_name", read_only=True)
    week_number = serializers.IntegerField(
        source="roadmap_week.week_number",
        read_only=True,
        allow_null=True,
    )
    pdf_url = serializers.SerializerMethodField()
    performance_comparison = serializers.SerializerMethodField()

    class Meta:
        model = WeeklyReport
        fields = [
            "id",
            "intern",
            "intern_name",
            "program",
            "roadmap_week",
            "week_number",
            "performance_summary",
            "achievements",
            "learning_progress",
            "productivity_analysis",
            "mentor_focus_suggestions",
            "recommended_next_focus",
            "overall_weekly_score",
            "additional_mentor_notes",
            "generated_by_ai",
            "status",
            "approved_by",
            "approved_at",
            "pdf_file",
            "pdf_url",
            "performance_comparison",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "overall_weekly_score",
            "generated_by_ai",
            "approved_by",
            "approved_at",
            "pdf_file",
            "pdf_url",
            "performance_comparison",
            "created_at",
            "updated_at",
            "intern_name",
            "week_number",
        ]

    def get_pdf_url(self, obj):
        request = self.context.get("request")
        if obj.pdf_file and request:
            return request.build_absolute_uri(obj.pdf_file.url)
        if obj.pdf_file:
            return obj.pdf_file.url
        return None

    def get_performance_comparison(self, obj):
        return build_weekly_report_comparison(
            intern=obj.intern,
            program=obj.program,
            current_week=obj.roadmap_week,
            current_weekly_score=obj.overall_weekly_score,
        )

    def create(self, validated_data):
        report = WeeklyReport.objects.create(**validated_data)
        report.overall_weekly_score = calculate_overall_weekly_score(
            report.intern,
            report.roadmap_week,
        )
        report.save(update_fields=["overall_weekly_score", "updated_at"])
        return report

    def update(self, instance, validated_data):
        previous_status = instance.status
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.overall_weekly_score = calculate_overall_weekly_score(
            instance.intern,
            instance.roadmap_week,
        )
        if instance.status == AiContentStatus.APPROVED:
            if previous_status != AiContentStatus.APPROVED or not instance.approved_at:
                instance.approved_by = self.context["request"].user
                instance.approved_at = timezone.now()
            instance.save()
            if not instance.pdf_file:
                generate_weekly_report_pdf(instance)
            return instance
        instance.save()
        return instance


class WeeklyReportGeneratePromptSerializer(serializers.Serializer):
    program_id = serializers.IntegerField()
    intern_id = serializers.IntegerField()
    roadmap_week_id = serializers.IntegerField()


class WeeklyReportGenerateContinueSerializer(serializers.Serializer):
    preview_id = serializers.UUIDField()


class FinalSummaryGeneratePromptSerializer(serializers.Serializer):
    program_id = serializers.IntegerField()
    intern_id = serializers.IntegerField()


class FinalSummaryGenerateContinueSerializer(serializers.Serializer):
    preview_id = serializers.UUIDField()


class FinalInternshipSummarySerializer(serializers.ModelSerializer):
    intern_name = serializers.CharField(source="intern.user.full_name", read_only=True)
    pdf_url = serializers.SerializerMethodField()
    pdf_available = serializers.SerializerMethodField()
    final_score = serializers.SerializerMethodField()
    scored_weekly_report_count = serializers.SerializerMethodField()
    week_performance = serializers.SerializerMethodField()

    class Meta:
        model = FinalInternshipSummary
        fields = [
            "id",
            "intern",
            "intern_name",
            "program",
            "overall_performance_summary",
            "learning_journey",
            "main_achievements",
            "goal_achievement",
            "final_performance_summary",
            "final_score",
            "scored_weekly_report_count",
            "week_performance",
            "mentor_comments",
            "additional_mentor_notes",
            "generated_by_ai",
            "status",
            "approved_by",
            "approved_at",
            "pdf_file",
            "pdf_url",
            "pdf_available",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "final_score",
            "scored_weekly_report_count",
            "week_performance",
            "generated_by_ai",
            "approved_by",
            "approved_at",
            "pdf_file",
            "pdf_url",
            "pdf_available",
            "created_at",
            "updated_at",
            "intern_name",
        ]

    def get_pdf_url(self, obj):
        request = self.context.get("request")
        if obj.pdf_file and request:
            return request.build_absolute_uri(obj.pdf_file.url)
        if obj.pdf_file:
            return obj.pdf_file.url
        return None

    def get_pdf_available(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None
        if bool(obj.pdf_file) or obj.status == AiContentStatus.APPROVED:
            return True
        if user and getattr(user, "role", None) == Role.MENTOR:
            return True
        return False

    def get_final_score(self, obj):
        score = refresh_final_summary_score(obj)
        if score is None:
            return None
        return float(score)

    def get_scored_weekly_report_count(self, obj):
        return count_scored_weekly_reports(obj.intern, obj.program)

    def get_week_performance(self, obj):
        return build_final_summary_week_performance(
            intern=obj.intern,
            program=obj.program,
        )

    def update(self, instance, validated_data):
        # Final Score is Django-calculated; ignore any client-provided value.
        validated_data.pop("final_score", None)
        status_value = validated_data.get("status", instance.status)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        refresh_final_summary_score(instance)
        if status_value == AiContentStatus.APPROVED:
            if not instance.approved_at:
                instance.approved_by = self.context["request"].user
                instance.approved_at = timezone.now()
            if not instance.pdf_file:
                generate_final_summary_pdf(instance)
        else:
            # Clear stale PDF after draft edits so regenerated PDF reflects content.
            instance.pdf_file = None
        instance.save()
        return instance
