from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.models.audits.trip_exception_log import TripExceptionLog
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment


class TripExceptionLogSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):

    daily_trip_assignment_id = serializers.SlugRelatedField(
        source="daily_trip_assignment",
        slug_field="unique_id",
        queryset=DailyTripAssignment.objects.all()
    )

    class Meta:
        model = TripExceptionLog
        fields = [
            "unique_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
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
