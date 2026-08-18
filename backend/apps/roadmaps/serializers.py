from django.utils import timezone
from rest_framework import serializers

from apps.programs.models import InternProfile
from apps.roadmaps.models import Roadmap, RoadmapWeek
from apps.tasks.models import TaskAssignment
from apps.tasks.serializers import TaskSerializer
from common.constants import RoadmapScope, RoadmapStatus


class RoadmapWeekSerializer(serializers.ModelSerializer):
    tasks = TaskSerializer(many=True, read_only=True)

    class Meta:
        model = RoadmapWeek
        fields = [
            "id",
            "roadmap",
            "week_number",
            "weekly_focus",
            "learning_objectives",
            "expected_skills_gained",
            "mentor_notes",
            "start_date",
            "end_date",
            "display_order",
            "tasks",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "tasks", "created_at", "updated_at"]


class RoadmapSerializer(serializers.ModelSerializer):
    weeks = RoadmapWeekSerializer(many=True, read_only=True)
    assigned_intern_ids = serializers.PrimaryKeyRelatedField(
        source="assigned_interns",
        many=True,
        queryset=InternProfile.objects.all(),
        required=False,
    )
    program_title = serializers.CharField(source="program.title", read_only=True)

    class Meta:
        model = Roadmap
        fields = [
            "id",
            "program",
            "program_title",
            "title",
            "summary",
            "assignment_scope",
            "number_of_weeks",
            "status",
            "generated_by_ai",
            "assigned_intern_ids",
            "approved_by",
            "approved_at",
            "published_at",
            "weeks",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "approved_by",
            "approved_at",
            "published_at",
            "created_at",
            "updated_at",
            "program_title",
        ]

    def validate(self, attrs):
        scope = attrs.get(
            "assignment_scope",
            getattr(self.instance, "assignment_scope", RoadmapScope.PROGRAM),
        )
        interns = attrs.get("assigned_interns")
        if interns is None and self.instance is not None:
            interns = list(self.instance.assigned_interns.all())
        interns = interns or []
        if scope == RoadmapScope.INDIVIDUAL and len(interns) != 1:
            raise serializers.ValidationError(
                {"assigned_intern_ids": "Individual scope requires exactly one intern."}
            )
        if scope == RoadmapScope.GROUP and len(interns) < 1:
            raise serializers.ValidationError(
                {"assigned_intern_ids": "Group scope requires at least one intern."}
            )
        return attrs

    def create(self, validated_data):
        interns = validated_data.pop("assigned_interns", [])
        roadmap = Roadmap.objects.create(**validated_data)
        if interns:
            roadmap.assigned_interns.set(interns)
        return roadmap

    def update(self, instance, validated_data):
        interns = validated_data.pop("assigned_interns", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if interns is not None:
            instance.assigned_interns.set(interns)
        return instance


class RoadmapPublishSerializer(serializers.Serializer):
    def save(self, **kwargs):
        roadmap: Roadmap = self.context["roadmap"]
        user = self.context["request"].user
        if roadmap.status == RoadmapStatus.PUBLISHED:
            raise serializers.ValidationError("Roadmap is already published.")

        if roadmap.assignment_scope == RoadmapScope.PROGRAM:
            interns = list(roadmap.program.interns.all())
        else:
            interns = list(roadmap.assigned_interns.all())

        for week in roadmap.weeks.all():
            for task in week.tasks.all():
                for intern in interns:
                    TaskAssignment.objects.get_or_create(
                        task=task,
                        intern=intern,
                        defaults={},
                    )

        roadmap.status = RoadmapStatus.PUBLISHED
        roadmap.approved_by = user
        roadmap.approved_at = timezone.now()
        roadmap.published_at = timezone.now()
        roadmap.save()
        return roadmap


class RoadmapGeneratePromptSerializer(serializers.Serializer):
    program_id = serializers.IntegerField()
    assignment_scope = serializers.ChoiceField(choices=RoadmapScope.CHOICES)
    selected_intern_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
    )
    mentor_focus_skills = serializers.ListField(
        child=serializers.CharField(max_length=255, allow_blank=False),
        required=False,
        allow_empty=True,
    )


class RoadmapGenerateContinueSerializer(serializers.Serializer):
    preview_id = serializers.UUIDField()


# Backward-compatible alias used by older imports/tests if needed.
RoadmapGenerateSerializer = RoadmapGeneratePromptSerializer
