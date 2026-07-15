from django.utils import timezone
from rest_framework import serializers

from app.models.schedule_masters.vehicle_breakdown import VehicleBreakdown
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.user_creations.staffcreation import Staffcreation
from app.utils.hierarchy import flat_geo_display


class VehicleBreakdownSerializer(serializers.ModelSerializer):

    # Write fields — accept unique_id strings
    trip_assignment_id = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=DailyTripAssignment.objects.filter(is_deleted=False),
    )
    breakdown_vehicle_id = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=VehicleCreation.objects.filter(is_deleted=False),
    )
    replacement_vehicle_id = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=VehicleCreation.objects.filter(is_deleted=False),
    )
    replacement_driver_id = serializers.SlugRelatedField(
        slug_field="staff_unique_id",
        queryset=Staffcreation.objects.filter(is_deleted=False),
    )
    replacement_operator_id = serializers.SlugRelatedField(
        slug_field="staff_unique_id",
        queryset=Staffcreation.objects.filter(is_deleted=False),
    )

    # Read-only detail fields
    trip_assignment_detail = serializers.SerializerMethodField(read_only=True)
    breakdown_vehicle_detail = serializers.SerializerMethodField(read_only=True)
    replacement_vehicle_detail = serializers.SerializerMethodField(read_only=True)
    replacement_driver_detail = serializers.SerializerMethodField(read_only=True)
    replacement_operator_detail = serializers.SerializerMethodField(read_only=True)
    original_driver_detail = serializers.SerializerMethodField(read_only=True)
    original_operator_detail = serializers.SerializerMethodField(read_only=True)
    approved_by_detail = serializers.SerializerMethodField(read_only=True)

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
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "unique_id",
            "alt_staff_template_id",
            "status",
            "approval_status",
            "approved_by",
            "approved_at",
            "rejection_remarks",
            "created_at",
            "updated_at",
        ]

    # ── Validation ───────────────────────────────────────────────────

    def validate(self, attrs):
        assignment = attrs.get("trip_assignment_id")
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
        if repl and orig and repl.unique_id == orig.unique_id:
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

    def get_trip_assignment_detail(self, obj):
        a = obj.trip_assignment_id
        if not a:
            return None
        trip_plan = getattr(a, "trip_plan_id", None)
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
        return self._vehicle_dict(obj.breakdown_vehicle_id)

    def get_replacement_vehicle_detail(self, obj):
        return self._vehicle_dict(obj.replacement_vehicle_id)

    def get_replacement_driver_detail(self, obj):
        return self._staff_dict(obj.replacement_driver_id)

    def get_replacement_operator_detail(self, obj):
        return self._staff_dict(obj.replacement_operator_id)

    def get_original_driver_detail(self, obj):
        try:
            assignment = obj.trip_assignment_id
            template = assignment.alt_staff_template_id or assignment.staff_template_id
            if template:
                return self._staff_dict(template.driver_id)
        except Exception:
            pass
        return None

    def get_original_operator_detail(self, obj):
        try:
            assignment = obj.trip_assignment_id
            template = assignment.alt_staff_template_id or assignment.staff_template_id
            if template:
                return self._staff_dict(template.operator_id)
        except Exception:
            pass
        return None

    def get_approved_by_detail(self, obj):
        return self._staff_dict(obj.approved_by)


class VehicleBreakdownVerifySerializer(serializers.Serializer):
    """Used for PATCH /{id}/verify/ — approves the breakdown and wires the replacement."""
    remarks = serializers.CharField(required=False, allow_blank=True, default="")

    def save(self):
        instance = self.context["instance"]
        account = self.context.get("account")
        remarks = self.validated_data.get("remarks", "")
        now = timezone.now()

        if instance.approval_status == VehicleBreakdown.APPROVAL_APPROVED:
            raise serializers.ValidationError("Breakdown has already been approved.")
        if instance.approval_status == VehicleBreakdown.APPROVAL_REJECTED:
            raise serializers.ValidationError("Rejected breakdowns cannot be approved.")

        from django.db import transaction
        from app.models.schedule_masters.alternative_staff_template import AlternativeStaffTemplate

        with transaction.atomic():
            assignment = instance.trip_assignment_id

            # Create or update AlternativeStaffTemplate for replacement crew.
            # The model has a UniqueConstraint on staff_template, so use
            # update_or_create to handle cases where one already exists.
            alt_template, _ = AlternativeStaffTemplate.objects.update_or_create(
                staff_template=assignment.staff_template_id,
                defaults=dict(
                    driver_id=instance.replacement_driver_id,
                    operator_id=instance.replacement_operator_id,
                    change_reason="Vehicle Breakdown",
                    change_remarks=remarks or instance.breakdown_remarks or "",
                ),
            )

            # Update DailyTripAssignment: replacement vehicle, alt staff template, and
            # advance status to In Progress (breakdown proves the trip was underway).
            update_fields = ["vehicle_id", "alt_staff_template_id", "updated_at"]
            assignment.vehicle_id = instance.replacement_vehicle_id
            assignment.alt_staff_template_id = alt_template
            if assignment.status == DailyTripAssignment.STATUS_SCHEDULED:
                assignment.status = DailyTripAssignment.STATUS_IN_PROGRESS
                update_fields.append("status")
            assignment.save(update_fields=update_fields)

            # Update the breakdown record
            approved_by_staff = None
            if account:
                try:
                    approved_by_staff = Staffcreation.objects.filter(
                        account=account
                    ).first()
                except Exception:
                    pass

            VehicleBreakdown.objects.filter(pk=instance.pk).update(
                alt_staff_template_id=alt_template,
                status=VehicleBreakdown.STATUS_REPLACEMENT_ARRANGED,
                approval_status=VehicleBreakdown.APPROVAL_APPROVED,
                approved_by=approved_by_staff,
                approved_at=now,
                updated_at=now,
            )
            instance.refresh_from_db()

            from app.models.schedule_masters.secondary_bin_collection_event import BinCollectionEvent

            BinCollectionEvent.objects.filter(
                trip_assignment_id=assignment,
                is_deleted=False,
            ).update(
                vehicle_breakdown_id=instance,
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
