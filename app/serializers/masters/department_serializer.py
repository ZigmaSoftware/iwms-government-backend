from rest_framework import serializers

from app.models.masters.department import Department


class DepartmentSerializer(serializers.ModelSerializer):
    status = serializers.ChoiceField(
        choices=(("active", "Active"), ("inactive", "Inactive")),
        write_only=True,
        required=False,
    )
    status_label = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Department
        fields = [
            "unique_id",
            "department_name",
            "department_code",
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

    def validate_department_code(self, value):
        return value.strip().upper()

    def validate(self, attrs):
        status = attrs.pop("status", None)
        if status:
            attrs["is_active"] = status == "active"

        name = attrs.get("department_name")
        code = attrs.get("department_code")
        if name:
            attrs["department_name"] = name.strip()
        if code:
            attrs["department_code"] = code.strip().upper()
        return attrs
