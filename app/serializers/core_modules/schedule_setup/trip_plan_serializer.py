from rest_framework import serializers

from app.models.masters.waste_masters.bins import Bins
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.superadmin.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.masters.panchayat import Panchayat
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.ward import Ward
from app.models.core_modules.schedule_setup.collection_point import Collection_point
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.models.core_modules.schedule_setup.trip_plan_collection_point import TripPlanCollectionPoint
from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.models.masters.waste_masters.wastetype import WasteType
from app.utils import ref_cache

_GEO_LOOKUP_MODELS = {
    "state": (State, "name"),
    "district": (District, "name"),
    "area_type": (AreaType, "name"),
    "corporation": (Corporation, "corporation_name"),
    "municipality": (Municipality, "municipality_name"),
    "town_panchayat": (TownPanchayat, "town_panchayat_name"),
    "panchayat_union": (PanchayatUnion, "union_name"),
    "panchayat": (Panchayat, "panchayat_name"),
}


class TripPlanStopInputSerializer(serializers.Serializer):
    collection_type = serializers.ChoiceField(
        choices=TripPlanCollectionPoint.COLLECTION_TYPE_CHOICES,
        default=TripPlanCollectionPoint.COLLECTION_TYPE_BIN,
    )
    collection_point_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    bin_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    customer_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    sequence = serializers.IntegerField(min_value=1)
    is_active = serializers.BooleanField(default=True)


