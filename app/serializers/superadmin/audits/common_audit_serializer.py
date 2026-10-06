from rest_framework import serializers

from app.utils import ref_cache
from app.utils.common_audit import CommonAudit
from app.utils.hierarchy import (
    FLAT_GEO_LEVEL_CANDIDATES,
    LOCAL_BODY_FIELDS,
    _geo_attr_value,
    _geo_model,
)

# {geo field: (name attribute on its master, display label)}
GEO_NAME_ATTRS = {
    field: (name_attr, label) for field, name_attr, label in FLAT_GEO_LEVEL_CANDIDATES
}


def geo_ref_name(field, unique_id):
    """Display name of the `field`-level geo master row `unique_id`, cached
    for the rest of the request so a list page resolves each body once."""
    if not unique_id or field not in GEO_NAME_ATTRS:
        return None
    row = ref_cache.get(_geo_model(field), unique_id, "unique_id")
    return getattr(row, GEO_NAME_ATTRS[field][0], None) or None


def local_body_ref(obj):
    """(level, unique_id) of `obj`'s most specific local body, or
    (None, None). Works for bare-named geo fields (CommonAudit) and
    "<field>_id"-named ones (Staffcreation) alike."""
    if obj is None:
        return None, None
    for field in reversed(LOCAL_BODY_FIELDS):
        value = _geo_attr_value(obj, field)
        if value:
            return field, getattr(value, "unique_id", value)
    return None, None


def geo_display(obj):
    """{district_name, local_body_name, local_body_level} for `obj` — the
    government counterpart of the company/project names the private trail
    shows, since rows here are scoped by geography, not tenancy."""
    district_id = _geo_attr_value(obj, "district") if obj is not None else None
    district_id = getattr(district_id, "unique_id", district_id)
    level, local_body_id = local_body_ref(obj)
    return {
        "district_name": geo_ref_name("district", district_id),
        "local_body_name": geo_ref_name(level, local_body_id) if level else None,
        "local_body_level": GEO_NAME_ATTRS[level][1] if level else None,
    }


class CommonAuditSerializer(serializers.ModelSerializer):

    # Rows written before actor capture existed have no actor name. Surface
    # the legacy createdBy string instead of rendering a blank cell.
    created_by_name = serializers.SerializerMethodField()
    district_name = serializers.SerializerMethodField()
    local_body_name = serializers.SerializerMethodField()
    local_body_level = serializers.SerializerMethodField()

    class Meta:
        model = CommonAudit
        fields = "__all__"
        # Identity, request context and geo scope are stamped server-side in
        # perform_create and must never be accepted from the client, or the
        # trail is forgeable (or fileable under another local body).
        read_only_fields = (
            "uuid",
            "createdAt",
            "createdBy",
            "created_by_id",
            "created_by_name",
            "created_by_type",
            "ip_address",
            "user_agent",
            "success",
            "reason",
            "state",
            "district",
            "area_type",
            "corporation",
            "municipality",
            "town_panchayat",
            "panchayat_union",
            "panchayat",
        )

    def _geo(self, obj):
        cache = getattr(self, "_geo_cache", None)
        if cache is None:
            cache = self._geo_cache = {}
        if obj.pk not in cache:
            cache[obj.pk] = geo_display(obj)
        return cache[obj.pk]

    def get_created_by_name(self, obj):
        return obj.created_by_name or obj.createdBy or None

    def get_district_name(self, obj):
        return self._geo(obj)["district_name"]

    def get_local_body_name(self, obj):
        return self._geo(obj)["local_body_name"]

    def get_local_body_level(self, obj):
        return self._geo(obj)["local_body_level"]
