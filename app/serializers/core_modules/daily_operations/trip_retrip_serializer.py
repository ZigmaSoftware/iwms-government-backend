from rest_framework import serializers

from app.models.core_modules.daily_operations.trip_retrip_request import TripRetripRequest
from app.services.retrip_service import build_pending_snapshot


class TripRetripRequestSerializer(serializers.ModelSerializer):
    """Everything a supervisor needs to decide, in one payload.

    `pending_snapshot` is what the driver saw when they raised the request;
    `live_pending` is recomputed on read, because a colleague may have collected
    a stop since — the supervisor must tick boxes against reality, not history.
    """

    assignment_unique_id = serializers.CharField(source="assignment.unique_id", read_only=True)
    trip_date = serializers.DateField(source="assignment.trip_date", read_only=True)
    scheduled_time = serializers.TimeField(source="assignment.scheduled_time", read_only=True)
    assignment_status = serializers.CharField(source="assignment.status", read_only=True)
    collection_type = serializers.SerializerMethodField()
    vehicle_no = serializers.CharField(source="assignment.vehicle.vehicle_no", read_only=True)
    area_name = serializers.SerializerMethodField()
    requested_by_name = serializers.CharField(
        source="requested_by.employee_name", read_only=True
    )
    reviewed_by_name = serializers.CharField(source="reviewed_by.employee_name", read_only=True)
    live_pending = serializers.SerializerMethodField()
    # Plain id columns, exposed under their original API names.
    assignment = serializers.CharField(source="assignment_id", read_only=True)
    requested_by = serializers.CharField(source="requested_by_id", read_only=True)
    reviewed_by = serializers.CharField(source="reviewed_by_id", read_only=True)
    new_assignment = serializers.CharField(source="new_assignment_id", read_only=True)

    class Meta:
        model = TripRetripRequest
        exclude = ["assignment_id", "requested_by_id", "reviewed_by_id", "new_assignment_id"]
        read_only_fields = ["unique_id", "created_at", "updated_at"]

    def get_collection_type(self, obj):
        plan = getattr(obj.assignment, "trip_plan", None)
        return getattr(plan, "collection_type", None)

    def get_area_name(self, obj):
        from app.models.masters.panchayat import Panchayat

        assignment = obj.assignment
        ward = assignment.wards.first()
        if ward is not None:
            return ward.ward_name
        panchayat_id = assignment.panchayat_id
        if not panchayat_id:
            return None
        return Panchayat.objects.filter(unique_id=panchayat_id).values_list(
            "panchayat_name", flat=True
        ).first()

    def get_live_pending(self, obj):
        return build_pending_snapshot(obj.assignment)