class TripPlanSerializer(serializers.ModelSerializer):
    # ---- Geo hierarchy: plain unique_id strings in, display names out ----
    # TripPlan's own columns are literally named "<field>_id" (CharField, no
    # DB relation) — same convention as Ward/Corporation/District/etc. — so
    # these input fields need no `source=` override.
    state_id = serializers.CharField(required=False, allow_null=True)
    district_id = serializers.CharField()
    area_type_id = serializers.CharField(required=False, allow_null=True)
    corporation_id = serializers.CharField(required=False, allow_null=True)
    municipality_id = serializers.CharField(required=False, allow_null=True)
    town_panchayat_id = serializers.CharField(required=False, allow_null=True)
    panchayat_union_id = serializers.CharField(required=False, allow_null=True)
    panchayat_id = serializers.CharField(required=False, allow_null=True)
    # Plain unique_ids (no DB relation); checked in validate_*.
    staff_template_id = serializers.CharField(write_only=True)
    vehicle_id = serializers.CharField(write_only=True)
    supervisor_id = serializers.CharField(write_only=True, required=False, allow_null=True)
    # Multiple waste types support
    waste_type_ids = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=WasteType.objects.filter(is_deleted=False),
        many=True,
        required=False,
        source="waste_types",
        write_only=True,
    )
    ward_ids = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=Ward.objects.filter(is_deleted=False),
        many=True,
        required=False,
        source="wards",
        write_only=True,
    )
    collection_points = TripPlanStopInputSerializer(many=True, write_only=True, required=False)
    is_auto_assign = serializers.BooleanField(required=False)
    repeat_days = serializers.ListField(child=serializers.IntegerField(min_value=0, max_value=6), required=False, allow_null=True)

    state = serializers.SerializerMethodField()
    district = serializers.SerializerMethodField()
    area_type = serializers.SerializerMethodField()
    corporation = serializers.SerializerMethodField()
    municipality = serializers.SerializerMethodField()
    town_panchayat = serializers.SerializerMethodField()
    panchayat_union = serializers.SerializerMethodField()
    panchayat = serializers.SerializerMethodField()
    staff_template = serializers.SerializerMethodField()
    vehicle = serializers.SerializerMethodField()
    supervisor = serializers.SerializerMethodField()
    waste_types_detail = serializers.SerializerMethodField()
    wards_detail = serializers.SerializerMethodField()
    plan_collection_points = serializers.SerializerMethodField()

    class Meta:
        model = TripPlan
        fields = [
            "unique_id", "display_code", "state_id", "district_id", "area_type_id", "corporation_id",
            "municipality_id", "town_panchayat_id", "panchayat_union_id", "panchayat_id",
            "staff_template_id", "vehicle_id", "supervisor_id",
            "waste_type_ids", "ward_ids", "wards_detail", "state", "district", "area_type", "corporation",
            "municipality", "town_panchayat", "panchayat_union", "panchayat",
            "staff_template", "vehicle", "supervisor",
            "waste_types_detail", "collection_type", "trip_trigger_weight_kg",
            "max_vehicle_capacity_kg", "scheduled_time", "is_auto_assign", "repeat_days",
            "approval_status", "status", "collection_points", "plan_collection_points",
            "created_at", "updated_at",
        ]
        read_only_fields = ["unique_id", "display_code", "created_at", "updated_at"]

    def _ref(self, obj, field):
        # TripPlan's own geo columns are now plain unique_id strings (no DB
        # relation), so the display ref is resolved with a lookup against
        # the relevant master rather than attribute-chaining a live FK.
        value = getattr(obj, f"{field}_id", None)
        if not value:
            return None
        model, label_attr = _GEO_LOOKUP_MODELS[field]
        name = getattr(ref_cache.get(model, value, "unique_id"), label_attr, None)
        return {"unique_id": value, label_attr: name}

    def get_state(self, obj):
        return self._ref(obj, "state")

    def get_district(self, obj):
        return self._ref(obj, "district")

    def get_area_type(self, obj):
        return self._ref(obj, "area_type")

    def get_corporation(self, obj):
        return self._ref(obj, "corporation")

    def get_municipality(self, obj):
        return self._ref(obj, "municipality")

    def get_town_panchayat(self, obj):
        return self._ref(obj, "town_panchayat")

    def get_panchayat_union(self, obj):
        return self._ref(obj, "panchayat_union")

    def get_panchayat(self, obj):
        return self._ref(obj, "panchayat")

    def validate_staff_template_id(self, value):
        if not StaffTemplate.objects.filter(unique_id=value, is_deleted=False).exists():
            raise serializers.ValidationError(f"Object with unique_id={value} does not exist.")
        return value

    def validate_vehicle_id(self, value):
        if not VehicleCreation.objects.filter(unique_id=value, is_deleted=False).exists():
            raise serializers.ValidationError(f"Object with unique_id={value} does not exist.")
        return value

    def validate_supervisor_id(self, value):
        if not value:
            return None
        if not Staffcreation.objects.filter(staff_unique_id=value, is_deleted=False).exists():
            raise serializers.ValidationError(f"Object with staff_unique_id={value} does not exist.")
        return value

    def get_staff_template(self, obj):
        st = obj.staff_template
        if not st:
            return None
        return {
            "unique_id": st.unique_id,
            "display_code": st.display_code,
            "driver": getattr(getattr(st, "driver", None), "employee_name", None),
            "operator": getattr(getattr(st, "operator", None), "employee_name", None),
        }

    def get_vehicle(self, obj):
        vehicle = obj.vehicle
        if not vehicle:
            return None
        return {"unique_id": vehicle.unique_id, "vehicle_no": vehicle.vehicle_no, "capacity": vehicle.capacity}

    def get_supervisor(self, obj):
        supervisor = obj.supervisor
        if not supervisor:
            return None
        return {"unique_id": supervisor.staff_unique_id, "employee_name": supervisor.employee_name}

    def get_waste_types_detail(self, obj):
        return [
            {"unique_id": wt.unique_id, "waste_type_name": wt.waste_type_name}
            for wt in obj.waste_types.all()
        ]

    def get_wards_detail(self, obj):
        return [
            {"unique_id": ward.unique_id, "ward_name": ward.ward_name}
            for ward in obj.wards.all()
        ]

    def get_plan_collection_points(self, obj):
        stops = obj.plan_collection_points.filter(is_deleted=False)
        rows = []
        for stop in stops:
            cp, bin_obj, customer = stop.collection_point, stop.bin, stop.customer
            rows.append({
                "unique_id": stop.unique_id,
                "collection_type": stop.collection_type,
                "collection_point_id": stop.collection_point_id,
                "collection_point": {"unique_id": cp.unique_id, "cp_name": cp.cp_name} if cp else None,
                "collection_point_wards": [{"unique_id": ward.unique_id, "ward_name": ward.ward_name} for ward in cp.wards] if cp else [],
                "bin_id": stop.bin_id,
                "bin": {"unique_id": bin_obj.unique_id, "bin_name": bin_obj.bin_name} if bin_obj else None,
                "customer_id": stop.customer_id,
                "customer": {"unique_id": customer.unique_id, "customer_name": customer.customer_name, "ward_id": customer.ward_id, "ward_name": getattr(customer.ward, "ward_name", None)} if customer else None,
                "sequence": stop.sequence,
                "is_active": stop.is_active,
            })
        return rows

    def validate(self, attrs):
        instance = getattr(self, "instance", None)

        def value_for(field):
            # `attrs`/the model both key geo values as "<field>_id" (plain
            # unique_id strings) now — no live FK object to unwrap.
            return attrs.get(f"{field}_id", getattr(instance, f"{field}_id", None))

        # Most specific populated geo field wins - a trip plan scoped to one
        # Panchayat validates stops/customers against that Panchayat; one
        # scoped only to a District validates against the District.
        trip_hierarchy_field = None
        trip_hierarchy_value = None
        for field in ("panchayat", "panchayat_union", "town_panchayat", "municipality", "corporation", "district"):
            candidate = value_for(field)
            if candidate:
                trip_hierarchy_field, trip_hierarchy_value = field, candidate
                break

        if not trip_hierarchy_value:
            raise serializers.ValidationError({"district_id": "Trip plan must be assigned to at least a district."})

        trip_hierarchy_obj = _GEO_LOOKUP_MODELS[trip_hierarchy_field][0].objects.filter(
            unique_id=trip_hierarchy_value
        ).first()

        staff_template = attrs.get("staff_template_id", getattr(instance, "staff_template_id", None))
        vehicle = attrs.get("vehicle_id", getattr(instance, "vehicle_id", None))
        collection_type = attrs.get(
            "collection_type",
            getattr(instance, "collection_type", TripPlan.COLLECTION_TYPE_BIN),
        )
        wards = attrs.get(
            "wards",
            list(instance.wards.all()) if instance else [],
        )
        target_ward_ids = {str(ward.pk) for ward in wards}
        location_fields = (
            "state",
            "district",
            "area_type",
            "corporation",
            "municipality",
            "town_panchayat",
            "panchayat_union",
            "panchayat",
        )
        target_location = tuple(
            str(value_for(field) or "")
            for field in location_fields
        )

        def has_same_location(plan):
            plan_location = tuple(
                str(getattr(plan, f"{field}_id") or "")
                for field in location_fields
            )
            if plan_location != target_location:
                return False
            plan_ward_ids = {str(ward_id) for ward_id in plan.ward_ids or []}
            return plan_ward_ids == target_ward_ids

        other_plans = TripPlan.objects.filter(is_deleted=False, status=TripPlan.Status.ACTIVE)
        if instance:
            # TripPlan uses unique_id as its primary key. Exclude explicitly
            # by that identifier so an edit of the current plan never treats
            # its own staff template or vehicle as a duplicate.
            other_plans = other_plans.exclude(unique_id=instance.unique_id)
        same_type_plans = other_plans.filter(
            collection_type=collection_type,
        )
        if staff_template and any(
            has_same_location(plan)
            for plan in same_type_plans.filter(staff_template_id=staff_template)
        ):
            raise serializers.ValidationError({
                "staff_template_id": (
                    "This staff template is already assigned to another active "
                    "Trip Plan for the same location and collection type."
                )
            })
        if vehicle and any(
            has_same_location(plan)
            for plan in same_type_plans.filter(vehicle_id=vehicle)
        ):
            raise serializers.ValidationError({
                "vehicle_id": (
                    "This vehicle is already assigned to another active Trip "
                    "Plan for the same location and collection type."
                )
            })

        wards = attrs.get("wards")
        if wards and trip_hierarchy_field != "district":
            mismatched = [
                ward for ward in wards
                if getattr(ward, f"{trip_hierarchy_field}_id", None) != trip_hierarchy_obj.pk
            ]
            if mismatched:
                raise serializers.ValidationError(
                    {"ward_ids": "Selected wards must belong to the trip plan's local body."}
                )

        trigger = attrs.get("trip_trigger_weight_kg", getattr(instance, "trip_trigger_weight_kg", None))
        capacity = attrs.get("max_vehicle_capacity_kg", getattr(instance, "max_vehicle_capacity_kg", None))
        if trigger is not None and capacity is not None and trigger >= capacity:
            raise serializers.ValidationError("Trigger weight must be less than vehicle capacity.")

        stops = attrs.get("collection_points")
        plan_collection_type = attrs.get(
            "collection_type",
            getattr(instance, "collection_type", TripPlan.COLLECTION_TYPE_BIN),
        )
        if stops is not None:
            sequences = [stop["sequence"] for stop in stops]
            if len(sequences) != len(set(sequences)):
                raise serializers.ValidationError({"collection_points": "Stop sequences must be unique."})
            collection_point_bins = [
                (stop.get("collection_point_id"), stop.get("bin_id"))
                for stop in stops
                if stop.get("collection_type") == TripPlanCollectionPoint.COLLECTION_TYPE_BIN
            ]
            if len(collection_point_bins) != len(set(collection_point_bins)):
                raise serializers.ValidationError({"collection_points": "The same bin cannot be repeated at the same collection point in a trip plan."})
            # A plan generates exactly one category of daily work (see
            # TripPlan.collection_type), so every stop's type must match the
            # plan's own type. Bulk-waste plans are auto-generated and never
            # carry a manual stop list, so a bulk plan must not receive manual
            # stops, and no plan may receive a bulk stop manually.
            if plan_collection_type == TripPlanCollectionPoint.COLLECTION_TYPE_BULK and stops:
                raise serializers.ValidationError(
                    {"collection_points": "Bulk waste plans are auto-generated and take no manual stops."}
                )
            for stop in stops:
                collection_type = stop.get("collection_type") or plan_collection_type
                if collection_type == TripPlanCollectionPoint.COLLECTION_TYPE_BULK:
                    raise serializers.ValidationError(
                        {"collection_points": "Bulk waste stops cannot be added manually."}
                    )
                if collection_type != plan_collection_type:
                    raise serializers.ValidationError(
                        {"collection_points": "Stop type must match the trip plan's collection type."}
                    )
                if collection_type in {
                    TripPlanCollectionPoint.COLLECTION_TYPE_HOUSEHOLD,
                    TripPlanCollectionPoint.COLLECTION_TYPE_BULK,
                }:
                    customer_id = stop.get("customer_id")
                    if customer_id:
                        customer = CustomerCreation.objects.filter(unique_id=customer_id, is_deleted=False).first()
                        if not customer:
                            raise serializers.ValidationError({"collection_points": "Invalid customer."})
                        if (
                            collection_type == TripPlanCollectionPoint.COLLECTION_TYPE_BULK
                            and not customer.is_bulkwaste_generator
                        ):
                            raise serializers.ValidationError({"collection_points": "Bulk waste stops require a bulk-waste customer."})
                        if (
                            collection_type == TripPlanCollectionPoint.COLLECTION_TYPE_HOUSEHOLD
                            and customer.is_bulkwaste_generator
                        ):
                            raise serializers.ValidationError({"collection_points": "Household stops require a non-bulk customer."})
                        if getattr(customer, f"{trip_hierarchy_field}_id", None) != getattr(trip_hierarchy_obj, "unique_id", None):
                            raise serializers.ValidationError({"collection_points": "Customer does not belong to the selected hierarchy level."})
                    continue

                if not stop.get("collection_point_id"):
                    raise serializers.ValidationError({"collection_points": "Collection point is required for secondary collection."})
                if not stop.get("bin_id"):
                    raise serializers.ValidationError({"collection_points": "Bin is required for secondary collection."})
                cp = Collection_point.objects.filter(unique_id=stop["collection_point_id"], is_deleted=False).first()
                bin_obj = Bins.objects.filter(unique_id=stop["bin_id"], is_deleted=False).first()
                if not cp:
                    raise serializers.ValidationError({"collection_points": "Invalid collection point."})
                if getattr(cp, f"{trip_hierarchy_field}_id", None) != getattr(trip_hierarchy_obj, "unique_id", None):
                    raise serializers.ValidationError({"collection_points": "Collection point does not belong to the selected hierarchy level."})
                if wards and not cp.wards.filter(unique_id__in=[ward.unique_id for ward in wards]).exists():
                    raise serializers.ValidationError({"collection_points": "Collection point does not serve any selected ward."})
                if not bin_obj or bin_obj.collection_point_id != cp.unique_id:
                    raise serializers.ValidationError({"collection_points": "Selected bin does not belong to the collection point."})
                reserved_bins = TripPlanCollectionPoint.objects.filter(
                    bin_id=bin_obj.unique_id,
                    trip_plan_id__in=TripPlan.objects.filter(is_deleted=False).values("unique_id"),
                )
                if instance:
                    reserved_bins = reserved_bins.exclude(trip_plan_id=instance.unique_id)
                if reserved_bins.exists():
                    raise serializers.ValidationError(
                        {"collection_points": "This bin is already assigned to another Trip Plan."}
                    )

        # Wards / waste types are stored as plain unique_id lists (no M2M).
        if "wards" in attrs:
            attrs["ward_ids"] = [ward.unique_id for ward in attrs.pop("wards")]
        if "waste_types" in attrs:
            attrs["waste_type_ids"] = [wt.unique_id for wt in attrs.pop("waste_types")]

        return attrs

    def _sync_stops(self, trip_plan, stops):
        if stops is None:
            return
        # Full replace: remove existing stops, then rebuild from the payload.
        # Hard-delete (not soft) because the unique (trip_plan_id, sequence)
        # constraint ignores is_deleted — soft-deleted rows would keep their
        # sequence numbers and collide with the freshly created stops. Nothing
        # FKs to TripPlanCollectionPoint (daily-trip children are cloned to their
        # own tables at assignment time), so deleting the master rows is safe.
        TripPlanCollectionPoint.objects.filter(trip_plan_id=trip_plan.unique_id).delete()
        for stop in stops:
            collection_type = stop.get("collection_type") or trip_plan.collection_type
            if collection_type in {
                TripPlanCollectionPoint.COLLECTION_TYPE_HOUSEHOLD,
                TripPlanCollectionPoint.COLLECTION_TYPE_BULK,
            }:
                customer_id = stop.get("customer_id")
                TripPlanCollectionPoint.objects.create(
                    trip_plan_id=trip_plan.unique_id,
                    collection_type=collection_type,
                    customer_id=CustomerCreation.objects.get(unique_id=customer_id).unique_id if customer_id else None,
                    sequence=stop["sequence"],
                    is_active=stop.get("is_active", True),
                )
            else:
                TripPlanCollectionPoint.objects.create(
                    trip_plan_id=trip_plan.unique_id,
                    collection_type=collection_type,
                    collection_point_id=Collection_point.objects.get(unique_id=stop["collection_point_id"]).unique_id,
                    bin_id=Bins.objects.get(unique_id=stop["bin_id"]).unique_id,
                    sequence=stop["sequence"],
                    is_active=stop.get("is_active", True),
                )

    def create(self, validated_data):
        stops = validated_data.pop("collection_points", None)
        trip_plan = super().create(validated_data)
        self._sync_stops(trip_plan, stops)
        return trip_plan

    def update(self, instance, validated_data):
        stops = validated_data.pop("collection_points", None)
        trip_plan = super().update(instance, validated_data)
        self._sync_stops(trip_plan, stops)

        # A Trip Plan can be edited after its Daily Trip Assignment was
        # generated. Keep existing assignments in sync so newly added bin
        # stops (including another bin at the same collection point) appear
        # immediately in that day's trip instead of requiring a duplicate
        # assignment to be created.
        if stops is not None:
            from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
            from app.signals.trip_plan_signals import sync_daily_assignment_stops_from_plan

            assignments = DailyTripAssignment.objects.filter(
                trip_plan_id=trip_plan.unique_id,
                is_deleted=False,
            ).exclude(status=DailyTripAssignment.STATUS_CANCELLED)
            for assignment in assignments:
                sync_daily_assignment_stops_from_plan(assignment)
        return trip_plan
