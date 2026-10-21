from rest_framework import serializers

from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.trip_delay_report import TripDelayReport
from app.serializers.evidence_image import EvidenceImageField, absolute_image_url


class TripDelayReportSerializer(serializers.ModelSerializer):
    """Read/write for the delay log.

    The driver supplies only `trip_assignment_id`, `delay_reason`,
    `delay_remarks`, the geotagged `evidence_image` + `delay_lat`/`delay_lng`
    (plus optional minutes/location). Everything else — geography, reporter,
    timestamps, status — is stamped server-side, so a client cannot report a
    delay against another crew's trip or backdate one.
    """

    # Plain DailyTripAssignment.unique_id (no DB relation); checked below.
    trip_assignment_id = serializers.CharField(max_length=50)

    # Flattened read-only context so the supervisor list needs no extra calls.
    delay_reason_display = serializers.CharField(
        source="get_delay_reason_display", read_only=True
    )
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    reported_by = serializers.CharField(source="reported_by_id", read_only=True)
    acknowledged_by = serializers.CharField(
        source="acknowledged_by_id", read_only=True, default=None
    )
    reported_by_name = serializers.SerializerMethodField()
    vehicle_no = serializers.SerializerMethodField()
    trip_date = serializers.SerializerMethodField()
    evidence_image = EvidenceImageField(required=False, allow_null=True)
    evidence_image_url = serializers.SerializerMethodField()

    class Meta:
        model = TripDelayReport
        fields = [
            "unique_id",
            "state_id",
            "district_id",
            "area_type_id",
            "corporation_id",
            "municipality_id",
            "town_panchayat_id",
            "panchayat_union_id",
            "panchayat_id",
            "trip_assignment_id",
            "trip_date",
            "vehicle_no",
            "reported_by",
            "reported_by_name",
            "delay_reason",
            "delay_reason_display",
            "delay_remarks",
            "estimated_delay_minutes",
            "delay_time",
            "delay_lat",
            "delay_lng",
            "delay_location",
            "evidence_image",
            "evidence_image_url",
            "status",
            "status_display",
            "acknowledged_by",
            "acknowledged_at",
            "supervisor_remarks",
            "resolved_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "unique_id",
            # Server-stamped: see the class docstring.
            "state_id",
            "district_id",
            "area_type_id",
            "corporation_id",
            "municipality_id",
            "town_panchayat_id",
            "panchayat_union_id",
            "panchayat_id",
            "reported_by",
            "delay_time",
            "status",
            "acknowledged_by",
            "acknowledged_at",
            "resolved_at",
            "created_at",
            "updated_at",
        ]

    def get_reported_by_name(self, obj):
        return getattr(obj.reported_by, "employee_name", None)

    def get_vehicle_no(self, obj):
        assignment = obj.trip_assignment
        return getattr(getattr(assignment, "vehicle", None), "vehicle_no", None)

    def get_trip_date(self, obj):
        trip_date = getattr(obj.trip_assignment, "trip_date", None)
        return trip_date.isoformat() if trip_date else None

    def get_evidence_image_url(self, obj):
        return absolute_image_url(self, obj.evidence_image)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance is None:
            errors = {}
            if not attrs.get("evidence_image"):
                errors["evidence_image"] = "A geotagged evidence image is required."
            if attrs.get("delay_lat") is None:
                errors["delay_lat"] = "Capture latitude is required."
            if attrs.get("delay_lng") is None:
                errors["delay_lng"] = "Capture longitude is required."
            if errors:
                raise serializers.ValidationError(errors)
        return attrs

    def validate_trip_assignment_id(self, value):
        assignment = DailyTripAssignment.objects.filter(
            unique_id=value, is_deleted=False
        ).first()
        if assignment is None:
            raise serializers.ValidationError("Trip assignment not found.")
        request = self.context.get("request")
        if request is not None:
            from app.utils.roles import can_manage_trips
            from app.viewsets.operator_mobile.helpers import effective_crew_q, _effective_extra_operator_ids
            user = request.user
            staff_id = getattr(user, "staff_unique_id", None)
            if can_manage_trips(user):
                from app.utils.hierarchy import filter_flat_geo_queryset_by_requester_scope
                owned = getattr(assignment.trip_plan, "supervisor_id", None) == staff_id and staff_id
                visible = filter_flat_geo_queryset_by_requester_scope(
                    DailyTripAssignment.objects.filter(pk=assignment.pk), user
                ).exists()
                allowed = owned or visible
            else:
                allowed = staff_id and (
                    DailyTripAssignment.objects.filter(pk=assignment.pk).filter(effective_crew_q(staff_id)).exists()
                    or staff_id in _effective_extra_operator_ids(assignment)
                )
            if not allowed:
                raise serializers.ValidationError("This trip is outside your responsibility.")
        # A delay on a closed trip is noise.
        if assignment.status in (
            DailyTripAssignment.STATUS_COMPLETED,
            DailyTripAssignment.STATUS_CANCELLED,
        ):
            raise serializers.ValidationError(
                "Cannot report a delay for a completed or cancelled trip."
            )
        return assignment.unique_id

    def validate_delay_remarks(self, value):
        # The remarks ARE the feature — a delay with no explanation tells the
        # supervisor nothing.
        cleaned = (value or "").strip()
        if not cleaned:
            raise serializers.ValidationError(
                "Describe what caused the delay."
            )
        return cleaned


class TripDelayAcknowledgeSerializer(serializers.Serializer):
    supervisor_remarks = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )
