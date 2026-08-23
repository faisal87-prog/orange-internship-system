from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.roadmaps.models import Roadmap, RoadmapWeek
from apps.roadmaps.serializers import (
    RoadmapGenerateContinueSerializer,
    RoadmapGeneratePromptSerializer,
    RoadmapPublishSerializer,
    RoadmapSerializer,
    RoadmapWeekSerializer,
)
from common.constants import Role, RoadmapScope, RoadmapStatus
from permissions.roles import IsMentor
from services.ai.service import (
    build_ai_roadmap_prompt_preview,
    continue_ai_roadmap_generation,
    to_api_error_payload,
)


class RoadmapViewSet(viewsets.ModelViewSet):
    serializer_class = RoadmapSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Roadmap.objects.select_related("program", "approved_by").prefetch_related(
            "weeks__tasks__resources",
            "weeks__tasks__assignments",
            "assigned_interns",
        )
        if user.role == Role.ADMIN:
            return qs
        if user.role == Role.MENTOR:
            return qs.filter(program__mentor=user)
        if user.role == Role.INTERN and hasattr(user, "intern_profile"):
            profile = user.intern_profile
            return qs.filter(
                status=RoadmapStatus.PUBLISHED,
                program_id=profile.program_id,
            ).filter(
                Q(assignment_scope=RoadmapScope.PROGRAM) | Q(assigned_interns=profile)
            ).distinct()
        return qs.none()

    def get_permissions(self):
        if self.action in {
            "create",
            "update",
            "partial_update",
            "destroy",
            "publish",
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

    @action(detail=False, methods=["post"], url_path="generate/prompt")
    def generate_prompt(self, request):
        serializer = RoadmapGeneratePromptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            preview = build_ai_roadmap_prompt_preview(
                mentor=request.user,
                program_id=serializer.validated_data["program_id"],
                assignment_scope=serializer.validated_data["assignment_scope"],
                selected_intern_ids=serializer.validated_data.get(
                    "selected_intern_ids"
                )
                or [],
                mentor_focus_skills=serializer.validated_data.get(
                    "mentor_focus_skills"
                )
                or [],
            )
        except Exception as exc:  # noqa: BLE001 - mapped to safe API errors
            status_code, payload = to_api_error_payload(exc)
            return Response(payload, status=status_code)
        return Response(preview, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="generate/continue")
    def generate_continue(self, request):
        serializer = RoadmapGenerateContinueSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            roadmap = continue_ai_roadmap_generation(
                mentor=request.user,
                preview_id=str(serializer.validated_data["preview_id"]),
            )
        except Exception as exc:  # noqa: BLE001 - mapped to safe API errors
            status_code, payload = to_api_error_payload(exc)
            return Response(payload, status=status_code)
        return Response(
            RoadmapSerializer(roadmap, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        roadmap = self.get_object()
        if roadmap.program.mentor_id != request.user.id:
            return Response({"detail": "Not your roadmap."}, status=status.HTTP_403_FORBIDDEN)
        serializer = RoadmapPublishSerializer(
            data={},
            context={"roadmap": roadmap, "request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        roadmap.refresh_from_db()
        return Response(RoadmapSerializer(roadmap, context={"request": request}).data)


class RoadmapWeekViewSet(viewsets.ModelViewSet):
    serializer_class = RoadmapWeekSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = RoadmapWeek.objects.select_related("roadmap__program").prefetch_related(
            "tasks__resources",
            "tasks__assignments",
        )
        if user.role == Role.ADMIN:
            return qs
        if user.role == Role.MENTOR:
            return qs.filter(roadmap__program__mentor=user)
        if user.role == Role.INTERN and hasattr(user, "intern_profile"):
            return qs.filter(
                roadmap__status=RoadmapStatus.PUBLISHED,
                roadmap__program_id=user.intern_profile.program_id,
            )
        return qs.none()

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsMentor()]
        return [IsAuthenticated()]
