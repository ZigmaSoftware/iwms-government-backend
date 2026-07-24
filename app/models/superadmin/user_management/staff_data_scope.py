from django.db import models

from app.models.superadmin.common_masters.state import State
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.district import District
from app.models.masters.hierarchy_tree import HierarchyNode
from app.models.masters.municipality import Municipality
from app.models.masters.panchayat import Panchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.ward import Ward
from app.models.superadmin.user_management.staffcreation import StaffcreationOfficeDetails
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


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
    staff = models.ForeignKey(
        StaffcreationOfficeDetails,
        on_delete=models.CASCADE,
        to_field="staff_unique_id",
        db_column="staff_id",
        related_name="data_scopes",
    )
    location_nodes = models.ManyToManyField(
        HierarchyNode,
        blank=True,
        related_name="scoped_staff",
    )
    state = models.ForeignKey(
        State,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scoped_staff",
        to_field="unique_id",
        db_column="state_id",
    )
    district = models.ForeignKey(
        District,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scoped_staff",
        to_field="unique_id",
        db_column="district_id",
    )
    area_type = models.ForeignKey(
        AreaType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scoped_staff",
        to_field="unique_id",
        db_column="area_type_id",
    )
    corporations = models.ManyToManyField(
        Corporation,
        blank=True,
        related_name="scoped_staff",
    )
    municipalities = models.ManyToManyField(
        Municipality,
        blank=True,
        related_name="scoped_staff",
    )
    town_panchayats = models.ManyToManyField(
        TownPanchayat,
        blank=True,
        related_name="scoped_staff",
    )
    panchayat_unions = models.ManyToManyField(
        PanchayatUnion,
        blank=True,
        related_name="scoped_staff",
    )
    panchayats = models.ManyToManyField(
        Panchayat,
        blank=True,
        related_name="scoped_staff",
    )
    wards = models.ManyToManyField(
        Ward,
        blank=True,
        related_name="scoped_staff",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Staff Data Scope"
        verbose_name_plural = "Staff Data Scopes"

    def __str__(self):
        return f"Data scope for {self.staff_id}"
