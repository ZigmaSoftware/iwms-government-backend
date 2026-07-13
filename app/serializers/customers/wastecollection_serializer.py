from rest_framework import serializers
from app.models.customers.wastecollection import WasteCollection
from app.models.customers.customercreation import CustomerCreation
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat
from app.utils.hierarchy import flat_geo_display


class CustomerField(serializers.SlugRelatedField):
    """Accept customer unique_id or PK, serialize as unique_id."""

    def to_representation(self, value):
        return value.unique_id if value else None

    def to_internal_value(self, data):
        if data in [None, ""]:
            raise serializers.ValidationError("Customer is required")
        # try unique_id
        try:
            return self.get_queryset().get(unique_id=str(data))
        except CustomerCreation.DoesNotExist:
            # fallback: pk
            try:
                return self.get_queryset().get(pk=int(data))
            except (ValueError, TypeError, CustomerCreation.DoesNotExist):
                raise serializers.ValidationError("Invalid customer reference")


class WasteCollectionSerializer(serializers.ModelSerializer):
    customer = CustomerField(
        slug_field="unique_id",
        queryset=CustomerCreation.objects.all(),
        write_only=True,
    )
    # Expose customer unique identifier as `customer_id`
    customer_id = serializers.CharField(
        source="customer.unique_id", read_only=True
    )
    customer_name = serializers.CharField(source="customer.customer_name", read_only=True)
    # Household (customer) contact & address, surfaced read-only for the list/form
    contact_no = serializers.CharField(source="customer.contact_no", read_only=True)
    building_no = serializers.CharField(source="customer.building_no", read_only=True)
    street = serializers.CharField(source="customer.street", read_only=True)
    area = serializers.CharField(source="customer.area", read_only=True)

    # ---- geography: state/district/area type/local body (stored on the record,
    # auto-inherited from the household when left blank in WasteCollection.save) --
    state_id = serializers.SlugRelatedField(
        source="state", queryset=State.objects.filter(is_deleted=False),
        slug_field="unique_id", required=False, allow_null=True,
    )
    state_name = serializers.CharField(source="state.name", read_only=True)

    district_id = serializers.SlugRelatedField(
        source="district", queryset=District.objects.filter(is_deleted=False),
        slug_field="unique_id", required=False, allow_null=True,
    )
    district_name = serializers.CharField(source="district.name", read_only=True)

    area_type_id = serializers.SlugRelatedField(
        source="area_type", queryset=AreaType.objects.filter(is_deleted=False),
        slug_field="unique_id", required=False, allow_null=True,
    )
    area_type_name = serializers.CharField(source="area_type.name", read_only=True)

    corporation_id = serializers.SlugRelatedField(
        source="corporation", queryset=Corporation.objects.filter(is_deleted=False),
        slug_field="unique_id", required=False, allow_null=True,
    )
    corporation_name = serializers.CharField(source="corporation.corporation_name", read_only=True)

    municipality_id = serializers.SlugRelatedField(
        source="municipality", queryset=Municipality.objects.filter(is_deleted=False),
        slug_field="unique_id", required=False, allow_null=True,
    )
    municipality_name = serializers.CharField(source="municipality.municipality_name", read_only=True)

    town_panchayat_id = serializers.SlugRelatedField(
        source="town_panchayat", queryset=TownPanchayat.objects.filter(is_deleted=False),
        slug_field="unique_id", required=False, allow_null=True,
    )
    town_panchayat_name = serializers.CharField(source="town_panchayat.town_panchayat_name", read_only=True)

    panchayat_union_id = serializers.SlugRelatedField(
        source="panchayat_union", queryset=PanchayatUnion.objects.filter(is_deleted=False),
        slug_field="unique_id", required=False, allow_null=True,
    )
    panchayat_union_name = serializers.CharField(source="panchayat_union.union_name", read_only=True)

    panchayat_id = serializers.SlugRelatedField(
        source="panchayat", queryset=Panchayat.objects.filter(is_deleted=False),
        slug_field="unique_id", required=False, allow_null=True,
    )
    panchayat_name = serializers.CharField(source="panchayat.panchayat_name", read_only=True)

    # Most-specific local body (corporation/municipality/.../panchayat) + its level
    location_name = serializers.SerializerMethodField(read_only=True)
    location_level = serializers.SerializerMethodField(read_only=True)

    trip_assignment_id = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=DailyTripAssignment.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )
    trip_assignment_display = serializers.CharField(
        source="trip_assignment_id.unique_id", read_only=True, default=None
    )

    class Meta:
        model = WasteCollection
        # Explicit list: the model's bare geo FKs (state/district/...) are written
        # via the *_id SlugRelatedFields above, so they are intentionally omitted
        # here to avoid duplicate writable fields on the same source.
        fields = [
            "unique_id",
            "customer",
            "customer_id",
            "customer_name",
            "contact_no",
            "building_no",
            "street",
            "area",
            "state_id",
            "state_name",
            "district_id",
            "district_name",
            "area_type_id",
            "area_type_name",
            "corporation_id",
            "corporation_name",
            "municipality_id",
            "municipality_name",
            "town_panchayat_id",
            "town_panchayat_name",
            "panchayat_union_id",
            "panchayat_union_name",
            "panchayat_id",
            "panchayat_name",
            "location_name",
            "location_level",
            "trip_assignment_id",
            "trip_assignment_display",
            "wet_waste",
            "dry_waste",
            "mixed_waste",
            "total_quantity",
            "collection_date",
            "collection_time",
            "is_active",
            "is_deleted",
        ]
        read_only_fields = ["unique_id", "total_quantity", "collection_date", "collection_time"]

    def get_location_name(self, obj):
        # Prefer the record's own geo; fall back to the household's.
        name, _ = flat_geo_display(obj)
        if not name:
            name, _ = flat_geo_display(obj.customer)
        return name

    def get_location_level(self, obj):
        _, level = flat_geo_display(obj)
        if not level:
            _, level = flat_geo_display(obj.customer)
        return level
