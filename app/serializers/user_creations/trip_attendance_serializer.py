from rest_framework import serializers
from django.utils import timezone
from django.conf import settings
from app.models.masters.transport_masters.trip_attendance import TripAttendance
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.user_creations.staffcreation import Staffcreation
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation


class TripAttendanceSerializer(serializers.ModelSerializer):

    daily_trip_assignment_id = serializers.SlugRelatedField(
        source="daily_trip_assignment",
        slug_field="unique_id",
        queryset=DailyTripAssignment.objects.all()
    )

    staff_id = serializers.SlugRelatedField(
        source="staff",
        slug_field="staff_unique_id",
        queryset=Staffcreation.objects.all()
    )

    vehicle_id = serializers.SlugRelatedField(
        source="vehicle",
        slug_field="unique_id",
        queryset=VehicleCreation.objects.all()
    )

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
        trip = attrs.get("daily_trip_assignment") if "daily_trip_assignment" in attrs else getattr(instance, "daily_trip_assignment", None)
        staff = attrs.get("staff") if "staff" in attrs else getattr(instance, "staff", None)
        vehicle = attrs.get("vehicle") if "vehicle" in attrs else getattr(instance, "vehicle", None)

        if instance:
            return attrs

        if not trip or not staff:
            return attrs

        # Trip must be active (create only)
        if trip.status != DailyTripAssignment.STATUS_IN_PROGRESS:
            raise serializers.ValidationError(
                "Attendance allowed only for in-progress trips"
            )

        if not trip.staff_template_id:
            raise serializers.ValidationError(
                "Trip has no staff template assigned"
            )

        # Staff must belong to trip
        if staff.staff_unique_id not in [
            trip.staff_template_id.operator_id_id,
            trip.staff_template_id.driver_id_id,
        ]:
            raise serializers.ValidationError(
                "Staff is not assigned to this trip"
            )

        if staff.staffusertype_id and staff.staffusertype_id.name.lower() not in [
            "operator",
            "driver",
        ]:
            raise serializers.ValidationError(
                "Attendance allowed only for operator or driver"
            )

        if vehicle != trip.vehicle_id:
            raise serializers.ValidationError(
                "Vehicle does not match daily trip assignment"
            )

        # Trip attendance cooldown enforcement (create only)
        last = (
            TripAttendance.objects
            .filter(daily_trip_assignment=trip, staff=staff)
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
