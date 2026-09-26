from rest_framework import serializers
from django.utils import timezone
from django.conf import settings
from app.models.masters.transport_masters.trip_attendance import TripAttendance
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.utils.plain_ref import ref_id


class TripAttendanceSerializer(serializers.ModelSerializer):

    # Plain unique_id references (no DB relation); checked in validate_*.
    daily_trip_assignment_id = serializers.CharField()
    staff_id = serializers.CharField()
    vehicle_id = serializers.CharField()

    def validate_daily_trip_assignment_id(self, value):
        if not DailyTripAssignment.objects.filter(unique_id=value).exists():
            raise serializers.ValidationError(f'Object with unique_id={value} does not exist.')
        return value

    def validate_staff_id(self, value):
        if not Staffcreation.objects.filter(staff_unique_id=value).exists():
            raise serializers.ValidationError(f'Object with staff_unique_id={value} does not exist.')
        return value

    def validate_vehicle_id(self, value):
        if not VehicleCreation.objects.filter(unique_id=value).exists():
            raise serializers.ValidationError(f'Object with unique_id={value} does not exist.')
        return value

    class Meta:
        model = TripAttendance
        fields = [
            "unique_id",
            "daily_trip_assignment_id",
            "staff_id",
            "vehicle_id",
            "attendance_time",
            "latitude",
            "longitude",
            "photo",
            "source",
            "created_at",
        ]
        read_only_fields = ["unique_id", "created_at"]

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        if instance:
            return attrs

        trip = DailyTripAssignment.objects.filter(
            unique_id=attrs.get("daily_trip_assignment_id")
        ).first()
        staff = Staffcreation.objects.filter(staff_unique_id=attrs.get("staff_id")).first()
        vehicle_id = attrs.get("vehicle_id")

        if not trip or not staff:
            return attrs

        # Trip must be active (create only)
        if trip.status != DailyTripAssignment.STATUS_IN_PROGRESS:
            raise serializers.ValidationError(
                "Attendance allowed only for in-progress trips"
            )

        if not trip.staff_template:
            raise serializers.ValidationError(
                "Trip has no staff template assigned"
            )

        # Staff must belong to trip
        if staff.staff_unique_id not in [
            trip.staff_template.operator_id,
            trip.staff_template.driver_id,
        ]:
            raise serializers.ValidationError(
                "Staff is not assigned to this trip"
            )

        if staff.staffusertype and staff.staffusertype.name.lower() not in [
            "operator",
            "driver",
        ]:
            raise serializers.ValidationError(
                "Attendance allowed only for operator or driver"
            )

        if vehicle_id != trip.vehicle_id:
            raise serializers.ValidationError(
                "Vehicle does not match daily trip assignment"
            )

        # Trip attendance cooldown enforcement (create only)
        last = (
            TripAttendance.objects
            .filter(daily_trip_assignment_id=trip.unique_id, staff_id=staff.staff_unique_id)
            .order_by("-attendance_time")
            .first()
        )

        if last:
            cooldown_minutes = getattr(
                settings,
                "TRIP_ATTENDANCE_COOLDOWN_MINUTES",
                45,
            )
            delta = timezone.now() - last.attendance_time
            if delta.total_seconds() < cooldown_minutes * 60:
                raise serializers.ValidationError(
                    f"Attendance already captured within last {cooldown_minutes} minutes"
                )

        return attrs
