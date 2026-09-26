from rest_framework import serializers

from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.models.superadmin.staff_management.unassigned_staff_pool import UnassignedStaffPool


class UnassignedStaffPoolSerializer(serializers.ModelSerializer):
    operator_id = serializers.CharField(max_length=30, required=False, allow_null=True, allow_blank=True)
    driver_id = serializers.CharField(max_length=30, required=False, allow_null=True, allow_blank=True)
    daily_trip_assignment_id = serializers.CharField(max_length=50, required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = UnassignedStaffPool
        fields = ["unique_id", "operator_id", "driver_id", "status", "daily_trip_assignment_id", "created_at"]
        read_only_fields = ["unique_id", "created_at"]

    def _staff(self, value, field):
        if not value:
            return None
        staff = Staffcreation.objects.filter(staff_unique_id=value).first()
        if staff is None:
            raise serializers.ValidationError({field: "Invalid staff."})
        return staff

    def validate_daily_trip_assignment_id(self, value):
        if not value:
            return None
        if not DailyTripAssignment.objects.filter(unique_id=value).exists():
            raise serializers.ValidationError("Invalid daily trip assignment.")
        return value

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        for field in ("operator_id", "driver_id"):
            if field in attrs:
                attrs[field] = attrs[field] or None
        operator = self._staff(
            attrs["operator_id"] if "operator_id" in attrs else getattr(instance, "operator_id", None),
            "operator_id",
        )
        driver = self._staff(
            attrs["driver_id"] if "driver_id" in attrs else getattr(instance, "driver_id", None),
            "driver_id",
        )

        if not operator and not driver:
            raise serializers.ValidationError("Either operator_id or driver_id is required")
        if operator and driver:
            raise serializers.ValidationError("Only one of operator_id or driver_id must be provided")

        staff = operator or driver
        if staff:
            role_name = staff.staffusertype.name.lower() if staff.staffusertype else ""
            if operator and role_name != "operator":
                raise serializers.ValidationError({"operator_id": "Selected user is not an operator."})
            if driver and role_name != "driver":
                raise serializers.ValidationError({"driver_id": "Selected user is not a driver."})

        return attrs
