from django.db import models

from app.models.masters.corporation import Corporation
from app.models.masters.hierarchy_tree import HierarchyNode
from app.models.masters.municipality import Municipality
from app.models.masters.panchayat import Panchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.ward import Ward
from app.models.superadmin.staff_management.staffcreation import StaffcreationOfficeDetails
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils import ref_cache


def generate_staff_data_scope_id():
    return f"STAFFSCOPE-{generate_unique_id()}"


class StaffDataScope(BaseMaster):
    unique_id = models.CharField(
        max_length=60,
        primary_key=True,
        unique=True,
        default=generate_staff_data_scope_id,
        editable=False,
    )
    # StaffcreationOfficeDetails.staff_unique_id (plain string, no DB relation).
    staff_id = models.CharField(max_length=30, db_column="staff_id", db_index=True)
    # HierarchyNode unique_ids (plain JSON list); read via `location_nodes`.
    location_node_ids = models.JSONField(default=list, blank=True)
    # Plain CharFields holding State/District/AreaType.unique_id (no DB
    # relation/join) — matches the rest of the geo-hierarchy refactor's
    # convention. db_column kept as "state_id"/etc (the field's own bare
    # name predates the "_id"-suffixed FK attname convention) so the
    # existing DB columns are preserved unrenamed.
    state = models.CharField(max_length=30, null=True, blank=True, db_column="state_id")
    district = models.CharField(max_length=30, null=True, blank=True, db_column="district_id")
    area_type = models.CharField(max_length=30, null=True, blank=True, db_column="area_type_id")
    # Local-body / ward scope: plain JSON lists of unique_ids (a staff can be
    # scoped to several at once); read via the same-named properties below
    # (`corporations`, `wards`, ...), which return querysets.
    corporation_ids = models.JSONField(default=list, blank=True)
    municipality_ids = models.JSONField(default=list, blank=True)
    town_panchayat_ids = models.JSONField(default=list, blank=True)
    panchayat_union_ids = models.JSONField(default=list, blank=True)
    panchayat_ids = models.JSONField(default=list, blank=True)
    ward_ids = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Staff Data Scope"
        verbose_name_plural = "Staff Data Scopes"

    # Read-only `*_id` aliases: the rest of the flat-geo models name these
    # fields `state_id`/etc, and callers (e.g. the staff access dashboard)
    # read them that way. Writes/queries must still use the real field names.
    @property
    def state_id(self):
        return self.state

    @property
    def district_id(self):
        return self.district

    @property
    def area_type_id(self):
        return self.area_type

    @property
    def staff(self):
        return ref_cache.get(StaffcreationOfficeDetails, self.staff_id)

    @property
    def location_nodes(self):
        return HierarchyNode.objects.filter(unique_id__in=self.location_node_ids or [])

    @property
    def corporations(self):
        return Corporation.objects.filter(unique_id__in=self.corporation_ids or [])

    @property
    def municipalities(self):
        return Municipality.objects.filter(unique_id__in=self.municipality_ids or [])

    @property
    def town_panchayats(self):
        return TownPanchayat.objects.filter(unique_id__in=self.town_panchayat_ids or [])

    @property
    def panchayat_unions(self):
        return PanchayatUnion.objects.filter(unique_id__in=self.panchayat_union_ids or [])

    @property
    def panchayats(self):
        return Panchayat.objects.filter(unique_id__in=self.panchayat_ids or [])

    @property
    def wards(self):
        return Ward.objects.filter(unique_id__in=self.ward_ids or [])

    def __str__(self):
        return f"Data scope for {self.staff_id}"
