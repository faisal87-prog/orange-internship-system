from django.utils import timezone
from rest_framework import serializers

from apps.reports.models import FinalInternshipSummary, WeeklyReport
from common.constants import AiContentStatus
from common.validators import validate_score
from services.pdf import generate_final_summary_pdf, generate_weekly_report_pdf
from services.weekly_score import calculate_overall_weekly_score


class WeeklyReportSerializer(serializers.ModelSerializer):
    intern_name = serializers.CharField(source="intern.user.full_name", read_only=True)
    week_number = serializers.IntegerField(
        source="roadmap_week.week_number",
        read_only=True,
        allow_null=True,
    )
    pdf_url = serializers.SerializerMethodField()

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


class FinalInternshipSummarySerializer(serializers.ModelSerializer):
    intern_name = serializers.CharField(source="intern.user.full_name", read_only=True)
    pdf_url = serializers.SerializerMethodField()
    pdf_available = serializers.SerializerMethodField()

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
            "mentor_comments",
            "additional_mentor_notes",
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
        return bool(obj.pdf_file) or obj.status == AiContentStatus.APPROVED

    def validate_final_score(self, value):
        validate_score(value)
        return value

    def update(self, instance, validated_data):
        status_value = validated_data.get("status", instance.status)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if status_value == AiContentStatus.APPROVED:
            if not instance.approved_at:
                instance.approved_by = self.context["request"].user
                instance.approved_at = timezone.now()
            if not instance.pdf_file:
                generate_final_summary_pdf(instance)
        instance.save()
        return instance
