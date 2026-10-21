from app.serializers.evidence_image import absolute_image_url
from rest_framework import serializers

from app.utils.plain_ref import ref_id
from app.models.superadmin.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.masters.panchayat import Panchayat
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.ward import Ward
from app.models.core_modules.schedule_setup.alternative_staff_template import AlternativeStaffTemplate
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.masters.waste_masters.wastetype import WasteType
from app.utils.crew import CrewPresenceCache, crew_payload
from app.utils.waste_images import capture_images_for_customer
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


def _pick(ordered_rows, key, ids):
    """The rows of `ordered_rows` whose `key` is in `ids`, in the query's
    order — what a per-row `.filter(<key>__in=ids)` would have returned."""
    wanted = set(ids or [])
    return [row for row in ordered_rows if getattr(row, key) in wanted]


def _first_per(rows, key):
    """{row.<key>: first row} for rows already in the wanted order."""
    first = {}
    for row in rows:
        first.setdefault(getattr(row, key), row)
    return first


class _AssignmentPage:
    """Everything DailyTripAssignmentSerializer resolves per row, loaded for a
    whole list page in a fixed number of queries. References resolved through
    model properties are primed into ref_cache; reverse lookups are kept
    here, keyed by assignment (or trip plan) unique_id."""

    def __init__(self, assignments):
        from app.models.core_modules.daily_operations.daily_trip_collection_point import (
            DailyTripCollectionPoint,
        )
        from app.models.core_modules.daily_operations.daily_trip_household_collection import (
            DailyTripHouseholdCollection,
        )
        from app.models.core_modules.daily_operations.trip_retrip_request import TripRetripRequest
        from app.models.core_modules.daily_operations.vehicle_breakdown import VehicleBreakdown
        from app.models.core_modules.daily_operations.waste_collection import WasteCollection
        from app.models.core_modules.schedule_setup.collection_point import Collection_point
        from app.models.core_modules.schedule_setup.trip_plan_collection_point import TripPlanCollectionPoint
        from app.models.masters.customer_masters.customercreation import CustomerCreation
        from app.models.masters.waste_masters.bins import Bins
        from app.models.superadmin.staff_management.staffcreation import Staffcreation
        from app.utils.waste_type_breakdown import waste_type_breakdown_for_assignments

        ids = {a.unique_id for a in assignments}

        ref_cache.prime(TripPlan, {a.trip_plan_id for a in assignments}, "unique_id")
        plans = [p for p in (a.trip_plan for a in assignments) if p]
        plan_ids = {p.unique_id for p in plans}
        ref_cache.prime(StaffTemplate, {a.staff_template_id for a in assignments}, "unique_id")
        ref_cache.prime(AlternativeStaffTemplate, {a.alt_staff_template_id for a in assignments}, "unique_id")
        templates = [a.staff_template for a in assignments] + [a.alt_staff_template for a in assignments]
        staff_ids = set()
        for template in filter(None, templates):
            staff_ids |= {template.driver_id, template.operator_id}
        ref_cache.prime(Staffcreation, staff_ids, "staff_unique_id")
        ref_cache.prime(
            VehicleCreation,
            {a.vehicle_id for a in assignments} | {p.vehicle_id for p in plans},
            "unique_id",
        )

        # trip_count(): position among same plan + same day assignments.
        siblings = {}
        for row in DailyTripAssignment.objects.filter(
            trip_plan_id__in={a.trip_plan_id for a in assignments},
            trip_date__in={a.trip_date for a in assignments},
            is_deleted=False,
        ).order_by("created_at", "unique_id").values("unique_id", "trip_plan_id", "trip_date"):
            siblings.setdefault((row["trip_plan_id"], row["trip_date"]), []).append(row["unique_id"])
        self.trip_counts = {}
        for a in assignments:
            same_day = siblings.get((a.trip_plan_id, a.trip_date), [])
            self.trip_counts[a.unique_id] = (
                same_day.index(a.unique_id) + 1 if a.unique_id in same_day else len(same_day) + 1
            )

        self.plan_stop_types = {}
        for plan_id, collection_type in TripPlanCollectionPoint.objects.filter(
            trip_plan_id__in=plan_ids, is_deleted=False
        ).values_list("trip_plan_id", "collection_type"):
            self.plan_stop_types.setdefault(plan_id, []).append(collection_type)

        all_waste_types = list(WasteType.objects.filter(unique_id__in={
            i
            for row in [*assignments, *plans]
            for i in (row.waste_type_ids or [])
        } | {i for a in assignments for i in (a.household_waste_type_ids or [])}))
        self.waste_types = {a.unique_id: _pick(all_waste_types, "unique_id", a.waste_type_ids) for a in assignments}
        self.household_waste_types = {
            a.unique_id: _pick(all_waste_types, "unique_id", a.household_waste_type_ids) for a in assignments
        }
        self.plan_waste_types = {p.unique_id: _pick(all_waste_types, "unique_id", p.waste_type_ids) for p in plans}

        self.breakdown = waste_type_breakdown_for_assignments(ids)

        self.collection_points = {}
        for stop in DailyTripCollectionPoint.objects.filter(
            trip_assignment_id__in=ids, is_deleted=False
        ).order_by("trip_assignment_id", "sequence"):
            self.collection_points.setdefault(stop.trip_assignment_id, []).append(stop)
        stops = [stop for rows in self.collection_points.values() for stop in rows]
        ref_cache.prime(Collection_point, {s.collection_point_id for s in stops}, "unique_id")
        ref_cache.prime(Bins, {s.bin_id for s in stops}, "unique_id")
        cps = [cp for cp in (s.collection_point for s in stops) if cp]

        self.households = {}
        for stop in DailyTripHouseholdCollection.objects.filter(
            trip_assignment_id__in=ids, is_deleted=False
        ).order_by("trip_assignment_id", "sequence"):
            self.households.setdefault(stop.trip_assignment_id, []).append(stop)
        households = [stop for rows in self.households.values() for stop in rows]
        ref_cache.prime(CustomerCreation, {s.customer_id for s in households}, "unique_id")
        ref_cache.prime(WasteCollection, {s.waste_collection_id for s in households}, "unique_id")
        customers = [c for c in (s.customer for s in households) if c]
        ref_cache.prime(Ward, {c.ward_id for c in customers}, "unique_id")

        all_wards = list(Ward.objects.filter(unique_id__in={
            i for row in [*assignments, *cps] for i in (row.ward_ids or [])
        }))
        self.wards = {a.unique_id: _pick(all_wards, "unique_id", a.ward_ids) for a in assignments}
        self.cp_wards = {cp.unique_id: _pick(all_wards, "unique_id", cp.ward_ids) for cp in cps}

        # `.first()` per assignment, in the same order each would have used.
        self.vehicle_breakdowns = _first_per(
            VehicleBreakdown.objects.filter(trip_assignment_id__in=ids), "trip_assignment_id"
        )
        self.retrips = _first_per(
            TripRetripRequest.objects.filter(assignment_id__in=ids, is_deleted=False).order_by("-created_at"),
            "assignment_id",
        )


