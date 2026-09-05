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

    staff_id = models.ForeignKey(
        StaffcreationOfficeDetails,
        on_delete=models.CASCADE,
        to_field="staff_unique_id",
        db_column="staff_id",
        related_name="access_configuration",
    )

    # Mobile apps this staff member may sign into. No module ticked means the
    # mobile login is refused — what they can do once inside comes from the
    # ordinary screen permissions, which also govern web.
    app_modules = models.ManyToManyField(
        AppModule,
        related_name="staff_access_configurations",
        blank=True,
    )

    # Geography, mirroring Staffcreation's own hierarchy. An empty selection
    # at a level means "unrestricted at that level", matching how the rest of
    # this codebase reads an empty scope.
    states = models.ManyToManyField(State, related_name="staff_access_configurations", blank=True)
    districts = models.ManyToManyField(District, related_name="staff_access_configurations", blank=True)
    area_types = models.ManyToManyField(AreaType, related_name="staff_access_configurations", blank=True)
    corporations = models.ManyToManyField(Corporation, related_name="staff_access_configurations", blank=True)
    municipalities = models.ManyToManyField(Municipality, related_name="staff_access_configurations", blank=True)
    town_panchayats = models.ManyToManyField(TownPanchayat, related_name="staff_access_configurations", blank=True)
    panchayat_unions = models.ManyToManyField(PanchayatUnion, related_name="staff_access_configurations", blank=True)
    panchayats = models.ManyToManyField(Panchayat, related_name="staff_access_configurations", blank=True)
    wards = models.ManyToManyField(Ward, related_name="staff_access_configurations", blank=True)

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
        return f"{self.staff_id_id}"

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

    staff_access_configuration_id = models.ForeignKey(
        StaffAccessConfiguration,
        on_delete=models.CASCADE,
        to_field="unique_id",
        db_column="staff_access_configuration_id",
        related_name="granted_permissions",
    )

    mainscreen_id = models.ForeignKey(
        MainScreen, on_delete=models.PROTECT,
        to_field="unique_id", db_column="mainscreen_id",
        related_name="staff_access_configuration_permissions",
    )
    userscreen_id = models.ForeignKey(
        UserScreen, on_delete=models.PROTECT,
        to_field="unique_id", db_column="userscreen_id",
        related_name="staff_access_configuration_permissions",
    )
    userscreenaction_id = models.ForeignKey(
        UserScreenAction, on_delete=models.PROTECT,
        to_field="unique_id", db_column="userscreenaction_id",
        related_name="staff_access_configuration_permissions",
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
        return f"{self.staff_access_configuration_id_id}:{self.userscreen_id_id}"

    def delete(self, *args, **kwargs):
        self.is_active = False
        self.is_deleted = True
        self.save(update_fields=["is_active", "is_deleted"])
