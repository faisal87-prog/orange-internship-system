from django.http import FileResponse, Http404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.reports.models import FinalInternshipSummary, WeeklyReport
from apps.reports.serializers import (
    FinalInternshipSummarySerializer,
    FinalSummaryGenerateContinueSerializer,
    FinalSummaryGeneratePromptSerializer,
    WeeklyReportGenerateContinueSerializer,
    WeeklyReportGeneratePromptSerializer,
    WeeklyReportSerializer,
)
from common.constants import AiContentStatus, Role
from permissions.roles import IsMentor
from services.ai.final_summary_service import (
    build_ai_final_summary_prompt_preview,
    continue_ai_final_summary_generation,
    to_final_summary_api_error_payload,
)
from services.ai.weekly_report_service import (
    build_ai_weekly_report_prompt_preview,
    continue_ai_weekly_report_generation,
    to_weekly_report_api_error_payload,
)
from services.pdf import (
    final_summary_pdf_filename,
    generate_final_summary_pdf,
    generate_weekly_report_pdf,
    weekly_report_pdf_filename,
)
from services.weekly_score import refresh_weekly_report_score


class WeeklyReportViewSet(viewsets.ModelViewSet):
    serializer_class = WeeklyReportSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = WeeklyReport.objects.select_related(
            "intern__user",
            "program",
            "roadmap_week",
            "approved_by",
        )
        if user.role == Role.ADMIN:
            return qs
        if user.role == Role.MENTOR:
            return qs.filter(program__mentor=user)
        if user.role == Role.INTERN and hasattr(user, "intern_profile"):
            return qs.filter(
                intern=user.intern_profile,
                status=AiContentStatus.APPROVED,
            )
        return qs.none()

    def get_permissions(self):
        if self.action in {
            "create",
            "update",
            "partial_update",
            "destroy",
            "approve",
            "refresh_score",
            "generate_prompt",
            "generate_continue",
        }:
            return [IsMentor()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        program = serializer.validated_data["program"]
        if program.mentor_id != self.request.user.id:
            raise PermissionDenied("Not your program.")
        serializer.save()

    def perform_update(self, serializer):
        report = self.get_object()
        if report.program.mentor_id != self.request.user.id:
            raise PermissionDenied("Not your report.")
        serializer.save()

    @action(detail=False, methods=["post"], url_path="generate/prompt")
    def generate_prompt(self, request):
        serializer = WeeklyReportGeneratePromptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            preview = build_ai_weekly_report_prompt_preview(
                mentor=request.user,
                program_id=serializer.validated_data["program_id"],
                intern_id=serializer.validated_data["intern_id"],
                roadmap_week_id=serializer.validated_data["roadmap_week_id"],
            )
        except Exception as exc:  # noqa: BLE001
            status_code, payload = to_weekly_report_api_error_payload(exc)
            return Response(payload, status=status_code)
        return Response(preview, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="generate/continue")
    def generate_continue(self, request):
        serializer = WeeklyReportGenerateContinueSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            report = continue_ai_weekly_report_generation(
                mentor=request.user,
                preview_id=str(serializer.validated_data["preview_id"]),
            )
        except Exception as exc:  # noqa: BLE001
            status_code, payload = to_weekly_report_api_error_payload(exc)
            return Response(payload, status=status_code)
        return Response(
            WeeklyReportSerializer(report, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        report = self.get_object()
        if report.program.mentor_id != request.user.id:
            return Response({"detail": "Not your report."}, status=status.HTTP_403_FORBIDDEN)
        report.status = AiContentStatus.APPROVED
        report.approved_by = request.user
        from django.utils import timezone

        report.approved_at = timezone.now()
        refresh_weekly_report_score(report)
        generate_weekly_report_pdf(report)
        report.refresh_from_db()
        return Response(WeeklyReportSerializer(report, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def refresh_score(self, request, pk=None):
        report = self.get_object()
        if report.program.mentor_id != request.user.id:
            return Response({"detail": "Not your report."}, status=status.HTTP_403_FORBIDDEN)
        refresh_weekly_report_score(report)
        return Response(WeeklyReportSerializer(report, context={"request": request}).data)

    @action(detail=True, methods=["get"])
    def download_pdf(self, request, pk=None):
        report = self.get_object()
        if request.user.role == Role.INTERN and report.status != AiContentStatus.APPROVED:
            raise PermissionDenied("Only approved reports are available.")
        if not report.pdf_file:
            if report.status == AiContentStatus.APPROVED:
                generate_weekly_report_pdf(report)
            elif request.user.role == Role.MENTOR and report.program.mentor_id == request.user.id:
                generate_weekly_report_pdf(report, draft_watermark=True)
            else:
                raise Http404("PDF not available.")
        return FileResponse(
            report.pdf_file.open("rb"),
            as_attachment=True,
            filename=weekly_report_pdf_filename(report),
        )

class FinalInternshipSummaryViewSet(viewsets.ModelViewSet):
    serializer_class = FinalInternshipSummarySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = FinalInternshipSummary.objects.select_related(
            "intern__user",
            "program",
            "approved_by",
        )
        if user.role == Role.ADMIN:
            return qs
        if user.role == Role.MENTOR:
            return qs.filter(program__mentor=user)
        if user.role == Role.INTERN and hasattr(user, "intern_profile"):
            return qs.filter(
                intern=user.intern_profile,
                status=AiContentStatus.APPROVED,
            )
        return qs.none()

    def get_permissions(self):
        if self.action in {
            "create",
            "update",
            "partial_update",
            "destroy",
            "approve",
            "generate_prompt",
            "generate_continue",
        }:
            return [IsMentor()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        program = serializer.validated_data["program"]
        if program.mentor_id != self.request.user.id:
            raise PermissionDenied("Not your program.")
        serializer.save()

    def perform_update(self, serializer):
        summary = self.get_object()
        if summary.program.mentor_id != self.request.user.id:
            raise PermissionDenied("Not your summary.")
        if summary.status == AiContentStatus.APPROVED:
            raise PermissionDenied("Approved summaries cannot be edited.")
        serializer.save()

    @action(detail=False, methods=["post"], url_path="generate/prompt")
    def generate_prompt(self, request):
        serializer = FinalSummaryGeneratePromptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            preview = build_ai_final_summary_prompt_preview(
                mentor=request.user,
                program_id=serializer.validated_data["program_id"],
                intern_id=serializer.validated_data["intern_id"],
            )
        except Exception as exc:  # noqa: BLE001
            status_code, payload = to_final_summary_api_error_payload(exc)
            return Response(payload, status=status_code)
        return Response(preview, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="generate/continue")
    def generate_continue(self, request):
        serializer = FinalSummaryGenerateContinueSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            summary = continue_ai_final_summary_generation(
                mentor=request.user,
                preview_id=str(serializer.validated_data["preview_id"]),
            )
        except Exception as exc:  # noqa: BLE001
            status_code, payload = to_final_summary_api_error_payload(exc)
            return Response(payload, status=status_code)
        return Response(
            FinalInternshipSummarySerializer(
                summary, context={"request": request}
            ).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        summary = self.get_object()
        if summary.program.mentor_id != request.user.id:
            return Response({"detail": "Not your summary."}, status=status.HTTP_403_FORBIDDEN)
        from django.utils import timezone

        summary.status = AiContentStatus.APPROVED
        summary.approved_by = request.user
        summary.approved_at = timezone.now()
        summary.save()
        from services.final_summary_score import refresh_final_summary_score

        refresh_final_summary_score(summary)
        generate_final_summary_pdf(summary)
        summary.refresh_from_db()
        return Response(
            FinalInternshipSummarySerializer(summary, context={"request": request}).data
        )

    @action(detail=True, methods=["get"])
    def download_pdf(self, request, pk=None):
        summary = self.get_object()
        if request.user.role == Role.INTERN and summary.status != AiContentStatus.APPROVED:
            raise PermissionDenied("Only approved summaries are available.")
        if not summary.pdf_file:
            if summary.status == AiContentStatus.APPROVED:
                generate_final_summary_pdf(summary)
            elif (
                request.user.role == Role.MENTOR
                and summary.program.mentor_id == request.user.id
            ):
                generate_final_summary_pdf(summary, draft_watermark=True)
            else:
                raise Http404("PDF not available.")
        return FileResponse(
            summary.pdf_file.open("rb"),
            as_attachment=True,
            filename=final_summary_pdf_filename(summary),
        )
