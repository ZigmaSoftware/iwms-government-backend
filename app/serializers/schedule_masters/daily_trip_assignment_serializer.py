from rest_framework import serializers

from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
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


class DailyTripAssignmentSerializer(serializers.ModelSerializer):
    trip_plan_id = UniqueIdOrPkField(slug_field="unique_id", queryset=TripPlan.objects.filter(is_deleted=False, status="ACTIVE"), write_only=True)
    staff_template_id = UniqueIdOrPkField(slug_field="unique_id", queryset=StaffTemplate.objects.filter(is_deleted=False), write_only=True, required=False, allow_null=True)
    state_id = UniqueIdOrPkField(source="state", slug_field="unique_id", queryset=State.objects.filter(is_deleted=False), write_only=True, required=False, allow_null=True)
    district_id = UniqueIdOrPkField(source="district", slug_field="unique_id", queryset=District.objects.filter(is_deleted=False), write_only=True, required=False, allow_null=True)
    area_type_id = UniqueIdOrPkField(source="area_type", slug_field="unique_id", queryset=AreaType.objects.filter(is_deleted=False), write_only=True, required=False, allow_null=True)
    corporation_id = UniqueIdOrPkField(source="corporation", slug_field="unique_id", queryset=Corporation.objects.filter(is_deleted=False), write_only=True, required=False, allow_null=True)
    municipality_id = UniqueIdOrPkField(source="municipality", slug_field="unique_id", queryset=Municipality.objects.filter(is_deleted=False), write_only=True, required=False, allow_null=True)
    town_panchayat_id = UniqueIdOrPkField(source="town_panchayat", slug_field="unique_id", queryset=TownPanchayat.objects.filter(is_deleted=False), write_only=True, required=False, allow_null=True)
    panchayat_union_id = UniqueIdOrPkField(source="panchayat_union", slug_field="unique_id", queryset=PanchayatUnion.objects.filter(is_deleted=False), write_only=True, required=False, allow_null=True)
    panchayat_id = UniqueIdOrPkField(source="panchayat", slug_field="unique_id", queryset=Panchayat.objects.filter(is_deleted=False), write_only=True, required=False, allow_null=True)
    waste_type_id = UniqueIdOrPkField(slug_field="unique_id", queryset=WasteType.objects.filter(is_deleted=False), write_only=True, required=False, allow_null=True)
    household_waste_type_ids = serializers.SlugRelatedField(slug_field="unique_id", queryset=WasteType.objects.filter(is_deleted=False), many=True, required=False)
    household_waste_types = serializers.SerializerMethodField(read_only=True)
    vehicle_id = UniqueIdOrPkField(slug_field="unique_id", queryset=VehicleCreation.objects.filter(is_deleted=False), write_only=True, required=False, allow_null=True)
    alt_staff_template_id = UniqueIdOrPkField(slug_field="unique_id", queryset=AlternativeStaffTemplate.objects.all(), write_only=True, required=False, allow_null=True)

    collection_points_input = serializers.ListField(child=serializers.DictField(), write_only=True, required=False)

    trip_plan = serializers.SerializerMethodField(read_only=True)
    staff_template = serializers.SerializerMethodField(read_only=True)
    effective_staff = serializers.SerializerMethodField(read_only=True)
    collection_points = serializers.SerializerMethodField(read_only=True)
    household_collection_points = serializers.SerializerMethodField(read_only=True)
    breakdown_info = serializers.SerializerMethodField(read_only=True)
    state = serializers.SerializerMethodField(read_only=True)
    district = serializers.SerializerMethodField(read_only=True)
    area_type = serializers.SerializerMethodField(read_only=True)
    corporation = serializers.SerializerMethodField(read_only=True)
    municipality = serializers.SerializerMethodField(read_only=True)
    town_panchayat = serializers.SerializerMethodField(read_only=True)
    panchayat_union = serializers.SerializerMethodField(read_only=True)
    panchayat = serializers.SerializerMethodField(read_only=True)
    waste_type = serializers.SerializerMethodField(read_only=True)
    vehicle = serializers.SerializerMethodField(read_only=True)
    collection_types = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = DailyTripAssignment
        fields = [
            "unique_id", "trip_plan_id", "staff_template_id", "state_id", "district_id", "area_type_id", "corporation_id",
            "municipality_id", "town_panchayat_id", "panchayat_union_id", "panchayat_id",
            "waste_type_id", "household_waste_type_ids", "household_waste_types",
            "vehicle_id", "alt_staff_template_id", "collection_points_input", "trip_plan", "staff_template",
            "effective_staff", "state", "district", "area_type", "corporation", "municipality",
            "town_panchayat", "panchayat_union", "panchayat", "waste_type", "vehicle", "collection_types",
            "collection_points", "household_collection_points", "breakdown_info",
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
            "district": self._ref(plan.district),
            "panchayat": self._panchayat_payload(plan.panchayat),
            "vehicle_no": getattr(getattr(plan, "vehicle_id", None), "vehicle_no", None),
            "waste_type_name": getattr(getattr(plan, "waste_type_id", None), "waste_type_name", None),
            "has_bin": TripPlanCollectionPoint.COLLECTION_TYPE_BIN in stop_types,
            "has_household": TripPlanCollectionPoint.COLLECTION_TYPE_HOUSEHOLD in stop_types,
            "has_bulk": TripPlanCollectionPoint.COLLECTION_TYPE_BULK in stop_types,
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
        return self._panchayat_payload(obj.panchayat)

    def get_state(self, obj):
        return self._ref(obj.state)

    def get_district(self, obj):
        return self._ref(obj.district)

    def get_area_type(self, obj):
        return self._ref(obj.area_type)

    def get_corporation(self, obj):
        return self._ref(obj.corporation, "corporation_name")

    def get_municipality(self, obj):
        return self._ref(obj.municipality, "municipality_name")

    def get_town_panchayat(self, obj):
        return self._ref(obj.town_panchayat, "town_panchayat_name")

    def get_panchayat_union(self, obj):
        return self._ref(obj.panchayat_union, "union_name")

    def _ref(self, value, label_attr="name"):
        if not value:
            return None
        return {"unique_id": value.unique_id, label_attr: getattr(value, label_attr, None)}

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
            return {"has_bin": False, "has_household": False, "has_bulk": False}
        stops = plan.plan_collection_points.filter(is_deleted=False).values_list("collection_type", flat=True)
        return {
            "has_bin": TripPlanCollectionPoint.COLLECTION_TYPE_BIN in stops,
            "has_household": TripPlanCollectionPoint.COLLECTION_TYPE_HOUSEHOLD in stops,
            "has_bulk": TripPlanCollectionPoint.COLLECTION_TYPE_BULK in stops,
        }

    def get_collection_points(self, obj):
        stops = obj.trip_collection_points.filter(is_deleted=False).select_related(
            "collection_point_id", "bin_id", "collected_by",
        ).order_by("sequence")
        return [{
            "unique_id": stop.unique_id,
            "collection_point_id": stop.collection_point_id_id,
            "collection_point": {
                "unique_id": stop.collection_point_id.unique_id,
                "cp_name": stop.collection_point_id.cp_name,
                "latitude": stop.collection_point_id.latitude,
                "longitude": stop.collection_point_id.longitude,
            } if stop.collection_point_id else None,
            "bin_id": stop.bin_id_id,
            "bin": {"unique_id": stop.bin_id.unique_id, "bin_name": stop.bin_id.bin_name} if stop.bin_id else None,
            "sequence": stop.sequence,
            "is_collected": stop.is_collected,
            "collected_at": stop.collected_at,
            "collected_weight_kg": stop.collected_weight_kg,
            "status": stop.status,
        } for stop in stops]

    def get_household_collection_points(self, obj):
        stops = obj.trip_household_collections.filter(is_deleted=False).select_related("customer_id").order_by("sequence")
        return [{
            "unique_id": stop.unique_id,
            "customer_id": stop.customer_id_id,
            "customer": {
                "unique_id": getattr(stop.customer_id, "unique_id", None),
                "customer_name": getattr(stop.customer_id, "customer_name", None),
                "building_no": getattr(stop.customer_id, "building_no", None),
                "street": getattr(stop.customer_id, "street", None),
            } if stop.customer_id else None,
            "collection_type": stop.collection_type,
            "sequence": stop.sequence,
            "is_collected": stop.is_collected,
            "collected_at": stop.collected_at,
            "collected_weight_kg": stop.collected_weight_kg,
            "status": stop.status,
        } for stop in stops]

    def get_breakdown_info(self, obj):
        try:
            bd = obj.vehicle_breakdown
        except Exception:
            return None
        if not bd or getattr(bd, "is_deleted", False):
            return None
        return {
            "unique_id": bd.unique_id,
            "status": bd.status,
            "approval_status": bd.approval_status,
            "breakdown_reason": bd.breakdown_reason,
            "breakdown_time": str(bd.breakdown_time) if bd.breakdown_time else None,
            "breakdown_location": bd.breakdown_location,
            "breakdown_vehicle_no": getattr(bd.breakdown_vehicle_id, "vehicle_no", None),
            "replacement_vehicle_no": getattr(bd.replacement_vehicle_id, "vehicle_no", None),
            "replacement_driver": getattr(bd.replacement_driver_id, "employee_name", None),
            "replacement_operator": getattr(bd.replacement_operator_id, "employee_name", None),
        }

    def _sync_collection_points(self, assignment, points):
        # Update-only sync: stops are generated from the Trip Plan by signals;
        # this applies inline edits (sequence, weight, collected, status) from the form.
        if points is None:
            return
        from app.models.schedule_masters.daily_trip_collection_point import DailyTripCollectionPoint

        for item in points:
            unique_id = item.get("unique_id")
            if not unique_id:
                continue
            stop = DailyTripCollectionPoint.objects.filter(
                unique_id=unique_id,
                trip_assignment_id=assignment,
                is_deleted=False,
            ).first()
            if not stop:
                continue
            for field in ["sequence", "is_collected", "collected_at", "collected_weight_kg", "status"]:
                if field in item:
                    value = item.get(field)
                    setattr(stop, field, value if value != "" else None)
            stop.save()

    def create(self, validated_data):
        validated_data.pop("collection_points_input", None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        collection_points = validated_data.pop("collection_points_input", None)
        assignment = super().update(instance, validated_data)
        self._sync_collection_points(assignment, collection_points)
        return assignment

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        trip_plan = attrs.get("trip_plan_id", getattr(instance, "trip_plan_id", None))
        trip_date = attrs.get("trip_date", getattr(instance, "trip_date", None))
        scheduled_time = attrs.get("scheduled_time", getattr(instance, "scheduled_time", None))

        geo_fields = ("state", "district", "area_type", "corporation", "municipality", "town_panchayat", "panchayat_union", "panchayat")
        if trip_plan:
            attrs.setdefault("staff_template_id", trip_plan.staff_template_id)
            attrs.setdefault("vehicle_id", trip_plan.vehicle_id)
            attrs.setdefault("waste_type_id", trip_plan.waste_type_id)
            for field in geo_fields:
                attrs.setdefault(field, getattr(trip_plan, field, None))
            attrs.setdefault("scheduled_time", trip_plan.scheduled_time)
            scheduled_time = attrs.get("scheduled_time", scheduled_time)

        if not any(attrs.get(field, getattr(instance, field, None)) for field in ("district", "corporation", "municipality", "town_panchayat", "panchayat_union", "panchayat")):
            raise serializers.ValidationError("Daily trip assignment must belong to a geographic area.")

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
