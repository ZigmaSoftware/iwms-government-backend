from rest_framework import serializers
from app.models.superadmin.audits.trip_exception_log import TripExceptionLog
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment


class TripExceptionLogSerializer(serializers.ModelSerializer):

    daily_trip_assignment_id = serializers.SlugRelatedField(
        source="daily_trip_assignment",
        slug_field="unique_id",
        queryset=DailyTripAssignment.objects.all()
    )

    class Meta:
        model = TripExceptionLog
        fields = [
            "unique_id",
            "daily_trip_assignment_id",
            "exception_type",
            "remarks",
            "detected_by",
            "created_at",
        ]
        read_only_fields = ["unique_id", "created_at"]

    def validate(self, attrs):
        trip = attrs["daily_trip_assignment"]

        if trip.status in [DailyTripAssignment.STATUS_COMPLETED, DailyTripAssignment.STATUS_CANCELLED]:
            raise serializers.ValidationError(
                "Exceptions cannot be logged for completed or cancelled trips"
            )

        return attrs
