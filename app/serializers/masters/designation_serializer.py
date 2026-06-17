from rest_framework import serializers

from app.models.masters.department import Department
from app.models.masters.designation import Designation


class DesignationSerializer(serializers.ModelSerializer):
    status = serializers.ChoiceField(
        choices=(("active", "Active"), ("inactive", "Inactive")),
        write_only=True,
        required=False,
    )
    status_label = serializers.SerializerMethodField(read_only=True)
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )
    department_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Designation
        fields = [
            "unique_id",
            "department_id",
            "department_name",
            "designation_name",
            "designation_group",
            "description",
            "status",
            "status_label",
            "is_active",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["unique_id", "id", "created_at", "updated_at", "is_deleted"]

    def get_status_label(self, obj):
        return "active" if obj.is_active else "inactive"

    def get_department_name(self, obj):
        if obj.department_id:
            return obj.department_id.department_name
        return None

    def validate(self, attrs):
        status = attrs.pop("status", None)
        if status:
            attrs["is_active"] = status == "active"

        if attrs.get("designation_name"):
            attrs["designation_name"] = attrs["designation_name"].strip()
        if attrs.get("designation_group"):
            attrs["designation_group"] = attrs["designation_group"].strip()
        return attrs
