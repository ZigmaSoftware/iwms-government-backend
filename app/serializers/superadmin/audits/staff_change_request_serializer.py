from rest_framework import serializers

from app.models.superadmin.audits.staff_change_request import StaffChangeRequest
from app.models.superadmin.staff_management.staffcreation import StaffPersonalDetails


class StaffChangeRequestSerializer(serializers.ModelSerializer):
    requested_by = serializers.CharField(source="requested_by_id", read_only=True)
    requested_by_name = serializers.CharField(source="requested_by.employee_name", read_only=True, default=None)
    decided_by = serializers.CharField(source="decided_by_id", read_only=True)
    decided_by_name = serializers.CharField(source="decided_by.employee_name", read_only=True, default=None)

    class Meta:
        model = StaffChangeRequest
        fields = [
            "unique_id",
            "requested_by",
            "requested_by_name",
            "approver_id",
            "field_name",
            "old_value",
            "new_value",
            "reason",
            "status",
            "decided_by",
            "decided_by_name",
            "decided_at",
            "decision_remarks",
            "created_at",
        ]
        read_only_fields = [
            "unique_id",
            "requested_by",
            "approver_id",
            "old_value",
            "status",
            "decided_by",
            "decided_at",
            "created_at",
        ]


class StaffChangeRequestCreateSerializer(serializers.Serializer):
    """Validates a staff member's self-service request to change one of
    their own StaffPersonalDetails fields. old_value is captured server-side
    from the live record, never trusted from the client."""

    field_name = serializers.ChoiceField(choices=StaffChangeRequest.ALLOWED_FIELDS)
    new_value = serializers.JSONField()
    reason = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate(self, data):
        staff = self.context["staff"]
        if not StaffPersonalDetails._meta.get_field(data["field_name"]):
            raise serializers.ValidationError({"field_name": "Unknown field."})

        personal_details = getattr(staff, "personal_details", None)
        data["old_value"] = (
            getattr(personal_details, data["field_name"], None)
            if personal_details is not None
            else None
        )
        return data


class StaffChangeRequestDecisionSerializer(serializers.Serializer):
    decision_remarks = serializers.CharField(required=False, allow_blank=True, allow_null=True)
