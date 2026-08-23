from django.db.models import Q
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from apps.tasks.models import Task, TaskAssignment, TaskResource
from apps.tasks.serializers import (
    TaskAssignmentSerializer,
    TaskResourceSerializer,
    TaskSerializer,
)
from common.constants import Role, RoadmapStatus
from permissions.roles import IsMentor


def _intern_visible_task_filter():
    """Draft roadmap tasks stay mentor-only until the roadmap is published."""
    return Q(roadmap_week__isnull=True) | Q(
        roadmap_week__roadmap__status=RoadmapStatus.PUBLISHED
    )


class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Task.objects.select_related(
            "program", "roadmap_week", "roadmap_week__roadmap", "created_by"
        ).prefetch_related("resources", "assignments")
        if user.role == Role.ADMIN:
            return qs
        if user.role == Role.MENTOR:
            return qs.filter(program__mentor=user)
        if user.role == Role.INTERN and hasattr(user, "intern_profile"):
            return qs.filter(
                assignments__intern=user.intern_profile
            ).filter(_intern_visible_task_filter()).distinct()
        return qs.none()

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsMentor()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        program = serializer.validated_data["program"]
        if program.mentor_id != self.request.user.id:
            raise PermissionDenied("Not your program.")
        serializer.save(created_by=self.request.user)


class TaskResourceViewSet(viewsets.ModelViewSet):
    serializer_class = TaskResourceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = TaskResource.objects.select_related(
            "task__program", "task__roadmap_week__roadmap"
        )
        if user.role == Role.ADMIN:
            return qs
        if user.role == Role.MENTOR:
            return qs.filter(task__program__mentor=user)
        if user.role == Role.INTERN and hasattr(user, "intern_profile"):
            return (
                qs.filter(task__assignments__intern=user.intern_profile)
                .filter(
                    Q(task__roadmap_week__isnull=True)
                    | Q(task__roadmap_week__roadmap__status=RoadmapStatus.PUBLISHED)
                )
                .distinct()
            )
        return qs.none()

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsMentor()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        task = serializer.validated_data["task"]
        if task.program.mentor_id != self.request.user.id:
            raise PermissionDenied("Not your task.")
        serializer.save()


class TaskAssignmentViewSet(viewsets.ModelViewSet):
    serializer_class = TaskAssignmentSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        qs = TaskAssignment.objects.select_related(
            "task",
            "task__program",
            "task__roadmap_week",
            "task__roadmap_week__roadmap",
            "intern__user",
        ).prefetch_related("task__resources")
        if user.role == Role.ADMIN:
            return qs
        if user.role == Role.MENTOR:
            return qs.filter(task__program__mentor=user)
        if user.role == Role.INTERN and hasattr(user, "intern_profile"):
            return qs.filter(intern=user.intern_profile).filter(
                Q(task__roadmap_week__isnull=True)
                | Q(task__roadmap_week__roadmap__status=RoadmapStatus.PUBLISHED)
            )
        return qs.none()

    def perform_create(self, serializer):
        if self.request.user.role != Role.MENTOR:
            raise PermissionDenied("Only mentors can assign tasks.")
        task = serializer.validated_data["task"]
        if task.program.mentor_id != self.request.user.id:
            raise PermissionDenied("Not your task.")
        serializer.save()

    def perform_update(self, serializer):
        assignment = self.get_object()
        user = self.request.user
        if user.role == Role.MENTOR and assignment.task.program.mentor_id != user.id:
            raise PermissionDenied("Not your assignment.")
        if user.role == Role.INTERN:
            if assignment.intern_id != user.intern_profile.id:
                raise PermissionDenied("Not your assignment.")
            # Interns may only update status.
            allowed = {"status"}
            for key in list(serializer.validated_data.keys()):
                if key not in allowed:
                    serializer.validated_data.pop(key)
        if user.role == Role.ADMIN:
            raise PermissionDenied("Admin cannot review or score assignments.")
        serializer.save()
