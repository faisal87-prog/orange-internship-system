from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.roadmaps.models import Roadmap, RoadmapWeek
from apps.roadmaps.serializers import (
    RoadmapPublishSerializer,
    RoadmapSerializer,
    RoadmapWeekSerializer,
)
from common.constants import Role, RoadmapScope, RoadmapStatus
from permissions.roles import IsMentor


class RoadmapViewSet(viewsets.ModelViewSet):
    serializer_class = RoadmapSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Roadmap.objects.select_related("program", "approved_by").prefetch_related(
            "weeks__tasks__resources",
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
        if self.action in {"create", "update", "partial_update", "destroy", "publish"}:
            return [IsMentor()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        program = serializer.validated_data["program"]
        if program.mentor_id != self.request.user.id:
            raise PermissionDenied("Not your program.")
        serializer.save()

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
            "tasks__resources"
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
