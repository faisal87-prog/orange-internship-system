from django.utils import timezone
from rest_framework import serializers

from apps.programs.models import InternProfile
from apps.tasks.models import Task, TaskAssignment, TaskResource
from common.constants import TaskAssignmentStatus
from common.validators import infer_resource_type, validate_score, validate_upload_file


class TaskResourceSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = TaskResource
        fields = [
            "id",
            "task",
            "title",
            "resource_type",
            "file",
            "file_url",
            "external_url",
            "file_size",
            "display_order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "file_size", "created_at", "updated_at", "file_url"]
        extra_kwargs = {
            "resource_type": {"required": False},
            "file": {"required": False, "allow_null": True},
            "external_url": {"required": False, "allow_blank": True},
        }

    def get_file_url(self, obj):
        request = self.context.get("request")
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        if obj.file:
            return obj.file.url
        return None

    def validate(self, attrs):
        file = attrs["file"] if "file" in attrs else getattr(self.instance, "file", None)
        external_url = (
            attrs["external_url"]
            if "external_url" in attrs
            else getattr(self.instance, "external_url", "")
        )
        if file:
            validate_upload_file(file)
        if not file and not external_url:
            raise serializers.ValidationError("Please provide a file or an external link.")
        if "resource_type" not in attrs or not attrs.get("resource_type"):
            attrs["resource_type"] = infer_resource_type(
                getattr(file, "name", None),
                external_url,
            )
        return attrs


class TaskSerializer(serializers.ModelSerializer):
    resources = TaskResourceSerializer(many=True, read_only=True)
    week_number = serializers.IntegerField(
        source="roadmap_week.week_number",
        read_only=True,
        allow_null=True,
    )
    assign_intern_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=InternProfile.objects.all(),
        write_only=True,
        required=False,
    )

    class Meta:
        model = Task
        fields = [
            "id",
            "roadmap_week",
            "week_number",
            "program",
            "created_by",
            "title",
            "description",
            "difficulty",
            "estimated_time_minutes",
            "deliverable",
            "success_criteria",
            "due_date",
            "requirement_type",
            "source",
            "display_order",
            "resources",
            "assign_intern_ids",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at", "week_number"]

    def create(self, validated_data):
        intern_ids = validated_data.pop("assign_intern_ids", [])
        task = Task.objects.create(**validated_data)
        for intern in intern_ids:
            TaskAssignment.objects.create(task=task, intern=intern)
        return task

    def update(self, instance, validated_data):
        validated_data.pop("assign_intern_ids", None)
        return super().update(instance, validated_data)


class TaskAssignmentSerializer(serializers.ModelSerializer):
    task = TaskSerializer(read_only=True)
    task_id = serializers.PrimaryKeyRelatedField(
        source="task",
        queryset=Task.objects.all(),
        write_only=True,
        required=False,
    )
    intern_name = serializers.CharField(source="intern.user.full_name", read_only=True)
    effective_due_date = serializers.DateField(read_only=True)
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = TaskAssignment
        fields = [
            "id",
            "task",
            "task_id",
            "intern",
            "intern_name",
            "status",
            "due_date_override",
            "effective_due_date",
            "is_overdue",
            "score",
            "mentor_feedback",
            "assigned_at",
            "reviewed_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "assigned_at",
            "reviewed_at",
            "completed_at",
            "created_at",
            "updated_at",
            "intern_name",
            "effective_due_date",
            "is_overdue",
        ]

    def get_is_overdue(self, obj):
        if obj.status == TaskAssignmentStatus.COMPLETED:
            return False
        return obj.effective_due_date < timezone.localdate()

    def validate_score(self, value):
        validate_score(value)
        return value

    def validate(self, attrs):
        status_value = attrs.get(
            "status",
            getattr(self.instance, "status", None),
        )
        if "score" in attrs:
            score = attrs.get("score")
        else:
            score = getattr(self.instance, "score", None) if self.instance else None

        if status_value == TaskAssignmentStatus.COMPLETED and score is None:
            raise serializers.ValidationError(
                {"score": "A score from 0 to 100 is required to mark the task as completed."}
            )
        return attrs

    def validate_status(self, value):
        request = self.context.get("request")
        instance = self.instance
        if not request or not instance:
            return value
        if request.user.is_intern:
            allowed = {
                TaskAssignmentStatus.TO_DO: {TaskAssignmentStatus.IN_PROGRESS},
                TaskAssignmentStatus.IN_PROGRESS: {TaskAssignmentStatus.SUBMITTED},
                TaskAssignmentStatus.NEEDS_REVISION: {
                    TaskAssignmentStatus.IN_PROGRESS,
                    TaskAssignmentStatus.SUBMITTED,
                },
                TaskAssignmentStatus.SUBMITTED: set(),
                TaskAssignmentStatus.COMPLETED: set(),
            }
            if value != instance.status and value not in allowed.get(instance.status, set()):
                raise serializers.ValidationError(
                    f"Intern cannot change status from {instance.status} to {value}."
                )
        return value

    def update(self, instance, validated_data):
        status_value = validated_data.get("status", instance.status)
        if status_value == TaskAssignmentStatus.COMPLETED:
            validated_data.setdefault("reviewed_at", timezone.now())
            validated_data.setdefault("completed_at", timezone.now())
        elif status_value == TaskAssignmentStatus.NEEDS_REVISION:
            validated_data.setdefault("reviewed_at", timezone.now())
            validated_data["completed_at"] = None
        return super().update(instance, validated_data)
