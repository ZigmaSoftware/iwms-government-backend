from rest_framework import serializers
from app.models.core_modules.daily_operations.waste_collection import WasteCollection
from app.utils.waste_images import capture_images_for_customer
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.superadmin.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.utils.hierarchy import flat_geo_display
from app.utils import ref_cache
from app.serializers.masters.transport_masters.vehicleCreation_serializer import (
    VehicleCreationSerializer,
)


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
    ward_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    ward_name = serializers.SerializerMethodField()
    # Writable plain unique_id string (no DB relation).
    # Accept both 'customer_id' (legacy) and 'customer' (frontend).
    customer_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    customer = serializers.CharField(required=False, allow_null=True, allow_blank=True, write_only=True)
    customer_name = serializers.CharField(source="customer.customer_name", read_only=True)
    # Household (customer) contact & address, surfaced read-only for the list/form
    contact_no = serializers.CharField(source="customer.contact_no", read_only=True)
    building_no = serializers.CharField(source="customer.building_no", read_only=True)
    street = serializers.CharField(source="customer.street", read_only=True)
    area = serializers.CharField(source="customer.area", read_only=True)

    # ---- geography: state/district/area type/local body (stored on the record,
    # auto-inherited from the household when left blank in WasteCollection.save).
    # Plain unique_id strings in, display names out (see WardSerializer).
    state_id = serializers.CharField(required=False, allow_null=True)
    district_id = serializers.CharField(required=False, allow_null=True)
    area_type_id = serializers.CharField(required=False, allow_null=True)
    corporation_id = serializers.CharField(required=False, allow_null=True)
    municipality_id = serializers.CharField(required=False, allow_null=True)
    town_panchayat_id = serializers.CharField(required=False, allow_null=True)
    panchayat_union_id = serializers.CharField(required=False, allow_null=True)
    panchayat_id = serializers.CharField(required=False, allow_null=True)

    state_name = serializers.SerializerMethodField()
    district_name = serializers.SerializerMethodField()
    area_type_name = serializers.SerializerMethodField()
    corporation_name = serializers.SerializerMethodField()
    municipality_name = serializers.SerializerMethodField()
    town_panchayat_name = serializers.SerializerMethodField()
    panchayat_union_name = serializers.SerializerMethodField()
    panchayat_name = serializers.SerializerMethodField()

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

    def get_panchayat_name(self, obj):
        return getattr(ref_cache.get(Panchayat, obj.panchayat_id, "unique_id"), "panchayat_name", None)

    # Most-specific local body (corporation/municipality/.../panchayat) + its level
    location_name = serializers.SerializerMethodField(read_only=True)
    location_level = serializers.SerializerMethodField(read_only=True)

    # Vehicle that performed the collection, resolved via the linked trip
    # assignment (falling back to its trip plan's vehicle).
    vehicle = serializers.SerializerMethodField(read_only=True)

    # Capture photos taken during collection. They live on the separate
    # WasteCollectionSub model (mobile capture flow), linked here by the same
    # household + collection date. Read-only convenience for the desktop screen.
    capture_images = serializers.SerializerMethodField(read_only=True)

    trip_assignment_id = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )

    class Meta:
        model = WasteCollection
        # Explicit list: the model's bare geo FKs (state/district/...) are written
        # via the *_id SlugRelatedFields above, so they are intentionally omitted
        # here to avoid duplicate writable fields on the same source.
        # Disable automatic UniqueTogetherValidator since we handle it manually in create()
        validators = []
        fields = [
            "unique_id",
            "customer_id",
            "customer",
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
            "ward_id",
            "ward_name",
            "location_name",
            "location_level",
            "vehicle",
            "capture_images",
            "trip_assignment_id",
            "wet_waste",
            "dry_waste",
            "mixed_waste",
            "sanitary_waste",
            "total_quantity",
            "status",
            "collection_date",
            "collection_time",
            "is_active",
            "is_deleted",
        ]
        read_only_fields = ["unique_id", "total_quantity", "collection_time"]

    def get_ward_name(self, obj):
        return getattr(obj.ward, "ward_name", None)

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

    def get_vehicle(self, obj):
        assignment = obj.trip_assignment
        if not assignment:
            return None
        vehicle = getattr(assignment, "vehicle", None) or getattr(
            getattr(assignment, "trip_plan", None), "vehicle", None
        )
        if not vehicle:
            return None
        return VehicleCreationSerializer(vehicle, context=self.context).data

    def get_capture_images(self, obj):
        """Capture photos for this collection, pulled from WasteCollectionSub
        (the mobile capture flow) for the same household + collection date."""
        return capture_images_for_customer(
            obj.customer_id,
            obj.collection_date,
            self.context.get("request"),
        )

    def validate_customer_id(self, value):
        if value is not None and value != "":
            if not CustomerCreation.objects.filter(unique_id=value).exists():
                raise serializers.ValidationError("Invalid customer reference")
        return value

    def validate_customer(self, value):
        if value is not None and value != "":
            if not CustomerCreation.objects.filter(unique_id=value).exists():
                raise serializers.ValidationError("Invalid customer reference")
        return value

    def validate(self, attrs):
        # Accept customer from either 'customer' or 'customer_id'
        customer_id = attrs.get("customer_id") or attrs.get("customer")
        if not customer_id:
            raise serializers.ValidationError({"customer_id": "Customer is required"})
        if not CustomerCreation.objects.filter(unique_id=customer_id).exists():
            raise serializers.ValidationError({"customer_id": "Invalid customer reference"})
        attrs["customer_id"] = customer_id
        # Remove 'customer' field as it's write-only and the model has no setter
        attrs.pop("customer", None)
        return attrs

    def create(self, validated_data):
        validated_data.pop("customer", None)
        
        # Check for existing record for this customer + trip assignment
        customer_id = validated_data.get("customer_id")
        trip_assignment_id = validated_data.get("trip_assignment_id")
        
        if customer_id and trip_assignment_id:
            existing = WasteCollection.objects.filter(
                customer_id=customer_id,
                trip_assignment_id=trip_assignment_id,
                is_deleted=False
            ).first()
            if existing:
                # Update existing record instead of creating duplicate
                for key, value in validated_data.items():
                    setattr(existing, key, value)
                existing.save()
                return existing
        
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop("customer", None)
        return super().update(instance, validated_data)

    def validate_ward_id(self, value):
        if value and not Ward.objects.filter(unique_id=value).exists():
            raise serializers.ValidationError("Invalid ward.")
        return value or None

    def validate_trip_assignment_id(self, value):
        if value and not DailyTripAssignment.objects.filter(unique_id=value).exists():
            raise serializers.ValidationError("Invalid trip assignment.")
        return value or None
