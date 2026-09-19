from django.db import models

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_ward_id():
    return f"WARD-{generate_unique_id()}"


class Ward(BaseMaster):
    """A ward sits under exactly one local body — Corporation/Municipality/
    TownPanchayat (ULB) or PanchayatUnion/Panchayat (RLB) — mirroring the same
    flat-geo FK block used by TripPlan/StaffTemplate/CustomerCreation. Exactly
    one of the five local-body FKs is populated per row; enforced in
    `WardSerializer.validate` via `normalize_flat_geo_attrs`, not at the DB
    level, matching that existing convention.

    state_id/district_id/area_type_id/corporation_id/municipality_id/
    town_panchayat_id/panchayat_union_id/panchayat_id are plain CharFields
    holding the related row's `unique_id` (no DB relation/join) — literal
    field names with the "_id" suffix, matching the rest of the geo-hierarchy
    (Continent/Country/State/District/AreaType/Corporation/Municipality/
    TownPanchayat/Panchayat/PanchayatUnion all follow this same convention)."""

    CASCADE_SOFT_DELETE = (
        "bins",
        "bin_collection_events",
        "waste_collections",
        "customers",
        "staff_access_configurations",
    )
    CACHE_SCOPES = ("ward_list", "ward_detail")

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_ward_id,
        editable=False,
    )
    state_id = models.CharField(max_length=30, null=True, blank=True)
    district_id = models.CharField(max_length=30, null=True, blank=True)
    area_type_id = models.CharField(max_length=30, null=True, blank=True)
    corporation_id = models.CharField(max_length=30, null=True, blank=True)
    municipality_id = models.CharField(max_length=30, null=True, blank=True)
    town_panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_union_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_id = models.CharField(max_length=30, null=True, blank=True)

    ward_name = models.CharField(max_length=100)
    coordinates = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ward_name"]
        unique_together = (
            "corporation_id", "municipality_id", "town_panchayat_id",
            "panchayat_union_id", "panchayat_id", "ward_name",
        )

    def __str__(self):
        return self.ward_name
