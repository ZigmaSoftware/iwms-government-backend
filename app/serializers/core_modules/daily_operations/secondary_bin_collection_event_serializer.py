from rest_framework import serializers

from app.models.masters.waste_masters.bins import Bins
from app.models.core_modules.daily_operations.secondary_bin_collection_event import BinCollectionEvent
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.models.superadmin.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.serializers.masters.waste_masters.bins_serializer import BinsSerializer
from app.serializers.masters.transport_masters.vehicleCreation_serializer import (
    VehicleCreationSerializer,
)
from app.serializers.core_modules.schedule_setup.alternative_staff_template_serializer import (
    AlternativeStaffTemplateSerializer,
)
from app.serializers.core_modules.schedule_setup.staff_template_serializer import StaffTemplateSerializer
from app.serializers.masters.waste_masters.wastetype_serializer import (
    WasteTypeSerializer,
)
from app.utils.hierarchy import flat_geo_display
from app.utils import ref_cache


class BinCollectionEventSerializer(serializers.ModelSerializer):
    # Plain unique_id references (no DB relation); resolved in validate().
    ward_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    ward_name = serializers.SerializerMethodField()
    trip_assignment_id = serializers.CharField(required=False, allow_null=True)
    trip_collection_point_id = serializers.CharField()
    bin_id = serializers.CharField(required=False, allow_null=True)
    collection_point_id = serializers.CharField(read_only=True)
    vehicle_breakdown_id = serializers.CharField(read_only=True)

    def get_ward_name(self, obj):
        return getattr(obj.ward, "ward_name", None)

    # Geo scope — writable. Explicit selections from the form are persisted;
    # when left blank the model's save() inherits them from the trip assignment.
    # Plain unique_id strings in, display names out (see WardSerializer).
    state_id = serializers.CharField(required=False, allow_null=True)
    district_id = serializers.CharField(required=False, allow_null=True)
    area_type_id = serializers.CharField(required=False, allow_null=True)
    corporation_id = serializers.CharField(required=False, allow_null=True)
    municipality_id = serializers.CharField(required=False, allow_null=True)
    town_panchayat_id = serializers.CharField(required=False, allow_null=True)
    panchayat_union_id = serializers.CharField(required=False, allow_null=True)
    panchayat_id = serializers.CharField(required=False, allow_null=True)

    # Read-only display names so the edit form can label its geo selects
    # immediately from the record, without waiting for the master lists.
    state_name = serializers.SerializerMethodField()
    district_name = serializers.SerializerMethodField()
    area_type_name = serializers.SerializerMethodField()
    corporation_name = serializers.SerializerMethodField()
    municipality_name = serializers.SerializerMethodField()
    town_panchayat_name = serializers.SerializerMethodField()
    panchayat_union_name = serializers.SerializerMethodField()

    def get_state_name(self, obj):
        return getattr(ref_cache.get(State, obj.state_id, "unique_id"), "name", None)

    def get_district_name(self, obj):
        return getattr(ref_cache.get(District, obj.district_id, "unique_id"), "name", None)

    def get_area_type_name(self, obj):
        return getattr(ref_cache.get(AreaType, obj.area_type_id, "unique_id"), "name", None)

    def get_corporation_name(self, obj):
        return getattr(ref_cache.get(Corporation, obj.corporation_id, "unique_id"), "corporation_name", None)

    def get_municipality_name(self, obj):
        return getattr(ref_cache.get(Municipality, obj.municipality_id, "unique_id"), "municipality_name", None)

    def get_town_panchayat_name(self, obj):
        return getattr(ref_cache.get(TownPanchayat, obj.town_panchayat_id, "unique_id"), "town_panchayat_name", None)

    def get_panchayat_union_name(self, obj):
        return getattr(ref_cache.get(PanchayatUnion, obj.panchayat_union_id, "unique_id"), "union_name", None)

    bin = serializers.SerializerMethodField()
    waste_type = serializers.SerializerMethodField()
    trip_plan = serializers.SerializerMethodField()
    vehicle = serializers.SerializerMethodField()
    staff_template = serializers.SerializerMethodField()
    alternative_staff_template = serializers.SerializerMethodField()
    effective_staff_template = serializers.SerializerMethodField()
    from_date = serializers.SerializerMethodField()
    to_date = serializers.SerializerMethodField()
    extra_operator_id = serializers.SerializerMethodField()
    change_reason = serializers.SerializerMethodField()
    approved_by = serializers.SerializerMethodField()
    approval_status = serializers.SerializerMethodField()
    display_code = serializers.SerializerMethodField()
    panchayat_name = serializers.SerializerMethodField()
    # Most-specific local body (corporation/municipality/.../panchayat) + its level
    location_name = serializers.SerializerMethodField(read_only=True)
    location_level = serializers.SerializerMethodField(read_only=True)
    collection_point = serializers.SerializerMethodField()
    breakdown_info = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = BinCollectionEvent
        fields = [
            "unique_id",
            "trip_assignment_id",
            "trip_collection_point_id",
            "collection_point_id",
            "bin_id",
            "state_id",
            "district_id",
            "area_type_id",
            "corporation_id",
            "municipality_id",
            "town_panchayat_id",
            "panchayat_union_id",
            "panchayat_id",
            "ward_id",
            "ward_name",
            "state_name",
            "district_name",
            "area_type_name",
            "corporation_name",
            "municipality_name",
            "town_panchayat_name",
            "panchayat_union_name",
            "bin",
            "waste_type",
            "trip_plan",
            "vehicle",
            "staff_template",
            "alternative_staff_template",
            "effective_staff_template",
            "from_date",
            "to_date",
            "extra_operator_id",
            "change_reason",
            "approved_by",
            "approval_status",
            "display_code",
            "collection_date",
            "collected_weight_kg",
            "status",
            "status_reason",
            "driver_latitude",
            "driver_longitude",
            "notes",
            "panchayat_name",
            "location_name",
            "location_level",
            "collection_point",
            "vehicle_breakdown_id",
            "breakdown_info",
            "created_by",
            "updated_by",
            "is_active",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "unique_id",
            "collection_point_id",
            "vehicle_breakdown_id",
            "breakdown_info",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        def resolve(model, key, active=True):
            value = attrs.get(key, getattr(self.instance, key, None))
            if not value:
                return None
            qs = model.objects.filter(unique_id=value)
            if active:
                qs = qs.filter(is_deleted=False)
            obj = qs.first()
            if obj is None:
                raise serializers.ValidationError({key: f"Object with unique_id={value} does not exist."})
            return obj

        trip_cp = resolve(DailyTripCollectionPoint, "trip_collection_point_id")
        assignment = resolve(DailyTripAssignment, "trip_assignment_id")
        bin_obj = resolve(Bins, "bin_id")

        if trip_cp:
            assignment = trip_cp.trip_assignment
            bin_obj = trip_cp.bin
            attrs["collection_point_id"] = trip_cp.collection_point_id

        if not assignment:
            raise serializers.ValidationError(
                {"trip_assignment_id": "trip_assignment_id is required."}
            )
        if not bin_obj:
            raise serializers.ValidationError({"bin_id": "bin_id is required."})
        status = attrs.get(
            "status",
            getattr(self.instance, "status", BinCollectionEvent.STATUS_COLLECTED),
        )
        if status == BinCollectionEvent.STATUS_COLLECTED and attrs.get("collected_weight_kg", getattr(self.instance, "collected_weight_kg", None)) in (None, ""):
            raise serializers.ValidationError({"collected_weight_kg": "Collected weight is required when status is Collected."})
        if status in {BinCollectionEvent.STATUS_NOT_COLLECTED, BinCollectionEvent.STATUS_COLLECT_LATER}:
            attrs["collected_weight_kg"] = None

        if trip_cp and trip_cp.trip_assignment_id != getattr(assignment, "unique_id", None):
            raise serializers.ValidationError(
                "Trip collection point does not belong to the selected assignment."
            )

        collection_point = trip_cp.collection_point if trip_cp else None
        attrs["collection_date"] = (
            attrs.get("collection_date")
            or getattr(assignment, "trip_date", None)
        )
        ward_id = attrs.get("ward_id", getattr(self.instance, "ward_id", None)) or None
        if not ward_id and assignment and len(assignment.ward_ids or []) == 1:
            ward_id = assignment.ward_ids[0]
        if ward_id and not Ward.objects.filter(unique_id=ward_id, is_deleted=False).exists():
            raise serializers.ValidationError({"ward_id": f"Object with unique_id={ward_id} does not exist."})
        if ward_id and assignment and ward_id not in (assignment.ward_ids or []):
            raise serializers.ValidationError({"ward_id": "Ward must belong to the selected trip assignment."})
        if ward_id and collection_point and ward_id not in (collection_point.ward_ids or []):
            raise serializers.ValidationError({"ward_id": "Ward is not served by the selected collection point."})
        attrs["ward_id"] = ward_id

        # Store plain unique_ids (no DB relations).
        attrs["trip_assignment_id"] = assignment.unique_id
        attrs["trip_collection_point_id"] = getattr(trip_cp, "unique_id", None)
        attrs["bin_id"] = bin_obj.unique_id

        # These are intentionally not serializer fields. They are derived only
        # to satisfy the current model while the API exposes nested objects.
        attrs["waste_type_id"] = bin_obj.wastetype_id
        attrs["vehicle_id"] = getattr(self._resolve_vehicle(assignment), "unique_id", None)
        attrs["vehicle_breakdown_id"] = getattr(
            self._resolve_approved_breakdown(assignment), "unique_id", None
        )

        return attrs

    def _resolve_approved_breakdown(self, assignment):
        from app.models.core_modules.daily_operations.vehicle_breakdown import VehicleBreakdown

        try:
            breakdown = assignment.vehicle_breakdown
        except Exception:
            return None
        if breakdown is None or breakdown.approval_status != VehicleBreakdown.APPROVAL_APPROVED:
            return None
        return breakdown

    def _resolve_vehicle(self, assignment):
        return getattr(assignment, "vehicle", None) or getattr(
            getattr(assignment, "trip_plan", None),
            "vehicle",
            None,
        )

    def _resolve_effective_staff_template(self, assignment):
        return getattr(assignment, "alt_staff_template", None) or getattr(assignment, "staff_template",
            None,
        )

    def _resolve_alternative_staff_template(self, obj):
        return getattr(obj.trip_assignment, "alt_staff_template", None)

    def get_bin(self, obj):
        if not obj.bin:
            return None
        return BinsSerializer(obj.bin, context=self.context).data

    def get_waste_type(self, obj):
        waste_type = getattr(obj.bin, "wastetype", None)
        if not waste_type:
            return None
        return WasteTypeSerializer(waste_type, context=self.context).data

    def get_trip_plan(self, obj):
        trip_plan = getattr(obj.trip_assignment, "trip_plan", None)
        if not trip_plan:
            return None
        return {
            "unique_id": trip_plan.unique_id,
            "display_code": trip_plan.display_code,
        }

    def get_vehicle(self, obj):
        vehicle = self._resolve_vehicle(obj.trip_assignment)
        if not vehicle:
            return None
        return VehicleCreationSerializer(vehicle, context=self.context).data

    def get_staff_template(self, obj):
        staff_template = getattr(obj.trip_assignment, "staff_template", None)
        if not staff_template:
            return None
        return StaffTemplateSerializer(staff_template, context=self.context).data

    def get_alternative_staff_template(self, obj):
        alt_template = self._resolve_alternative_staff_template(obj)
        if not alt_template:
            return None
        return AlternativeStaffTemplateSerializer(
            alt_template,
            context=self.context,
        ).data

    def get_effective_staff_template(self, obj):
        assignment = obj.trip_assignment
        staff_template = self._resolve_effective_staff_template(assignment)
        if not staff_template:
            return None

        if getattr(assignment, "alt_staff_template", None):
            return AlternativeStaffTemplateSerializer(
                staff_template,
                context=self.context,
            ).data

        return StaffTemplateSerializer(staff_template, context=self.context).data

    def get_from_date(self, obj):
        alt_template = self._resolve_alternative_staff_template(obj)
        return alt_template.from_date if alt_template else None

    def get_to_date(self, obj):
        alt_template = self._resolve_alternative_staff_template(obj)
        return alt_template.to_date if alt_template else None

    def get_extra_operator_id(self, obj):
        alt_template = self._resolve_alternative_staff_template(obj)
        return getattr(alt_template, "extra_operator_id", None) or []

    def get_change_reason(self, obj):
        alt_template = self._resolve_alternative_staff_template(obj)
        return getattr(alt_template, "change_reason", None) if alt_template else None

    def get_approved_by(self, obj):
        alt_template = self._resolve_alternative_staff_template(obj)
        approved_by = getattr(alt_template, "approved_by", None)
        if not approved_by:
            return None
        return {
            "unique_id": approved_by.staff_unique_id,
            "employee_name": approved_by.employee_name,
        }

    def get_approval_status(self, obj):
        alt_template = self._resolve_alternative_staff_template(obj)
        return getattr(alt_template, "approval_status", None) if alt_template else None

    def get_display_code(self, obj):
        alt_template = self._resolve_alternative_staff_template(obj)
        return getattr(alt_template, "display_code", None) if alt_template else None

    def get_panchayat_name(self, obj):
        # Prefer the event's own stored panchayat column (explicit selection),
        # then fall back to the collection point / trip assignment. All three
        # sources hold a plain panchayat unique_id string (Collection_point
        # and BinCollectionEvent are converted; DailyTripAssignment's own
        # `panchayat` FK attname `panchayat_id` also yields the raw id).
        panchayat_uid = (
            obj.panchayat_id
            or getattr(obj.collection_point, "panchayat_id", None)
            or getattr(obj.trip_assignment, "panchayat_id", None)
        )
        if not panchayat_uid:
            return None
        return Panchayat.objects.filter(unique_id=panchayat_uid).values_list(
            "panchayat_name", flat=True
        ).first()

    def get_location_name(self, obj):
        # Prefer the event's own geo; fall back to the collection point, then the trip assignment.
        name, _ = flat_geo_display(obj)
        if not name:
            name, _ = flat_geo_display(obj.collection_point)
        if not name:
            name, _ = flat_geo_display(obj.trip_assignment)
        return name

    def get_location_level(self, obj):
        _, level = flat_geo_display(obj)
        if not level:
            _, level = flat_geo_display(obj.collection_point)
        if not level:
            _, level = flat_geo_display(obj.trip_assignment)
        return level

    def get_collection_point(self, obj):
        cp = obj.collection_point
        if not cp:
            return None
        return {"unique_id": getattr(cp, "unique_id", None), "cp_name": getattr(cp, "cp_name", None)}

    def get_breakdown_info(self, obj):
        breakdown = obj.vehicle_breakdown
        if not breakdown:
            return None
        replacement_vehicle = getattr(breakdown, "replacement_vehicle", None)
        return {
            "unique_id": breakdown.unique_id,
            "status": breakdown.status,
            "approval_status": breakdown.approval_status,
            "breakdown_reason": breakdown.breakdown_reason,
            "replacement_vehicle_no": getattr(replacement_vehicle, "vehicle_no", None),
        }
