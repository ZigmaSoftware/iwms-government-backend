from django.db import models

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.superadmin.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat


def generate_ward_id():
    return f"WARD-{generate_unique_id()}"


class Ward(BaseMaster):
    """A ward sits under exactly one local body — Corporation/Municipality/
    TownPanchayat (ULB) or PanchayatUnion/Panchayat (RLB) — mirroring the same
    flat-geo FK block used by TripPlan/StaffTemplate/CustomerCreation. Exactly
    one of the five local-body FKs is populated per row; enforced in
    `WardSerializer.validate` via `normalize_flat_geo_attrs`, not at the DB
    level, matching that existing convention."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_ward_id,
        editable=False,
    )
    state = models.ForeignKey(
        State,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="wards",
        to_field="unique_id",
        db_column="state_id",
    )
    district = models.ForeignKey(
        District,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="wards",
        to_field="unique_id",
        db_column="district_id",
    )
    area_type = models.ForeignKey(
        AreaType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="wards",
        to_field="unique_id",
        db_column="area_type_id",
    )
    corporation = models.ForeignKey(
        Corporation,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="wards",
        to_field="unique_id",
        db_column="corporation_id",
    )
    municipality = models.ForeignKey(
        Municipality,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="wards",
        to_field="unique_id",
        db_column="municipality_id",
    )
    town_panchayat = models.ForeignKey(
        TownPanchayat,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="wards",
        to_field="unique_id",
        db_column="town_panchayat_id",
    )
    panchayat_union = models.ForeignKey(
        PanchayatUnion,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="wards",
        to_field="unique_id",
        db_column="panchayat_union_id",
    )
    panchayat = models.ForeignKey(
        Panchayat,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="wards",
        to_field="unique_id",
        db_column="panchayat_id",
    )

    ward_name = models.CharField(max_length=100)
    coordinates = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ward_name"]
        unique_together = (
            "corporation", "municipality", "town_panchayat",
            "panchayat_union", "panchayat", "ward_name",
        )

    def __str__(self):
        return self.ward_name