class DailyTripAssignmentListSerializer(serializers.ListSerializer):
    def to_representation(self, data):
        assignments = list(data.all() if hasattr(data, "all") else data)
        self.child._page = _AssignmentPage(assignments)
        try:
            return super().to_representation(assignments)
        finally:
            self.child._page = None


class DailyTripAssignmentSerializer(serializers.ModelSerializer):
    # Plain unique_id references (no DB relation); checked in validate_*.
    trip_plan_id = serializers.CharField()
    staff_template_id = serializers.CharField(write_only=True, required=False, allow_null=True)
    state_id = serializers.CharField(required=False, allow_null=True)
    district_id = serializers.CharField(required=False, allow_null=True)
    area_type_id = serializers.CharField(required=False, allow_null=True)
    corporation_id = serializers.CharField(required=False, allow_null=True)
    municipality_id = serializers.CharField(required=False, allow_null=True)
    town_panchayat_id = serializers.CharField(required=False, allow_null=True)
    panchayat_union_id = serializers.CharField(required=False, allow_null=True)
    panchayat_id = serializers.CharField(required=False, allow_null=True)
    waste_type_ids = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=WasteType.objects.filter(is_deleted=False),
        many=True,
        required=False,
        source="waste_types",
        write_only=True,
    )
    waste_types_detail = serializers.SerializerMethodField(read_only=True)
    waste_type_breakdown = serializers.SerializerMethodField(read_only=True)
    household_waste_type_ids = serializers.SlugRelatedField(slug_field="unique_id", queryset=WasteType.objects.filter(is_deleted=False), many=True, required=False, source="household_waste_types")
    household_waste_types = serializers.SerializerMethodField(read_only=True)
    ward_ids = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=Ward.objects.filter(is_deleted=False),
        many=True,
        required=False,
        source="wards",
        write_only=True,
    )
    wards_detail = serializers.SerializerMethodField(read_only=True)
    vehicle_id = serializers.CharField(write_only=True, required=False, allow_null=True)
    alt_staff_template_id = serializers.CharField(write_only=True, required=False, allow_null=True)

    def validate_trip_plan_id(self, value):
        if not TripPlan.objects.filter(unique_id=value, is_deleted=False, status="ACTIVE").exists():
            raise serializers.ValidationError(f"Object with unique_id={value} does not exist.")
        return value

    def validate_staff_template_id(self, value):
        if value and not StaffTemplate.objects.filter(unique_id=value, is_deleted=False).exists():
            raise serializers.ValidationError(f"Object with unique_id={value} does not exist.")
        return value or None

    def validate_vehicle_id(self, value):
        if value and not VehicleCreation.objects.filter(unique_id=value, is_deleted=False).exists():
            raise serializers.ValidationError(f"Object with unique_id={value} does not exist.")
        return value or None

    def validate_alt_staff_template_id(self, value):
        if value and not AlternativeStaffTemplate.objects.filter(unique_id=value).exists():
            raise serializers.ValidationError(f"Object with unique_id={value} does not exist.")
        return value or None

    collection_points_input = serializers.ListField(child=serializers.DictField(), write_only=True, required=False)

    trip_plan = serializers.SerializerMethodField(read_only=True)
    staff_template = serializers.SerializerMethodField(read_only=True)
    effective_staff = serializers.SerializerMethodField(read_only=True)
    collection_points = serializers.SerializerMethodField(read_only=True)
    household_collection_points = serializers.SerializerMethodField(read_only=True)
    service_notice = serializers.SerializerMethodField(read_only=True)
    trip_events = serializers.SerializerMethodField(read_only=True)
    trip_log_summary = serializers.SerializerMethodField(read_only=True)
    actual_start_at = serializers.DateTimeField(read_only=True)
    actual_end_at = serializers.DateTimeField(read_only=True)
    breakdown_info = serializers.SerializerMethodField(read_only=True)
    # A vehicle breakdown and a Re-Trip are unrelated events — a breakdown
    # swaps the vehicle/crew mid-trip, a Re-Trip closes the trip early and
    # carries leftover stops to a continuation — so this is deliberately its
    # own field/column, not folded into breakdown_info.
    retrip_info = serializers.SerializerMethodField(read_only=True)
    state = serializers.SerializerMethodField(read_only=True)
    district = serializers.SerializerMethodField(read_only=True)
    area_type = serializers.SerializerMethodField(read_only=True)
    corporation = serializers.SerializerMethodField(read_only=True)
    municipality = serializers.SerializerMethodField(read_only=True)
    town_panchayat = serializers.SerializerMethodField(read_only=True)
    panchayat_union = serializers.SerializerMethodField(read_only=True)
    panchayat = serializers.SerializerMethodField(read_only=True)
    vehicle = serializers.SerializerMethodField(read_only=True)
    collection_types = serializers.SerializerMethodField(read_only=True)
    # Driver + operator (+ extras) with photo and today's attendance, so the
    # supervisor Teams/Trips screens can show stacked crew avatars and presence
    # without a second request. Same shape/source as the mobile "Your crew".
    crew = serializers.SerializerMethodField(read_only=True)

    # Total time on the trip (actual_start_at -> actual_end_at, or -> now while
    # In Progress), in whole seconds — the client formats it however it needs
    # (web table cell vs. app card). Null until the trip has been started.
    total_trip_time_seconds = serializers.SerializerMethodField(read_only=True)
    # This assignment's 1-based position among today's assignments for the
    # same trip plan: 1 for the ordinary run, 2+ for a Re-Trip continuation
    # (and any further same-day re-trips of that continuation).
    trip_count = serializers.SerializerMethodField(read_only=True)

    # Set by DailyTripAssignmentListSerializer while it renders a list page.
    _page = None

    class Meta:
        model = DailyTripAssignment
        list_serializer_class = DailyTripAssignmentListSerializer
        fields = [
            "unique_id", "trip_plan_id", "staff_template_id", "state_id", "district_id", "area_type_id", "corporation_id",
            "municipality_id", "town_panchayat_id", "panchayat_union_id", "panchayat_id",
            "waste_type_ids", "waste_types_detail", "waste_type_breakdown",
            "ward_ids", "wards_detail",
            "household_waste_type_ids", "household_waste_types",
            "vehicle_id", "alt_staff_template_id", "collection_points_input", "trip_plan", "staff_template",
            "effective_staff", "crew", "state", "district", "area_type", "corporation", "municipality",
            "town_panchayat", "panchayat_union", "panchayat", "vehicle", "collection_types",
            "collection_points", "household_collection_points", "breakdown_info", "retrip_info",
            "trip_date", "scheduled_time", "actual_start_time", "actual_end_time",
            "total_trip_time_seconds", "trip_count", "service_notice", "trip_events", "trip_log_summary", "actual_start_at", "actual_end_at",
            "status", "approval_status", "remarks", "created_at", "updated_at",
        ]
        read_only_fields = ["unique_id", "actual_start_time", "actual_end_time", "approval_status", "created_at", "updated_at"]

    def get_service_notice(self, obj):
        from app.services.daily_service_notice import (
            active_notice_for_plan,
            serialize_notice,
        )

        return serialize_notice(
            active_notice_for_plan(obj.trip_plan_id, obj.trip_date)
        )

    def get_trip_events(self, obj):
        from app.models.core_modules.daily_operations.trip_delay_report import TripDelayReport
        from app.models.core_modules.daily_operations.trip_retrip_request import TripRetripRequest

        events = []
        for report in TripDelayReport.objects.filter(
            trip_assignment_id=obj.unique_id, is_deleted=False
        ):
            # unique_id + image let the supervisor app open this exact
            # report (photo, acknowledge/resolve) from the trip card alerts.
            events.append({"label": "Delay: " + report.get_delay_reason_display(),
                           "detail": report.delay_remarks, "at": report.created_at,
                           "status": report.status, "kind": "delay",
                           "unique_id": report.unique_id,
                           "image": absolute_image_url(self, report.evidence_image)})
        for request in TripRetripRequest.objects.filter(assignment_id=obj.unique_id):
            if request.is_deleted:
                continue
            events.append({"label": "Re-Trip requested", "detail": request.reason,
                           "at": request.created_at, "status": request.status,
                           "actor": getattr(request.requested_by, "employee_name", None)})
            if request.reviewed_at:
                events.append({"label": "Re-Trip " + request.status.lower(),
                               "detail": request.review_remarks, "at": request.reviewed_at,
                               "actor": getattr(request.reviewed_by, "employee_name", None),
                               "related_trip_id": request.new_assignment_id})
        for source in TripRetripRequest.objects.filter(new_assignment_id=obj.unique_id):
            if not source.is_deleted:
                events.append({"label": "Continuation of " + str(source.assignment_id),
                               "detail": source.review_remarks, "at": source.reviewed_at,
                               "related_trip_id": source.assignment_id})
        return sorted(events, key=lambda event: str(event.get("at") or ""))

    def get_trip_log_summary(self, obj):
        from app.models.core_modules.daily_operations.daily_trip_log import DailyTripLog

        log = DailyTripLog.objects.filter(
            trip_assignment_id=obj.unique_id, is_deleted=False,
        ).first()
        if not log:
            return None
        return {
            "unique_id": log.unique_id,
            "status": log.log_status,
            "verified_at": log.verified_at,
            "verified_by": str(log.verified_by) if log.verified_by else None,
            "bin_weight_kg": log.collected_weight_kg,
            "customer_weight_kg": log.household_collected_weight_kg,
            "driver": getattr(log.driver, "employee_name", None),
            "operator": getattr(log.operator, "employee_name", None),
            "vehicle_no": getattr(log.vehicle, "vehicle_no", None),
            "remarks": log.remarks,
        }

    def get_total_trip_time_seconds(self, obj):
        duration = obj.total_trip_time
        return int(duration.total_seconds()) if duration is not None else None

    def get_trip_count(self, obj):
        if self._page:
            return self._page.trip_counts[obj.unique_id]
        return obj.trip_count()

    def get_trip_plan(self, obj):
        from app.models.core_modules.schedule_setup.trip_plan_collection_point import TripPlanCollectionPoint
        plan = obj.trip_plan
        if not plan:
            return None
        if self._page:
            stop_types = self._page.plan_stop_types.get(plan.unique_id, [])
            plan_waste_types = self._page.plan_waste_types[plan.unique_id]
        else:
            stop_types = list(plan.plan_collection_points.filter(is_deleted=False).values_list("collection_type", flat=True))
            plan_waste_types = plan.waste_types.all()
        return {
            "unique_id": plan.unique_id,
            "display_code": plan.display_code,
            "scheduled_time": plan.scheduled_time,
            "district": self._geo_ref(plan.district_id, "district"),
            "panchayat": self._panchayat_payload(plan.panchayat_id),
            "vehicle_no": getattr(getattr(plan, "vehicle", None), "vehicle_no", None),
            "waste_type_names": [wt.waste_type_name for wt in plan_waste_types],
            "has_bin": TripPlanCollectionPoint.COLLECTION_TYPE_BIN in stop_types,
            "has_household": TripPlanCollectionPoint.COLLECTION_TYPE_HOUSEHOLD in stop_types,
            "has_bulk": TripPlanCollectionPoint.COLLECTION_TYPE_BULK in stop_types,
        }

    def get_staff_template(self, obj):
        st = obj.staff_template
        if not st:
            return None
        return {"unique_id": st.unique_id, "display_code": st.display_code, "driver": getattr(getattr(st, "driver", None), "employee_name", None), "operator": getattr(getattr(st, "operator", None), "employee_name", None)}

    def get_effective_staff(self, obj):
        alt = obj.alt_staff_template
        if alt:
            return {"source": "alternative", "unique_id": alt.unique_id, "display_code": alt.display_code, "driver": getattr(getattr(alt, "driver", None), "employee_name", None), "operator": getattr(getattr(alt, "operator", None), "employee_name", None), "from_date": str(alt.from_date), "to_date": str(alt.to_date)}
        return self.get_staff_template(obj)

    def get_crew(self, obj):
        presence_cache = getattr(self, "_presence_cache", None)
        if presence_cache is None:
            presence_cache = CrewPresenceCache()
            self._presence_cache = presence_cache
        return crew_payload(
            obj.staff_template,
            obj.alt_staff_template,
            obj.trip_date,
            request=self.context.get("request"),
            presence_cache=presence_cache,
        )

    def get_panchayat(self, obj):
        return self._panchayat_payload(obj.panchayat_id)

    def get_state(self, obj):
        return self._geo_ref(obj.state_id, "state")

    def get_district(self, obj):
        return self._geo_ref(obj.district_id, "district")

    def get_area_type(self, obj):
        return self._geo_ref(obj.area_type_id, "area_type")

    def get_corporation(self, obj):
        return self._geo_ref(obj.corporation_id, "corporation")

    def get_municipality(self, obj):
        return self._geo_ref(obj.municipality_id, "municipality")

    def get_town_panchayat(self, obj):
        return self._geo_ref(obj.town_panchayat_id, "town_panchayat")

    def get_panchayat_union(self, obj):
        return self._geo_ref(obj.panchayat_union_id, "panchayat_union")

    def _geo_ref(self, value, field):
        # These fields are now plain unique_id strings (no DB relation), so
        # the display ref is resolved with a lookup instead of attribute-
        # chaining a live related object.
        if not value:
            return None
        model, label_attr = _GEO_LOOKUP_MODELS[field]
        name = getattr(ref_cache.get(model, value, "unique_id"), label_attr, None)
        return {"unique_id": value, label_attr: name}

    def _panchayat_payload(self, panchayat_id):
        if not panchayat_id:
            return None
        name = getattr(ref_cache.get(Panchayat, panchayat_id, "unique_id"), "panchayat_name", None)
        return {"unique_id": panchayat_id, "panchayat_name": name}

    def get_vehicle(self, obj):
        vehicle = obj.vehicle
        if not vehicle:
            return None
        return {"unique_id": vehicle.unique_id, "vehicle_no": vehicle.vehicle_no}

    def get_household_waste_types(self, obj):
        waste_types = self._page.household_waste_types[obj.unique_id] if self._page else obj.household_waste_types
        return [{"unique_id": wt.unique_id, "waste_type_name": getattr(wt, "waste_type_name", None)} for wt in waste_types]

    def get_waste_types_detail(self, obj):
        waste_types = self._page.waste_types[obj.unique_id] if self._page else obj.waste_types.all()
        return [{"unique_id": wt.unique_id, "waste_type_name": wt.waste_type_name} for wt in waste_types]

    def get_wards_detail(self, obj):
        wards = self._page.wards[obj.unique_id] if self._page else obj.wards.all()
        return [{"unique_id": ward.unique_id, "ward_name": ward.ward_name} for ward in wards]

    def get_waste_type_breakdown(self, obj):
        from app.utils.waste_type_breakdown import waste_type_breakdown_for_assignment
        if self._page:
            return self._page.breakdown.get(obj.unique_id, [])
        return waste_type_breakdown_for_assignment(obj)

    def get_collection_types(self, obj):
        from app.models.core_modules.schedule_setup.trip_plan_collection_point import TripPlanCollectionPoint
        plan = obj.trip_plan
        if not plan:
            return {"has_bin": False, "has_household": False, "has_bulk": False}
        if self._page:
            stops = self._page.plan_stop_types.get(plan.unique_id, [])
        else:
            stops = plan.plan_collection_points.filter(is_deleted=False).values_list("collection_type", flat=True)
        return {
            "has_bin": TripPlanCollectionPoint.COLLECTION_TYPE_BIN in stops,
            "has_household": TripPlanCollectionPoint.COLLECTION_TYPE_HOUSEHOLD in stops,
            "has_bulk": TripPlanCollectionPoint.COLLECTION_TYPE_BULK in stops,
        }

    def _cp_wards(self, cp):
        return self._page.cp_wards[cp.unique_id] if self._page else cp.wards.all()

    def get_collection_points(self, obj):
        if self._page:
            stops = self._page.collection_points.get(obj.unique_id, [])
        else:
            stops = obj.trip_collection_points.filter(is_deleted=False).order_by("sequence")
        return [{
            "unique_id": stop.unique_id,
            "collection_point_id": stop.collection_point_id,
            "collection_point": {
                "unique_id": stop.collection_point.unique_id,
                "cp_name": stop.collection_point.cp_name,
                "latitude": stop.collection_point.latitude,
                "longitude": stop.collection_point.longitude,
            } if stop.collection_point else None,
            "wards": [{"unique_id": ward.unique_id, "ward_name": ward.ward_name} for ward in self._cp_wards(stop.collection_point)] if stop.collection_point else [],
            "bin_id": stop.bin_id,
            "bin": {
                "unique_id": stop.bin.unique_id,
                "bin_name": stop.bin.bin_name,
                "bin_qr": stop.bin.bin_qr.url if getattr(stop.bin, "bin_qr", None) else None,
            } if stop.bin else None,
            "waste_type_name": getattr(getattr(stop.bin_id, "wastetype", None), "waste_type_name", None),
            "sequence": stop.sequence,
            "is_collected": stop.is_collected,
            "collected_at": stop.collected_at,
            "collected_weight_kg": stop.collected_weight_kg,
            "status": stop.status,
            "status_reason": getattr(stop, "status_reason", None),
            # Bin collection doesn't capture a proof photo yet (planned).
            "image": None,
        } for stop in stops]

    def get_household_collection_points(self, obj):
        if self._page:
            stops = self._page.households.get(obj.unique_id, [])
        else:
            stops = obj.trip_household_collections.filter(is_deleted=False).order_by("sequence")
        return [{
            "unique_id": stop.unique_id,
            "customer_id": stop.customer_id,
            "customer": {
                "unique_id": getattr(stop.customer, "unique_id", None),
                "customer_name": getattr(stop.customer, "customer_name", None),
                "building_no": getattr(stop.customer, "building_no", None),
                "street": getattr(stop.customer, "street", None),
                "ward_id": getattr(stop.customer, "ward_id", None),
                "ward_name": getattr(getattr(stop.customer, "ward", None), "ward_name", None),
                "qr_code": stop.customer.qr_code.url if getattr(stop.customer, "qr_code", None) else None,
            } if stop.customer else None,
            "collection_type": stop.collection_type,
            "sequence": stop.sequence,
            "is_collected": stop.is_collected,
            "collected_at": stop.collected_at,
            "collected_weight_kg": stop.collected_weight_kg,
            "wet_waste": getattr(stop.waste_collection, "wet_waste", None),
            "dry_waste": getattr(stop.waste_collection, "dry_waste", None),
            "mixed_waste": getattr(stop.waste_collection, "mixed_waste", None),
            "sanitary_waste": getattr(stop.waste_collection, "sanitary_waste", None),
            "customer_available_at": stop.customer_available_at,
            "customer_available_note": stop.customer_available_note,
            "status_evidence_image_url": absolute_image_url(self, stop.status_evidence_image),
            "status": stop.status,
            "status_reason": getattr(stop, "status_reason", None),
        } for stop in stops]

    def get_breakdown_info(self, obj):
        try:
            bd = self._page.vehicle_breakdowns.get(obj.unique_id) if self._page else obj.vehicle_breakdown
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
            "breakdown_vehicle_no": getattr(bd.breakdown_vehicle, "vehicle_no", None),
            "replacement_vehicle_no": getattr(bd.replacement_vehicle, "vehicle_no", None),
            "replacement_driver": getattr(bd.replacement_driver, "employee_name", None),
            "replacement_operator": getattr(bd.replacement_operator, "employee_name", None),
            "new_assignment_id": bd.new_assignment_id,
            "photos": [url for photo in bd.photos.all() if (url := absolute_image_url(self, photo.photo))],
        }

    def get_retrip_info(self, obj):
        if self._page:
            retrip = self._page.retrips.get(obj.unique_id)
        else:
            retrip = obj.retrip_requests.filter(is_deleted=False).order_by("-created_at").first()
        if not retrip:
            return None
        return {
            "unique_id": retrip.unique_id,
            "status": retrip.status,
            "reason": retrip.reason,
            "review_remarks": retrip.review_remarks,
            "new_assignment_id": retrip.new_assignment_id,
            "expires_at": retrip.expires_at,
            "pending_bin_count": retrip.pending_bin_count,
            "pending_household_count": retrip.pending_household_count,
        }

    def _sync_collection_points(self, assignment, points):
        # Update-only sync: stops are generated from the Trip Plan by signals;
        # this applies inline edits (sequence, weight, collected, status) from the form.
        if points is None:
            return
        from app.models.core_modules.daily_operations.daily_trip_collection_point import DailyTripCollectionPoint

        for item in points:
            unique_id = item.get("unique_id")
            if not unique_id:
                continue
            stop = DailyTripCollectionPoint.objects.filter(
                unique_id=unique_id,
                trip_assignment_id=ref_id(assignment),
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
        # ward_ids are stored on the row, so the post_save stop-copy signal
        # already sees the selected wards; no re-sync needed.
        return super().create(validated_data)

    def update(self, instance, validated_data):
        collection_points = validated_data.pop("collection_points_input", None)
        assignment = super().update(instance, validated_data)
        # Pull in any stops added to the Trip Plan after this daily trip was
        # created (e.g. new household stops). Additive only — existing stops and
        # their collected data are left untouched.
        from app.signals.trip_plan_signals import sync_daily_assignment_stops_from_plan
        sync_daily_assignment_stops_from_plan(assignment)
        self._sync_collection_points(assignment, collection_points)
        return assignment

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        trip_plan_uid = attrs.get("trip_plan_id", getattr(instance, "trip_plan_id", None))
        trip_plan = TripPlan.objects.filter(unique_id=trip_plan_uid).first() if trip_plan_uid else None
        trip_date = attrs.get("trip_date", getattr(instance, "trip_date", None))
        scheduled_time = attrs.get("scheduled_time", getattr(instance, "scheduled_time", None))

        geo_fields = ("state_id", "district_id", "area_type_id", "corporation_id", "municipality_id", "town_panchayat_id", "panchayat_union_id", "panchayat_id")
        if trip_plan:
            attrs.setdefault("staff_template_id", trip_plan.staff_template_id)
            attrs.setdefault("vehicle_id", trip_plan.vehicle_id)
            if "waste_types" not in attrs:
                attrs["waste_types"] = list(trip_plan.waste_types.all())
            if "wards" not in attrs:
                attrs["wards"] = list(trip_plan.wards.all())
            for field in geo_fields:
                attrs.setdefault(field, getattr(trip_plan, field, None))
            attrs.setdefault("scheduled_time", trip_plan.scheduled_time)
            scheduled_time = attrs.get("scheduled_time", scheduled_time)

        waste_types = attrs.get("waste_types", list(getattr(instance, "waste_types", None).all()) if instance else [])
        if not waste_types:
            raise serializers.ValidationError({"waste_type_ids": "At least one waste type is required."})

        if not any(attrs.get(field, getattr(instance, field, None)) for field in ("district_id", "corporation_id", "municipality_id", "town_panchayat_id", "panchayat_union_id", "panchayat_id")):
            raise serializers.ValidationError("Daily trip assignment must belong to a geographic area.")

        if trip_plan and trip_date:
            conflict_qs = DailyTripAssignment.objects.filter(
                trip_plan_id=trip_plan.unique_id,
                trip_date=trip_date,
                is_deleted=False,
            ).exclude(status=DailyTripAssignment.STATUS_CANCELLED)
            if instance:
                conflict_qs = conflict_qs.exclude(pk=instance.pk)
            if conflict_qs.exists():
                raise serializers.ValidationError("Trip plan already assigned for this date.")

        staff_template = attrs.get("staff_template_id", getattr(instance, "staff_template_id", None))
        if staff_template and trip_date and "alt_staff_template_id" not in attrs:
            attrs["alt_staff_template_id"] = (
                AlternativeStaffTemplate.objects.filter(
                    staff_template_id=ref_id(staff_template),
                    from_date__lte=trip_date,
                    to_date__gte=trip_date,
                ).values_list("unique_id", flat=True).first()
            )

        # Wards / waste types are stored as plain unique_id lists (no M2M).
        if "wards" in attrs:
            attrs["ward_ids"] = [ward.unique_id for ward in attrs.pop("wards")]
        if "waste_types" in attrs:
            attrs["waste_type_ids"] = [wt.unique_id for wt in attrs.pop("waste_types")]
        if "household_waste_types" in attrs:
            attrs["household_waste_type_ids"] = [
                wt.unique_id for wt in attrs.pop("household_waste_types")
            ]

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
