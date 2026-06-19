from rest_framework import serializers

from app.models.masters.panchayat import Panchayat
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.schedule_masters.alternative_staff_template import AlternativeStaffTemplate
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.staff_template import StaffTemplate
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.serializers.user_creations.user_serializer import UniqueIdOrPkField
from app.utils.hierarchy import hierarchy_payload, selected_hierarchy_values


class DailyTripAssignmentSerializer(serializers.ModelSerializer):
    trip_plan_id = UniqueIdOrPkField(slug_field="unique_id", queryset=TripPlan.objects.filter(is_deleted=False, status="ACTIVE"), write_only=True)
    staff_template_id = UniqueIdOrPkField(slug_field="unique_id", queryset=StaffTemplate.objects.filter(is_deleted=False), write_only=True, required=False, allow_null=True)
    corporation_id = UniqueIdOrPkField(slug_field="unique_id", queryset=Corporation.objects.filter(is_deleted=False), write_only=True, required=False, allow_null=True)
    municipality_id = UniqueIdOrPkField(slug_field="unique_id", queryset=Municipality.objects.filter(is_deleted=False), write_only=True, required=False, allow_null=True)
    town_panchayat_id = UniqueIdOrPkField(slug_field="unique_id", queryset=TownPanchayat.objects.filter(is_deleted=False), write_only=True, required=False, allow_null=True)
    panchayat_union_id = UniqueIdOrPkField(slug_field="unique_id", queryset=PanchayatUnion.objects.filter(is_deleted=False), write_only=True, required=False, allow_null=True)
    panchayat_id = UniqueIdOrPkField(slug_field="unique_id", queryset=Panchayat.objects.filter(is_deleted=False), write_only=True, required=False, allow_null=True)
    waste_type_id = UniqueIdOrPkField(slug_field="unique_id", queryset=WasteType.objects.filter(is_deleted=False), write_only=True, required=False, allow_null=True)
    household_waste_type_ids = serializers.SlugRelatedField(slug_field="unique_id", queryset=WasteType.objects.filter(is_deleted=False), many=True, required=False)
    household_waste_types = serializers.SerializerMethodField(read_only=True)
    vehicle_id = UniqueIdOrPkField(slug_field="unique_id", queryset=VehicleCreation.objects.filter(is_deleted=False), write_only=True, required=False, allow_null=True)
    alt_staff_template_id = UniqueIdOrPkField(slug_field="unique_id", queryset=AlternativeStaffTemplate.objects.all(), write_only=True, required=False, allow_null=True)

    trip_plan = serializers.SerializerMethodField(read_only=True)
    staff_template = serializers.SerializerMethodField(read_only=True)
    effective_staff = serializers.SerializerMethodField(read_only=True)
    hierarchy = serializers.SerializerMethodField(read_only=True)
    panchayat = serializers.SerializerMethodField(read_only=True)
    waste_type = serializers.SerializerMethodField(read_only=True)
    vehicle = serializers.SerializerMethodField(read_only=True)
    collection_types = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = DailyTripAssignment
        fields = [
            "unique_id", "trip_plan_id", "staff_template_id", "corporation_id",
            "municipality_id", "town_panchayat_id", "panchayat_union_id", "panchayat_id",
            "waste_type_id", "household_waste_type_ids", "household_waste_types",
            "vehicle_id", "alt_staff_template_id", "trip_plan", "staff_template",
            "effective_staff", "hierarchy", "panchayat", "waste_type", "vehicle", "collection_types",
            "trip_date", "scheduled_time", "actual_start_time", "actual_end_time",
            "status", "approval_status", "remarks", "created_at", "updated_at",
        ]
        read_only_fields = ["unique_id", "actual_start_time", "actual_end_time", "approval_status", "created_at", "updated_at"]

    def get_trip_plan(self, obj):
        from app.models.schedule_masters.trip_plan_collection_point import TripPlanCollectionPoint
        plan = obj.trip_plan_id
        if not plan:
            return None
        stop_types = list(plan.plan_collection_points.filter(is_deleted=False).values_list("collection_type", flat=True))
        return {
            "unique_id": plan.unique_id,
            "display_code": plan.display_code,
            "scheduled_time": plan.scheduled_time,
            "hierarchy": hierarchy_payload(plan),
            "panchayat": self._panchayat_payload(getattr(plan, "panchayat_id", None)),
            "vehicle_no": getattr(getattr(plan, "vehicle_id", None), "vehicle_no", None),
            "waste_type_name": getattr(getattr(plan, "waste_type_id", None), "waste_type_name", None),
            "has_bin": TripPlanCollectionPoint.COLLECTION_TYPE_BIN in stop_types,
            "has_household": TripPlanCollectionPoint.COLLECTION_TYPE_HOUSEHOLD in stop_types,
        }

    def get_staff_template(self, obj):
        st = obj.staff_template_id
        if not st:
            return None
        return {"unique_id": st.unique_id, "display_code": st.display_code, "driver": getattr(getattr(st, "driver_id", None), "employee_name", None), "operator": getattr(getattr(st, "operator_id", None), "employee_name", None)}

    def get_effective_staff(self, obj):
        alt = obj.alt_staff_template_id
        if alt:
            return {"source": "alternative", "unique_id": alt.unique_id, "display_code": alt.display_code, "driver": getattr(getattr(alt, "driver_id", None), "employee_name", None), "operator": getattr(getattr(alt, "operator_id", None), "employee_name", None), "from_date": str(alt.from_date), "to_date": str(alt.to_date)}
        return self.get_staff_template(obj)

    def get_panchayat(self, obj):
        return self._panchayat_payload(obj.panchayat_id)

    def get_hierarchy(self, obj):
        return hierarchy_payload(obj)

    def _panchayat_payload(self, panchayat):
        if not panchayat:
            return None
        return {"unique_id": panchayat.unique_id, "panchayat_name": panchayat.panchayat_name}

    def get_waste_type(self, obj):
        waste_type = obj.waste_type_id
        if not waste_type:
            return None
        return {"unique_id": waste_type.unique_id, "waste_type_name": getattr(waste_type, "waste_type_name", None)}

    def get_vehicle(self, obj):
        vehicle = obj.vehicle_id
        if not vehicle:
            return None
        return {"unique_id": vehicle.unique_id, "vehicle_no": vehicle.vehicle_no}

    def get_household_waste_types(self, obj):
        return [{"unique_id": wt.unique_id, "waste_type_name": getattr(wt, "waste_type_name", None)} for wt in obj.household_waste_type_ids.all()]

    def get_collection_types(self, obj):
        from app.models.schedule_masters.trip_plan_collection_point import TripPlanCollectionPoint
        plan = obj.trip_plan_id
        if not plan:
            return {"has_bin": False, "has_household": False}
        stops = plan.plan_collection_points.filter(is_deleted=False).values_list("collection_type", flat=True)
        return {"has_bin": TripPlanCollectionPoint.COLLECTION_TYPE_BIN in stops, "has_household": TripPlanCollectionPoint.COLLECTION_TYPE_HOUSEHOLD in stops}

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        trip_plan = attrs.get("trip_plan_id", getattr(instance, "trip_plan_id", None))
        trip_date = attrs.get("trip_date", getattr(instance, "trip_date", None))
        scheduled_time = attrs.get("scheduled_time", getattr(instance, "scheduled_time", None))

        if trip_plan:
            attrs.setdefault("staff_template_id", trip_plan.staff_template_id)
            attrs.setdefault("vehicle_id", trip_plan.vehicle_id)
            attrs.setdefault("waste_type_id", trip_plan.waste_type_id)
            for field, value in selected_hierarchy_values(trip_plan).items():
                attrs.setdefault(field, value)
            attrs.setdefault("scheduled_time", trip_plan.scheduled_time)
            scheduled_time = attrs.get("scheduled_time", scheduled_time)

        if not selected_hierarchy_values(type("Merged", (), {
            field: attrs.get(field, getattr(instance, field, None)) for field in (
                "corporation_id", "municipality_id", "town_panchayat_id", "panchayat_union_id", "panchayat_id"
            )
        })()):
            raise serializers.ValidationError("Daily trip assignment must belong to a hierarchy level.")

        if trip_plan and trip_date and scheduled_time:
            conflict_qs = DailyTripAssignment.objects.filter(
                trip_plan_id=trip_plan,
                trip_date=trip_date,
                scheduled_time=scheduled_time,
                is_deleted=False,
            ).exclude(status=DailyTripAssignment.STATUS_CANCELLED)
            if instance:
                conflict_qs = conflict_qs.exclude(pk=instance.pk)
            if conflict_qs.exists():
                raise serializers.ValidationError("Trip plan already assigned for this date and time.")

        staff_template = attrs.get("staff_template_id", getattr(instance, "staff_template_id", None))
        if staff_template and trip_date and "alt_staff_template_id" not in attrs:
            attrs["alt_staff_template_id"] = AlternativeStaffTemplate.objects.filter(
                staff_template=staff_template,
                from_date__lte=trip_date,
                to_date__gte=trip_date,
            ).first()

        return attrs


class DailyTripAssignmentStatusSerializer(serializers.Serializer):
    VALID_TRANSITIONS = {
        DailyTripAssignment.STATUS_SCHEDULED: [DailyTripAssignment.STATUS_IN_PROGRESS],
        DailyTripAssignment.STATUS_IN_PROGRESS: [DailyTripAssignment.STATUS_COMPLETED],
    }

    status = serializers.ChoiceField(choices=DailyTripAssignment.STATUS_CHOICES)

    def validate_status(self, value):
        instance = self.context.get("instance")
        if not instance:
            return value
        current = instance.status
        if value == DailyTripAssignment.STATUS_CANCELLED:
            return value
        if value not in self.VALID_TRANSITIONS.get(current, []):
            raise serializers.ValidationError(f"Cannot change status from {current} to {value}.")
        return value


class DailyTripAssignmentApprovalSerializer(serializers.Serializer):
    approval_status = serializers.ChoiceField(choices=DailyTripAssignment.APPROVAL_CHOICES)
