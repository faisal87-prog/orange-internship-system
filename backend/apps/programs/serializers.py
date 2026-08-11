from rest_framework import serializers

from apps.programs.models import (
    InternProfile,
    InternshipProgram,
    ProgramReferenceMaterial,
)
from common.constants import ProgramStatus
from common.validators import infer_resource_type, validate_upload_file


class ProgramReferenceMaterialSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = ProgramReferenceMaterial
        fields = [
            "id",
            "program",
            "title",
            "resource_type",
            "file",
            "file_url",
            "external_url",
            "file_size",
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


class InternshipProgramSerializer(serializers.ModelSerializer):
    mentor_name = serializers.CharField(source="mentor.full_name", read_only=True)
    intern_count = serializers.IntegerField(source="interns.count", read_only=True)
    reference_materials = ProgramReferenceMaterialSerializer(many=True, read_only=True)
    assigned_intern_ids = serializers.PrimaryKeyRelatedField(
        source="interns",
        many=True,
        queryset=InternProfile.objects.all(),
        required=False,
    )

    class Meta:
        model = InternshipProgram
        fields = [
            "id",
            "mentor",
            "mentor_name",
            "title",
            "description",
            "role",
            "start_date",
            "end_date",
            "duration_weeks",
            "department",
            "weekly_hours",
            "maximum_interns",
            "skills_needed",
            "skills_to_develop",
            "goals",
            "expected_outcome",
            "final_project",
            "additional_instructions",
            "status",
            "assigned_intern_ids",
            "intern_count",
            "reference_materials",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "mentor", "created_at", "updated_at", "mentor_name", "intern_count"]

    def validate_status(self, value):
        request = self.context.get("request")
        if request and request.user.is_mentor and self.instance is None:
            if value not in {ProgramStatus.DRAFT, ProgramStatus.ACTIVE}:
                raise serializers.ValidationError("New programs may only be Draft or Active.")
        return value

    def create(self, validated_data):
        interns = validated_data.pop("interns", [])
        program = InternshipProgram.objects.create(**validated_data)
        if interns:
            InternProfile.objects.filter(id__in=[i.id for i in interns]).update(program=program)
        return program

    def update(self, instance, validated_data):
        interns = validated_data.pop("interns", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if interns is not None:
            InternProfile.objects.filter(program=instance).exclude(
                id__in=[i.id for i in interns]
            ).update(program=None)
            InternProfile.objects.filter(id__in=[i.id for i in interns]).update(program=instance)
        return instance
