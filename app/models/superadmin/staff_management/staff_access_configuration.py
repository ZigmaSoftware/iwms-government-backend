"""Per-staff access configuration — the anchor for mobile app access.

Ported from the private backend, re-mapped onto this codebase's geography.
Private scopes staff by company/project + zone/ward; here the scope is the
government hierarchy (state -> district -> area type -> local body -> ward),
so the M2Ms below mirror `Staffcreation`'s own FKs rather than private's.

What this adds on top of the existing permission system:

* `app_modules` — which mobile apps this person may sign into. No module
  ticked means the mobile login is refused outright. This is the piece the
  Flutter app depends on; it has no counterpart in the role/geography-keyed
  `UserScreenPermission` rows, which say what a role can do, not which app a
  particular person opens.

* `granted_permissions` — optional per-staff screen grants. These are layered
  on top of whatever the role already resolves to, never instead of it, so
  the existing role + geography resolution keeps working untouched for every
  staff member who has no configuration here.

* `enforce_strict_permissions` — when on, the role baseline stops applying to
  this person and the grants here are the whole of their access. Off by
  default so adding a configuration can never narrow someone unexpectedly.
"""

from django.db import models
from django.db.models import UniqueConstraint

from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.district import District
from app.models.masters.municipality import Municipality
from app.models.masters.panchayat import Panchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.ward import Ward
from app.models.superadmin.common_masters.state import State
from app.models.superadmin.screen_management.app_module import AppModule
from app.models.superadmin.screen_management.mainscreen import MainScreen
from app.models.superadmin.screen_management.userscreen import UserScreen
from app.models.superadmin.screen_management.userscreenaction import UserScreenAction
from app.models.superadmin.staff_management.staffcreation import StaffcreationOfficeDetails
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils import ref_cache


def generate_staff_access_configuration_id():
    return f"STFACCCFG-{generate_unique_id()}"


class StaffAccessConfiguration(BaseMaster):
    unique_id = models.CharField(
        max_length=60,
        primary_key=True,
        unique=True,
        default=generate_staff_access_configuration_id,
        editable=False,
    )

    # StaffcreationOfficeDetails.staff_unique_id (plain string, no DB relation).
    staff_id = models.CharField(max_length=30, db_column="staff_id", db_index=True)

    # Mobile apps this staff member may sign into (AppModule unique_ids). No
    # module ticked means the mobile login is refused — what they can do once
    # inside comes from the ordinary screen permissions, which also govern web.
    app_module_ids = models.JSONField(default=list, blank=True)

    # Geography, mirroring Staffcreation's own hierarchy, as plain JSON lists
    # of unique_ids (read through the same-named properties below). An empty
    # selection at a level means "unrestricted at that level", matching how
    # the rest of this codebase reads an empty scope.
    state_ids = models.JSONField(default=list, blank=True)
    district_ids = models.JSONField(default=list, blank=True)
    area_type_ids = models.JSONField(default=list, blank=True)
    corporation_ids = models.JSONField(default=list, blank=True)
    municipality_ids = models.JSONField(default=list, blank=True)
    town_panchayat_ids = models.JSONField(default=list, blank=True)
    panchayat_union_ids = models.JSONField(default=list, blank=True)
    panchayat_ids = models.JSONField(default=list, blank=True)
    ward_ids = models.JSONField(default=list, blank=True)

    enforce_strict_permissions = models.BooleanField(
        default=False,
        help_text=(
            "When off (the default), the staff member's role permissions still "
            "apply on top of the grants below, so a partial configuration "
            "cannot lock them out. Turn it on only once their grants have been "
            "verified — then these grants are the whole of their access."
        ),
    )

    description = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            UniqueConstraint(
                fields=["staff_id"],
                condition=models.Q(is_deleted=False),
                name="uq_active_staff_access_configuration",
            )
        ]

    def __str__(self):
        return f"{self.staff_id}"

    @property
    def staff(self):
        return ref_cache.get(StaffcreationOfficeDetails, self.staff_id)

    @property
    def app_modules(self):
        return AppModule.objects.filter(unique_id__in=self.app_module_ids or [])

    @property
    def states(self):
        return State.objects.filter(unique_id__in=self.state_ids or [])

    @property
    def districts(self):
        return District.objects.filter(unique_id__in=self.district_ids or [])

    @property
    def area_types(self):
        return AreaType.objects.filter(unique_id__in=self.area_type_ids or [])

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

    @property
    def granted_permissions(self):
        """This configuration's screen grants (plain
        staff_access_configuration_id); replaces the reverse FK accessor."""
        return StaffAccessConfigurationPermission.objects.filter(
            staff_access_configuration_id=self.unique_id
        )

    def delete(self, *args, **kwargs):
        self.is_active = False
        self.is_deleted = True
        self.save(update_fields=["is_active", "is_deleted"])


def generate_staff_access_configuration_permission_id():
    return f"STFACCCFGPERM-{generate_unique_id()}"


class StaffAccessConfigurationPermission(BaseMaster):
    """A single screen+action grant belonging to a StaffAccessConfiguration.

    Scope (geography) is inherited from the parent configuration, not
    duplicated here.
    """

    unique_id = models.CharField(
        max_length=70,
        primary_key=True,
        unique=True,
        default=generate_staff_access_configuration_permission_id,
        editable=False,
    )

    # Plain unique_id strings (no DB relation); read via the properties below.
    staff_access_configuration_id = models.CharField(
        max_length=60, db_column="staff_access_configuration_id", db_index=True
    )
    mainscreen_id = models.CharField(max_length=30, db_column="mainscreen_id", db_index=True)
    userscreen_id = models.CharField(max_length=30, db_column="userscreen_id", db_index=True)
    userscreenaction_id = models.CharField(
        max_length=30, db_column="userscreenaction_id", db_index=True
    )

    order_no = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order_no"]
        constraints = [
            UniqueConstraint(
                fields=[
                    "staff_access_configuration_id",
                    "userscreen_id",
                    "userscreenaction_id",
                ],
                condition=models.Q(is_deleted=False),
                name="uq_active_staff_access_configuration_permission",
            )
        ]

    def __str__(self):
        return f"{self.staff_access_configuration_id}:{self.userscreen_id}"

    @property
    def staff_access_configuration(self):
        return ref_cache.get(StaffAccessConfiguration, self.staff_access_configuration_id)

    @property
    def mainscreen(self):
        return ref_cache.get(MainScreen, self.mainscreen_id)

    @property
    def userscreen(self):
        return ref_cache.get(UserScreen, self.userscreen_id)

    @property
    def userscreenaction(self):
        return ref_cache.get(UserScreenAction, self.userscreenaction_id)

    def delete(self, *args, **kwargs):
        self.is_active = False
        self.is_deleted = True
        self.save(update_fields=["is_active", "is_deleted"])
