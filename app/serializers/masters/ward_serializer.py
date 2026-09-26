from rest_framework import serializers

from app.models.masters.ward import Ward
from app.models.superadmin.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat
from app.serializers.masters.geofence import GeoCoordinateSerializerMixin
from app.utils.hierarchy import BARE_TO_ID_GEO_FIELDS, normalize_flat_geo_attrs
from app.utils import ref_cache


class WardSerializer(GeoCoordinateSerializerMixin, serializers.ModelSerializer):
    # ---- Geo hierarchy: plain unique_id strings in, display names out ----
    # Ward's own columns are literally named "<field>_id" (CharField, no DB
    # relation) — same convention as Corporation/District/etc. — so these
    # input fields need no `source=` override; the declared name already
    # matches the model field.
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

    local_body_type = serializers.SerializerMethodField(read_only=True)
    local_body_name = serializers.SerializerMethodField(read_only=True)
    local_body_id = serializers.SerializerMethodField(read_only=True)

    # (bare geo-level name, model attribute) — the model attribute carries
    # the "_id" suffix (Ward's own literal field name).
    LOCAL_BODY_FIELDS = (
        ("corporation", "corporation_id"),
        ("municipality", "municipality_id"),
        ("town_panchayat", "town_panchayat_id"),
        ("panchayat_union", "panchayat_union_id"),
        ("panchayat", "panchayat_id"),
    )

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

    _LOCAL_BODY_MODELS = {
        "corporation_id": (Corporation, "corporation_name"),
        "municipality_id": (Municipality, "municipality_name"),
        "town_panchayat_id": (TownPanchayat, "town_panchayat_name"),
        "panchayat_union_id": (PanchayatUnion, "union_name"),
        "panchayat_id": (Panchayat, "panchayat_name"),
    }

    def get_local_body_type(self, obj):
        for level, attname in self.LOCAL_BODY_FIELDS:
            if getattr(obj, attname, None):
                return level
        return None

    def get_local_body_name(self, obj):
        for _, attname in self.LOCAL_BODY_FIELDS:
            value = getattr(obj, attname, None)
            if value:
                model, name_attr = self._LOCAL_BODY_MODELS[attname]
                return getattr(ref_cache.get(model, value, "unique_id"), name_attr, None)
        return None

    def get_local_body_id(self, obj):
        for _, attname in self.LOCAL_BODY_FIELDS:
            value = getattr(obj, attname, None)
            if value:
                return value
        return None

    class Meta:
        model = Ward
        fields = [
            "unique_id",
            "ward_name",
            "state_id", "state_name",
            "district_id", "district_name",
            "area_type_id", "area_type_name",
            "corporation_id", "corporation_name",
            "municipality_id", "municipality_name",
            "town_panchayat_id", "town_panchayat_name",
            "panchayat_union_id", "panchayat_union_name",
            "panchayat_id", "panchayat_name",
            "local_body_type",
            "local_body_name",
            "local_body_id",
            "coordinates",
            "is_active",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "is_deleted",
        ]
        read_only_fields = ["unique_id", "created_at", "updated_at"]
        # DRF auto-adds a UniqueTogetherValidator for the model's
        # unique_together, which would require ALL of corporation_id/
        # municipality_id/town_panchayat_id/panchayat_union_id/panchayat_id
        # to be present on every write — but the business rule is that only
        # ONE of those five is ever populated (enforced below via
        # normalize_flat_geo_attrs), so the auto validator is suppressed,
        # matching DistrictSerializer's identical `validators = []`.
        validators = []

    def validate(self, attrs):
        # `normalize_flat_geo_attrs` is shared with still-FK-based callers
        # (StaffTemplate/TripPlan) and works in terms of the bare geo-level
        # names ("state", "corporation", ...) both for reading `attrs`/
        # `instance` and for the keys it writes back. Ward's own model fields
        # are the "_id"-suffixed plain CharFields, so translate both ways
        # around the call: bare-keyed alias in, "_id"-suffixed attrs out.
        bare_attrs = dict(attrs)
        for bare, real in BARE_TO_ID_GEO_FIELDS.items():
            if real in bare_attrs:
                bare_attrs[bare] = bare_attrs.pop(real)

        errors = normalize_flat_geo_attrs(
            bare_attrs,
            instance=getattr(self, "instance", None),
            require_geo=True,
            as_strings=True,
        )
        if errors:
            raise serializers.ValidationError(errors)

        for bare, real in BARE_TO_ID_GEO_FIELDS.items():
            if bare in bare_attrs:
                attrs[real] = bare_attrs.pop(bare)
        attrs.update(bare_attrs)
        return attrs


class LiteWardSerializer(serializers.ModelSerializer):
    """Minimal ?lite=1 response: unique_id + ward_name + the district_id and
    local_body_type/id fields the geo-cascade dropdowns (useGeoHierarchy
    consumers) filter on, without the full nested name lookups."""

    district_id = serializers.CharField(read_only=True)
    local_body_type = serializers.SerializerMethodField()
    local_body_id = serializers.SerializerMethodField()

    def get_local_body_type(self, obj):
        for level, attname in WardSerializer.LOCAL_BODY_FIELDS:
            if getattr(obj, attname, None):
                return level
        return None

    def get_local_body_id(self, obj):
        for _, attname in WardSerializer.LOCAL_BODY_FIELDS:
            value = getattr(obj, attname, None)
            if value:
                return value
        return None

    class Meta:
        model = Ward
        fields = ["unique_id", "ward_name", "district_id", "local_body_type", "local_body_id"]
