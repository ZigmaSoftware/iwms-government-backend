from django.utils import timezone
from rest_framework import serializers

from app.utils.plain_ref import ref_id
from app.models.core_modules.daily_operations.vehicle_breakdown import VehicleBreakdown
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.utils.hierarchy import flat_geo_display


def _existing_id(model, key, value, message):
    """Blank -> None; otherwise the id itself, provided an active row exists."""
    if value in (None, ""):
        return None
    if not model.objects.filter(**{key: value, "is_deleted": False}).exists():
        raise serializers.ValidationError(message)
    return value


class VehicleBreakdownSerializer(serializers.ModelSerializer):

    # Write fields — plain unique_id strings, existence checked in validate_*.
    trip_assignment_id = serializers.CharField(max_length=50)
    breakdown_vehicle_id = serializers.CharField(max_length=40)
    replacement_vehicle_id = serializers.CharField(
        max_length=40, required=False, allow_null=True, allow_blank=True
    )
    replacement_driver_id = serializers.CharField(
        max_length=30, required=False, allow_null=True, allow_blank=True
    )
    replacement_operator_id = serializers.CharField(
        max_length=30, required=False, allow_null=True, allow_blank=True
    )
    alt_staff_template_id = serializers.CharField(read_only=True)
    approved_by = serializers.CharField(source="approved_by_id", read_only=True)
    photos = serializers.SerializerMethodField(read_only=True)

    # Read-only detail fields
    trip_assignment_detail = serializers.SerializerMethodField(read_only=True)
    breakdown_vehicle_detail = serializers.SerializerMethodField(read_only=True)
    replacement_vehicle_detail = serializers.SerializerMethodField(read_only=True)
    replacement_driver_detail = serializers.SerializerMethodField(read_only=True)
    replacement_operator_detail = serializers.SerializerMethodField(read_only=True)
    original_driver_detail = serializers.SerializerMethodField(read_only=True)
    original_operator_detail = serializers.SerializerMethodField(read_only=True)
    alt_staff_template_detail = serializers.SerializerMethodField(read_only=True)
    approved_by_detail = serializers.SerializerMethodField(read_only=True)
    new_assignment_id = serializers.SerializerMethodField(read_only=True)
    pending_stops = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = VehicleBreakdown
        fields = [
            "unique_id",
            "trip_assignment_id",
            "trip_assignment_detail",
            "breakdown_vehicle_id",
            "breakdown_vehicle_detail",
            "replacement_vehicle_id",
            "replacement_vehicle_detail",
            "replacement_driver_id",
            "replacement_driver_detail",
            "replacement_operator_id",
            "replacement_operator_detail",
            "original_driver_detail",
            "original_operator_detail",
            "alt_staff_template_id",
            "alt_staff_template_detail",
            "breakdown_time",
            "breakdown_lat",
            "breakdown_lng",
            "breakdown_location",
            "collected_weight_before_breakdown_kg",
            "breakdown_reason",
            "breakdown_remarks",
            "status",
            "approval_status",
            "approved_by",
            "approved_by_detail",
            "approved_at",
            "rejection_remarks",
            "photos",
            "new_assignment_id",
            "pending_stops",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "unique_id",
            "alt_staff_template_id",
            "alt_staff_template_detail",
            "status",
            "approval_status",
            "approved_by",
            "approved_at",
            "rejection_remarks",
            "new_assignment_id",
            "pending_stops",
            "created_at",
            "updated_at",
        ]

    # ── Validation ───────────────────────────────────────────────────

    def validate_trip_assignment_id(self, value):
        return _existing_id(DailyTripAssignment, "unique_id", value, "Invalid trip assignment.")

    def validate_breakdown_vehicle_id(self, value):
        return _existing_id(VehicleCreation, "unique_id", value, "Invalid vehicle.")

    def validate_replacement_vehicle_id(self, value):
        return _existing_id(VehicleCreation, "unique_id", value, "Invalid vehicle.")

    def validate_replacement_driver_id(self, value):
        return _existing_id(Staffcreation, "staff_unique_id", value, "Invalid staff.")

    def validate_replacement_operator_id(self, value):
        return _existing_id(Staffcreation, "staff_unique_id", value, "Invalid staff.")

    def validate(self, attrs):
        assignment_id = attrs.get("trip_assignment_id")
        assignment = (
            DailyTripAssignment.objects.filter(unique_id=assignment_id).first()
            if assignment_id else None
        )
        if assignment:
            if assignment.status in [
                DailyTripAssignment.STATUS_COMPLETED,
                DailyTripAssignment.STATUS_CANCELLED,
            ]:
                raise serializers.ValidationError(
                    {"trip_assignment_id": "Cannot log a breakdown for a completed or cancelled trip."}
                )

        repl = attrs.get("replacement_vehicle_id")
        orig = attrs.get("breakdown_vehicle_id")
        if repl and orig and repl == orig:
            raise serializers.ValidationError(
                {"replacement_vehicle_id": "Replacement vehicle must be different from the broken vehicle."}
            )

        if assignment and repl:
            conflict = DailyTripAssignment.objects.filter(
                vehicle_id=repl,
                trip_date=assignment.trip_date,
                status__in=[
                    DailyTripAssignment.STATUS_SCHEDULED,
                    DailyTripAssignment.STATUS_IN_PROGRESS,
                ],
                is_deleted=False,
            ).exclude(pk=assignment.pk).exists()
            if conflict:
                raise serializers.ValidationError(
                    {
                        "replacement_vehicle_id": (
                            f"Replacement vehicle is already assigned to another active trip on {assignment.trip_date}."
                        )
                    }
                )

        return attrs

    # ── Detail helpers ───────────────────────────────────────────────

    def _staff_dict(self, staff):
        if not staff:
            return None
        return {
            "unique_id": staff.staff_unique_id,
            "name": staff.employee_name,
        }

    def _vehicle_dict(self, vehicle):
        if not vehicle:
            return None
        return {
            "unique_id": vehicle.unique_id,
            "vehicle_no": vehicle.vehicle_no,
            "capacity": str(vehicle.capacity) if vehicle.capacity else None,
        }

    def _alt_staff_template_dict(self, template):
        if not template:
            return None
        return {
            "unique_id": template.unique_id,
            "display_code": template.display_code,
            "base_staff_template_id": getattr(template, "staff_template_id", None),
            "driver": self._staff_dict(getattr(template, "driver", None)),
            "operator": self._staff_dict(getattr(template, "operator", None)),
            "change_reason": template.change_reason,
            "change_remarks": template.change_remarks,
            "approval_status": template.approval_status,
        }

    def get_trip_assignment_detail(self, obj):
        a = obj.trip_assignment
        if not a:
            return None
        trip_plan = getattr(a, "trip_plan", None)
        location_name, location_level = flat_geo_display(a)
        return {
            "unique_id": a.unique_id,
            "trip_date": str(a.trip_date),
            "status": a.status,
            "scheduled_time": str(a.scheduled_time) if a.scheduled_time else None,
            "location_name": location_name,
            "location_level": location_level,
            "trip_plan_display_code": trip_plan.display_code if trip_plan else None,
        }

    def get_breakdown_vehicle_detail(self, obj):
        return self._vehicle_dict(obj.breakdown_vehicle)

    def get_replacement_vehicle_detail(self, obj):
        return self._vehicle_dict(obj.replacement_vehicle)

    def get_replacement_driver_detail(self, obj):
        return self._staff_dict(obj.replacement_driver)

    def get_replacement_operator_detail(self, obj):
        return self._staff_dict(obj.replacement_operator)

    def get_original_driver_detail(self, obj):
        try:
            assignment = obj.trip_assignment
            # The crew actually on the trip at breakdown time is whatever the
            # assignment was running on: its own alternative staff template
            # (if one was already substituted in) takes precedence over the
            # assignment's/trip plan's base staff template.
            active_alt = getattr(assignment, "alt_staff_template", None)
            trip_plan = getattr(assignment, "trip_plan", None)
            template = (
                active_alt
                or getattr(trip_plan, "staff_template", None)
                or assignment.staff_template
            )
            if template:
                return self._staff_dict(template.driver)
        except Exception:
            pass
        return None

    def get_original_operator_detail(self, obj):
        try:
            assignment = obj.trip_assignment
            active_alt = getattr(assignment, "alt_staff_template", None)
            trip_plan = getattr(assignment, "trip_plan", None)
            template = (
                active_alt
                or getattr(trip_plan, "staff_template", None)
                or assignment.staff_template
            )
            if template:
                return self._staff_dict(template.operator)
        except Exception:
            pass
        return None

    def get_alt_staff_template_detail(self, obj):
        return self._alt_staff_template_dict(obj.alt_staff_template)

    def get_approved_by_detail(self, obj):
        return self._staff_dict(obj.approved_by)

    def get_new_assignment_id(self, obj):
        return obj.new_assignment_id

    def get_pending_stops(self, obj):
        """What's still outstanding on the trip being broken down — bin
        collection points for a bin trip (supervisor picks which carry over
        at /verify/), or un-collected houses for a household trip (all of
        them auto-carry). Not shown once a replacement trip already exists."""
        assignment = obj.trip_assignment
        if not assignment or obj.new_assignment_id:
            return None
        from app.services.retrip_service import build_pending_snapshot

        return build_pending_snapshot(assignment)

    def get_photos(self, obj):
        request = self.context.get("request")
        photos = []
        for photo in obj.photos.all():
            url = photo.photo.url if photo.photo else None
            if url and request is not None:
                url = request.build_absolute_uri(url)
            photos.append({"id": photo.pk, "photo": url, "uploaded_at": photo.uploaded_at})
        return photos


