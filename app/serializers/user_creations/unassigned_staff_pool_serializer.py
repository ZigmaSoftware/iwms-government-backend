from rest_framework import serializers

from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.user_creations.staffcreation import Staffcreation
from app.models.user_creations.unassigned_staff_pool import UnassignedStaffPool


class UnassignedStaffPoolSerializer(serializers.ModelSerializer):
    operator_id = serializers.SlugRelatedField(source="operator", slug_field="staff_unique_id", queryset=Staffcreation.objects.all(), required=False, allow_null=True)
    driver_id = serializers.SlugRelatedField(source="driver", slug_field="staff_unique_id", queryset=Staffcreation.objects.all(), required=False, allow_null=True)
    daily_trip_assignment_id = serializers.SlugRelatedField(source="daily_trip_assignment", slug_field="unique_id", queryset=DailyTripAssignment.objects.all(), required=False, allow_null=True)

    class Meta:
        model = UnassignedStaffPool
        fields = ["unique_id", "operator_id", "driver_id", "status", "daily_trip_assignment_id", "created_at"]
        read_only_fields = ["unique_id", "created_at"]

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        operator = attrs.get("operator") if "operator" in attrs else getattr(instance, "operator", None)
        driver = attrs.get("driver") if "driver" in attrs else getattr(instance, "driver", None)

        if not operator and not driver:
            raise serializers.ValidationError("Either operator_id or driver_id is required")
        if operator and driver:
            raise serializers.ValidationError("Only one of operator_id or driver_id must be provided")

        staff = operator or driver
        if staff:
            role_name = staff.staffusertype_id.name.lower() if staff.staffusertype_id else ""
            if operator and role_name != "operator":
                raise serializers.ValidationError({"operator_id": "Selected user is not an operator."})
            if driver and role_name != "driver":
                raise serializers.ValidationError({"driver_id": "Selected user is not a driver."})

        return attrs
