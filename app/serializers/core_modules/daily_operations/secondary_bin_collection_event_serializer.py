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
from app.serializers.superadmin.user_management.user_serializer import UniqueIdOrPkField
from app.serializers.masters.waste_masters.wastetype_serializer import (
    WasteTypeSerializer,
)
from app.utils.hierarchy import flat_geo_display


class BinCollectionEventSerializer(serializers.ModelSerializer):
    ward_id = serializers.SlugRelatedField(
        source="ward", slug_field="unique_id", queryset=Ward.objects.filter(is_deleted=False),
        required=False, allow_null=True,
    )
    ward_name = serializers.CharField(source="ward.ward_name", read_only=True, allow_null=True)
    trip_assignment_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=DailyTripAssignment.objects.filter(is_deleted=False),
    )
    trip_collection_point_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=DailyTripCollectionPoint.objects.filter(is_deleted=False),
    )
    bin_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=Bins.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )

    # Geo scope — writable. Explicit selections from the form are persisted;
    # when left blank the model's save() inherits them from the trip assignment.
    state_id = serializers.SlugRelatedField(
        source="state", slug_field="unique_id",
        queryset=State.objects.filter(is_deleted=False), required=False, allow_null=True,
    )
    district_id = serializers.SlugRelatedField(
        source="district", slug_field="unique_id",
        queryset=District.objects.filter(is_deleted=False), required=False, allow_null=True,
    )
    area_type_id = serializers.SlugRelatedField(
        source="area_type", slug_field="unique_id",
        queryset=AreaType.objects.filter(is_deleted=False), required=False, allow_null=True,
    )
    corporation_id = serializers.SlugRelatedField(
        source="corporation", slug_field="unique_id",
        queryset=Corporation.objects.filter(is_deleted=False), required=False, allow_null=True,
    )
    municipality_id = serializers.SlugRelatedField(
        source="municipality", slug_field="unique_id",
        queryset=Municipality.objects.filter(is_deleted=False), required=False, allow_null=True,
    )
    town_panchayat_id = serializers.SlugRelatedField(
        source="town_panchayat", slug_field="unique_id",
        queryset=TownPanchayat.objects.filter(is_deleted=False), required=False, allow_null=True,
    )
    panchayat_union_id = serializers.SlugRelatedField(
        source="panchayat_union", slug_field="unique_id",
        queryset=PanchayatUnion.objects.filter(is_deleted=False), required=False, allow_null=True,
    )
    panchayat_id = serializers.SlugRelatedField(
        source="panchayat", slug_field="unique_id",
        queryset=Panchayat.objects.filter(is_deleted=False), required=False, allow_null=True,
    )

    # Read-only display names so the edit form can label its geo selects
    # immediately from the record, without waiting for the master lists.
    state_name = serializers.CharField(source="state.name", read_only=True, allow_null=True)
    district_name = serializers.CharField(source="district.name", read_only=True, allow_null=True)
    area_type_name = serializers.CharField(source="area_type.name", read_only=True, allow_null=True)
    corporation_name = serializers.CharField(source="corporation.corporation_name", read_only=True, allow_null=True)
    municipality_name = serializers.CharField(source="municipality.municipality_name", read_only=True, allow_null=True)
    town_panchayat_name = serializers.CharField(source="town_panchayat.town_panchayat_name", read_only=True, allow_null=True)
    panchayat_union_name = serializers.CharField(source="panchayat_union.union_name", read_only=True, allow_null=True)

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
        trip_cp = attrs.get(
            "trip_collection_point_id",
            getattr(self.instance, "trip_collection_point_id", None),
        )
        assignment = attrs.get(
            "trip_assignment_id",
            getattr(self.instance, "trip_assignment_id", None),
        )
        bin_obj = attrs.get("bin_id", getattr(self.instance, "bin_id", None))

        if trip_cp:
            assignment = trip_cp.trip_assignment_id
            bin_obj = trip_cp.bin_id
            attrs["trip_assignment_id"] = assignment
            attrs["bin_id"] = bin_obj
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

        if trip_cp and trip_cp.trip_assignment_id != assignment:
            raise serializers.ValidationError(
                "Trip collection point does not belong to the selected assignment."
            )

        collection_point = attrs.get("collection_point_id")
        attrs["collection_date"] = (
            attrs.get("collection_date")
            or getattr(assignment, "trip_date", None)
        )
        ward = attrs.get("ward", getattr(self.instance, "ward", None))
        if not ward and assignment:
            assignment_wards = assignment.wards.all()
            if assignment_wards.count() == 1:
                ward = assignment_wards.first()
                attrs["ward"] = ward
        if ward and assignment and not assignment.wards.filter(unique_id=ward.unique_id).exists():
            raise serializers.ValidationError({"ward_id": "Ward must belong to the selected trip assignment."})
        if ward and collection_point and not collection_point.wards.filter(unique_id=ward.unique_id).exists():
            raise serializers.ValidationError({"ward_id": "Ward is not served by the selected collection point."})

        # These are intentionally not serializer fields. They are derived only
        # to satisfy the current model while the API exposes nested objects.
        if hasattr(BinCollectionEvent, "waste_type_id"):
            attrs["waste_type_id"] = getattr(bin_obj, "wastetype_id", None)
        if hasattr(BinCollectionEvent, "vehicle_id"):
            attrs["vehicle_id"] = self._resolve_vehicle(assignment)
        if hasattr(BinCollectionEvent, "vehicle_breakdown_id"):
            attrs["vehicle_breakdown_id"] = self._resolve_approved_breakdown(assignment)

        return attrs

    def _resolve_approved_breakdown(self, assignment):
        from app.models.core_modules.daily_operations.vehicle_breakdown import VehicleBreakdown

        try:
            breakdown = assignment.vehicle_breakdown
        except Exception:
            return None
        if breakdown.approval_status != VehicleBreakdown.APPROVAL_APPROVED:
            return None
        return breakdown

    def _resolve_vehicle(self, assignment):
        return getattr(assignment, "vehicle_id", None) or getattr(
            getattr(assignment, "trip_plan_id", None),
            "vehicle_id",
            None,
        )

    def _resolve_effective_staff_template(self, assignment):
        return getattr(assignment, "alt_staff_template_id", None) or getattr(
            assignment,
            "staff_template_id",
            None,
        )

    def _resolve_alternative_staff_template(self, obj):
        return getattr(obj.trip_assignment_id, "alt_staff_template_id", None)

    def get_bin(self, obj):
        if not obj.bin_id:
            return None
        return BinsSerializer(obj.bin_id, context=self.context).data

    def get_waste_type(self, obj):
        waste_type = getattr(getattr(obj, "bin_id", None), "wastetype_id", None)
        if not waste_type:
            return None
        return WasteTypeSerializer(waste_type, context=self.context).data

    def get_trip_plan(self, obj):
        trip_plan = getattr(obj.trip_assignment_id, "trip_plan_id", None)
        if not trip_plan:
            return None
        return {
            "unique_id": trip_plan.unique_id,
            "display_code": trip_plan.display_code,
        }

    def get_vehicle(self, obj):
        vehicle = self._resolve_vehicle(obj.trip_assignment_id)
        if not vehicle:
            return None
        return VehicleCreationSerializer(vehicle, context=self.context).data

    def get_staff_template(self, obj):
        staff_template = getattr(obj.trip_assignment_id, "staff_template_id", None)
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
        assignment = obj.trip_assignment_id
        staff_template = self._resolve_effective_staff_template(assignment)
        if not staff_template:
            return None

        if getattr(assignment, "alt_staff_template_id", None):
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
        # then fall back to the collection point / trip assignment.
        panchayat = (
            getattr(obj, "panchayat", None)
            or getattr(getattr(obj, "collection_point_id", None), "panchayat_id", None)
            or getattr(getattr(obj, "trip_assignment_id", None), "panchayat_id", None)
        )
        return getattr(panchayat, "panchayat_name", None)

    def get_location_name(self, obj):
        # Prefer the event's own geo; fall back to the collection point, then the trip assignment.
        name, _ = flat_geo_display(obj)
        if not name:
            name, _ = flat_geo_display(obj.collection_point_id)
        if not name:
            name, _ = flat_geo_display(obj.trip_assignment_id)
        return name

    def get_location_level(self, obj):
        _, level = flat_geo_display(obj)
        if not level:
            _, level = flat_geo_display(obj.collection_point_id)
        if not level:
            _, level = flat_geo_display(obj.trip_assignment_id)
        return level

    def get_collection_point(self, obj):
        cp = obj.collection_point_id
        if not cp:
            return None
        return {"unique_id": getattr(cp, "unique_id", None), "cp_name": getattr(cp, "cp_name", None)}

    def get_breakdown_info(self, obj):
        breakdown = getattr(obj, "vehicle_breakdown_id", None)
        if not breakdown:
            return None
        replacement_vehicle = getattr(breakdown, "replacement_vehicle_id", None)
        return {
            "unique_id": breakdown.unique_id,
            "status": breakdown.status,
            "approval_status": breakdown.approval_status,
            "breakdown_reason": breakdown.breakdown_reason,
            "replacement_vehicle_no": getattr(replacement_vehicle, "vehicle_no", None),
        }
