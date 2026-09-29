from django.db import models

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils import ref_cache


def generate_staff_hierarchy_id():
    return f"STFHIER-{generate_unique_id()}"


class StaffHierarchy(BaseMaster):
    """Configurable reporting chain between Government Staff User Types.

    Each row says: staff of `governmentusertype_id` report up to staff of
    `reports_to_governmentusertype_id`. A blank reports-to marks the top of
    the chain (the platform super admin heads them). Replaces the fixed
    driver/operator -> supervisor -> admin rule the Staff Head dropdown
    used, so a chain can skip roles or cross levels (e.g. a Panchayat
    Supervisor reporting to a District Officer).

    A row can be scoped to a place — country, state, district, area type
    and/or one local body — so the chain can differ district to district or
    panchayat to panchayat. Blank scope columns mean "everywhere"; for a
    given staff member the most specific row covering their area wins (see
    app/utils/staff_hierarchy.py). Uniqueness of (role, scope) among active
    rows is enforced by the serializer, since NULL scope columns cannot take
    part in a database unique constraint.
    """

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_staff_hierarchy_id,
        editable=False,
    )

    # GovernmentStaffUserType unique_ids (plain strings, no DB relation).
    governmentusertype_id = models.CharField(
        max_length=40, db_column="governmentusertype_id", db_index=True
    )
    reports_to_governmentusertype_id = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        db_column="reports_to_governmentusertype_id",
        help_text="Left blank for the top of the chain (e.g. State Admin).",
    )

    # Scope (plain unique_id strings, no DB relation), broadest first. At
    # most one local-body column is set.
    country_id = models.CharField(max_length=30, null=True, blank=True, db_column="country_id")
    state_id = models.CharField(max_length=30, null=True, blank=True, db_column="state_id")
    district_id = models.CharField(max_length=30, null=True, blank=True, db_column="district_id")
    area_type_id = models.CharField(max_length=30, null=True, blank=True, db_column="area_type_id")
    corporation_id = models.CharField(max_length=30, null=True, blank=True, db_column="corporation_id")
    municipality_id = models.CharField(max_length=30, null=True, blank=True, db_column="municipality_id")
    town_panchayat_id = models.CharField(max_length=30, null=True, blank=True, db_column="town_panchayat_id")
    panchayat_union_id = models.CharField(max_length=30, null=True, blank=True, db_column="panchayat_union_id")
    panchayat_id = models.CharField(max_length=30, null=True, blank=True, db_column="panchayat_id")

    hierarchy_level = models.PositiveIntegerField(
        default=1,
        help_text="Display/ordering rank (1 = lowest level).",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["hierarchy_level", "created_at"]
        verbose_name = "Staff Hierarchy"
        verbose_name_plural = "Staff Hierarchies"
        indexes = [
            models.Index(fields=["governmentusertype_id", "is_deleted"]),
            models.Index(fields=["district_id"]),
        ]

    def __str__(self):
        return f"{self.governmentusertype_id} -> {self.reports_to_governmentusertype_id or '—'}"

    @property
    def governmentusertype(self):
        from .governmentStaffUserType import GovernmentStaffUserType
        return ref_cache.get(GovernmentStaffUserType, self.governmentusertype_id)

    @property
    def reports_to_governmentusertype(self):
        from .governmentStaffUserType import GovernmentStaffUserType
        if not self.reports_to_governmentusertype_id:
            return None
        return ref_cache.get(GovernmentStaffUserType, self.reports_to_governmentusertype_id)

    def delete(self, *args, **kwargs):
        self.is_active = False
        self.is_deleted = True
        self.save(update_fields=["is_active", "is_deleted"])
