from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from django.utils import timezone

from app.models.audits.vehicle_trip_audit import VehicleTripAudit
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.transport_masters.vehicleCreation import VehicleCreation


class VehicleTripAuditSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):

    daily_trip_assignment_id = serializers.SlugRelatedField(
        source="daily_trip_assignment",
        slug_field="unique_id",
        queryset=DailyTripAssignment.objects.all()
    )

    vehicle_id = serializers.SlugRelatedField(
        source="vehicle",
        slug_field="unique_id",
        queryset=VehicleCreation.objects.all()
    )

    class Meta:
        model = VehicleTripAudit
        fields = [
            "unique_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "daily_trip_assignment_id",
            "vehicle_id",
            "gps_lat",
            "gps_lon",
            "avg_speed",
            "idle_seconds",
            "captured_at",
            "created_at",
        ]
        read_only_fields = ["unique_id", "idle_seconds", "created_at"]

    def validate(self, attrs):
        instance = getattr(self, "instance", None)

        lat = attrs.get("gps_lat")
        lon = attrs.get("gps_lon")

        if lat is None and instance:
            lat = instance.gps_lat
        if lon is None and instance:
            lon = instance.gps_lon

        if not lat or not lon:
            raise serializers.ValidationError("GPS arrays cannot be empty")

        if len(lat) != len(lon):
            raise serializers.ValidationError("Latitude & Longitude array size mismatch")

        if len(lat) < 2:
            raise serializers.ValidationError("Minimum 2 GPS points required")

        try:
            [float(x) for x in lat]
            [float(x) for x in lon]
        except (TypeError, ValueError):
            raise serializers.ValidationError("GPS arrays must be numeric values")

        trip = attrs.get("daily_trip_assignment") or (instance.daily_trip_assignment if instance else None)
        if not trip:
            raise serializers.ValidationError("Daily trip assignment is required")
        if trip.status != DailyTripAssignment.STATUS_IN_PROGRESS:
            raise serializers.ValidationError(
                "GPS audit allowed only for in-progress trips"
            )

        vehicle = attrs.get("vehicle") or (instance.vehicle if instance else None)
        if vehicle and vehicle != trip.vehicle_id:
            raise serializers.ValidationError("Vehicle does not match daily trip assignment")

        return attrs

    def calculate_idle_time(self, speed, points_count):
        """
        Idle if speed <= 3 km/h.
        Each point = 5 seconds.
        """
        if speed <= 3:
            return points_count * 5
        return 0

    def create(self, validated_data):
        speed = validated_data["avg_speed"]
        points = len(validated_data["gps_lat"])

        validated_data["idle_seconds"] = self.calculate_idle_time(
            speed, points
        )

        return super().create(validated_data)