class VehicleBreakdownVerifySerializer(serializers.Serializer):
    """Used for PATCH /{id}/verify/ — the supervisor picks the replacement
    vehicle/driver/operator here (if not already set) and approves the breakdown."""
    remarks = serializers.CharField(required=False, allow_blank=True, default="")
    replacement_vehicle_id = serializers.CharField(
        max_length=40, required=False, allow_null=True, allow_blank=True
    )
    replacement_driver_id = serializers.CharField(
        max_length=30, required=False, allow_null=True, allow_blank=True
    )
    replacement_operator_id = serializers.CharField(
        max_length=30, required=False, allow_null=True, allow_blank=True
    )
    # Bin trips: which pending collection points move to the continuation
    # trip. Required for a bin trip, ignored for a household trip (every
    # pending household stop always carries over) — mirrors Re-Trip.
    collection_point_ids = serializers.ListField(
        child=serializers.CharField(), required=False, allow_empty=True
    )

    def validate_replacement_vehicle_id(self, value):
        return _existing_id(VehicleCreation, "unique_id", value, "Invalid vehicle.")

    def validate_replacement_driver_id(self, value):
        return _existing_id(Staffcreation, "staff_unique_id", value, "Invalid staff.")

    def validate_replacement_operator_id(self, value):
        return _existing_id(Staffcreation, "staff_unique_id", value, "Invalid staff.")

    def save(self):
        instance = self.context["instance"]
        account = self.context.get("account")
        remarks = self.validated_data.get("remarks", "")
        now = timezone.now()

        if instance.approval_status == VehicleBreakdown.APPROVAL_APPROVED:
            raise serializers.ValidationError("Breakdown has already been approved.")
        if instance.approval_status == VehicleBreakdown.APPROVAL_REJECTED:
            raise serializers.ValidationError("Rejected breakdowns cannot be approved.")

        replacement_vehicle = self.validated_data.get("replacement_vehicle_id") or instance.replacement_vehicle_id
        replacement_driver = self.validated_data.get("replacement_driver_id") or instance.replacement_driver_id
        replacement_operator = self.validated_data.get("replacement_operator_id") or instance.replacement_operator_id
        if not (replacement_vehicle and replacement_driver and replacement_operator):
            raise serializers.ValidationError(
                "Select a replacement vehicle, driver, and operator before approving this breakdown."
            )

        from django.db import transaction
        from app.models.core_modules.schedule_setup.alternative_staff_template import AlternativeStaffTemplate
        from app.services import retrip_service

        assignment = instance.trip_assignment
        pending_bins = list(assignment.pending_bin_stops())
        pending_households = list(assignment.pending_household_stops())
        is_bin_trip = assignment.trip_collection_points.exists()
        collection_point_ids = self.validated_data.get("collection_point_ids")
        if not pending_bins and not pending_households:
            raise serializers.ValidationError("There are no pending stops to carry over.")
        if is_bin_trip and pending_bins and not collection_point_ids:
            raise serializers.ValidationError(
                {"collection_point_ids": "Select at least one collection point to carry over to the replacement trip."}
            )
        if collection_point_ids:
            pending_bin_ids = {stop.unique_id for stop in pending_bins}
            unknown = set(collection_point_ids) - pending_bin_ids
            if unknown:
                raise serializers.ValidationError(
                    {"collection_point_ids": "Selected collection point is not pending on this trip."}
                )

        with transaction.atomic():
            # Always create a fresh AlternativeStaffTemplate for this
            # breakdown's replacement crew. A staff_template can accumulate
            # several of these over time (one per breakdown event) — reusing
            # a prior breakdown's row here would silently overwrite its
            # driver/operator, corrupting that earlier breakdown's history.
            alt_template = AlternativeStaffTemplate.objects.create(
                staff_template_id=assignment.staff_template_id,
                driver_id=replacement_driver,
                operator_id=replacement_operator,
                change_reason="Vehicle Breakdown",
                change_remarks=remarks or instance.breakdown_remarks or "",
            )

            # Open a continuation crewed by the replacement
            # vehicle/driver/operator, carrying over the pending
            # bin/household stops (same rules as Re-Trip). The source trip is
            # not completed here; verification only assigns the replacement.
            try:
                continuation = retrip_service.create_breakdown_continuation(
                    assignment,
                    vehicle_id=replacement_vehicle,
                    alt_staff_template_id=alt_template.unique_id,
                    collection_point_ids=collection_point_ids,
                )
            except ValueError as exc:
                raise serializers.ValidationError(str(exc)) from exc

            # Update the breakdown record
            approved_by_staff_id = getattr(account, "staff_id", None) if account else None

            VehicleBreakdown.objects.filter(pk=instance.pk).update(
                replacement_vehicle_id=replacement_vehicle,
                replacement_driver_id=replacement_driver,
                replacement_operator_id=replacement_operator,
                alt_staff_template_id=alt_template.unique_id,
                new_assignment_id=continuation.unique_id,
                status=VehicleBreakdown.STATUS_REPLACEMENT_ARRANGED,
                approval_status=VehicleBreakdown.APPROVAL_APPROVED,
                approved_by_id=approved_by_staff_id,
                approved_at=now,
                updated_at=now,
            )
            instance.refresh_from_db()

            from app.models.core_modules.daily_operations.secondary_bin_collection_event import BinCollectionEvent

            BinCollectionEvent.objects.filter(
                trip_assignment_id=ref_id(assignment),
                is_deleted=False,
            ).update(
                vehicle_breakdown_id=ref_id(instance),
                updated_at=now,
            )

        return instance


class VehicleBreakdownRejectSerializer(serializers.Serializer):
    """Used for PATCH /{id}/reject/ — rejects the breakdown request."""
    rejection_remarks = serializers.CharField(required=True)

    def save(self):
        instance = self.context["instance"]
        now = timezone.now()

        if instance.approval_status != VehicleBreakdown.APPROVAL_PENDING:
            raise serializers.ValidationError(
                "Only pending breakdowns can be rejected."
            )

        VehicleBreakdown.objects.filter(pk=instance.pk).update(
            status=VehicleBreakdown.STATUS_REJECTED,
            approval_status=VehicleBreakdown.APPROVAL_REJECTED,
            rejection_remarks=self.validated_data["rejection_remarks"],
            updated_at=now,
        )
        instance.refresh_from_db()
        return instance
