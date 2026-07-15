from django.conf import settings
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

    # Capture photos taken during collection. They live on the separate
    # WasteCollectionSub model (mobile capture flow), linked here by the same
    # household + collection date. Read-only convenience for the desktop screen.
    capture_images = serializers.SerializerMethodField(read_only=True)

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
            "capture_images",
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

    def get_capture_images(self, obj):
        """Capture photos for this collection, pulled from WasteCollectionSub
        (the mobile capture flow) for the same household. Linked by customer and,
        when available, the collection date. Returns absolute /media/ URLs."""
        from app.models.user_creations.waste_collection_bluetooth import (
            WasteCollectionSub,
        )

        subs = WasteCollectionSub.objects.filter(
            customer_id=obj.customer_id, is_deleted=False
        ).exclude(image__isnull=True).exclude(image="")
        if obj.collection_date:
            # Scope to the collection day via a datetime range (± 1 day to absorb
            # timezone skew) instead of a `__date` lookup, which is unreliable on
            # MySQL when the server timezone tables aren't loaded.
            import datetime as _dt

            from django.utils import timezone as _tz

            start = _dt.datetime.combine(obj.collection_date, _dt.time.min) - _dt.timedelta(days=1)
            end = _dt.datetime.combine(obj.collection_date, _dt.time.max) + _dt.timedelta(days=1)
            if _tz.is_aware(_tz.now()):
                start = _tz.make_aware(start)
                end = _tz.make_aware(end)
            subs = subs.filter(date_time__gte=start, date_time__lte=end)

        request = self.context.get("request")
        images = []
        for sub in subs.order_by("date_time"):
            url = self._build_media_url(sub.image, request)
            if url:
                images.append({
                    "url": url,
                    "waste_type_id": sub.waste_type_id,
                    "weight": sub.weight,
                })
        return images

    @staticmethod
    def _build_media_url(image, request):
        """Build a servable media URL from a stored image path. The mobile
        uploader stores paths like 'uploads/waste_collection_images/<file>' even
        though the file is served from MEDIA_URL + 'waste_collection_images/', so
        rebuild the URL from the filename to avoid the stale 'uploads/' prefix."""
        if not image:
            return None
        image = str(image)
        if image.startswith("http"):
            return image
        filename = image.rstrip("/").split("/")[-1]
        path = f"{settings.MEDIA_URL}waste_collection_images/{filename}"
        return request.build_absolute_uri(path) if request is not None else path
