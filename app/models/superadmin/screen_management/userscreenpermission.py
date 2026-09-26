from django.db import models
from django.db.models import Q, UniqueConstraint
from app.models.superadmin.screen_management.mainscreen import MainScreen
from app.models.superadmin.screen_management.userscreen import UserScreen
from app.models.superadmin.screen_management.userscreenaction import UserScreenAction
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils import ref_cache


class LocalBodyType(models.TextChoices):
    CORPORATION = "corporation", "Corporation"
    MUNICIPALITY = "municipality", "Municipality"
    PANCHAYAT = "panchayat", "Panchayat"
    TOWN_PANCHAYAT = "town_panchayat", "Town Panchayat"
    PANCHAYAT_UNION = "panchayat_union", "Panchayat Union"


class PermissionType(models.TextChoices):
    SCREEN = "screen", "Screen Permission"
    FIELD = "field", "Field Permission"


class PermissionOwnerKind(models.TextChoices):
    SUPER_ADMIN = "super_admin", "Super Admin"
    STAFF = "staff", "Staff"


def generate_userscreenpermission_id():
    return f"USERSCRNPERM-{generate_unique_id()}"


class LocalBodyType(models.TextChoices):
    CORPORATION = "corporation", "Corporation"
    MUNICIPALITY = "municipality", "Municipality"
    PANCHAYAT = "panchayat", "Panchayat"
    TOWN_PANCHAYAT = "town_panchayat", "Town Panchayat"
    PANCHAYAT_UNION = "panchayat_union", "Panchayat Union"


class PermissionType(models.TextChoices):
    SCREEN = "screen", "Screen Permission"
    FIELD = "field", "Field Permission"


class PermissionOwnerKind(models.TextChoices):
    SUPER_ADMIN = "super_admin", "Super Admin"
    STAFF = "staff", "Staff"


class UserScreenPermission(BaseMaster):

    unique_id = models.CharField(
        max_length=60,
        primary_key=True,
        unique=True,
        default=generate_userscreenpermission_id,
        editable=False
    )

    usertype_id = models.CharField(
        max_length=30,
        db_column="usertype_id",
        db_index=True,
        null=True,
        blank=True
    )

    staffusertype_id = models.CharField(
        max_length=30,
        db_column="staffusertype_id",
        db_index=True,
        null=True,
        blank=True
    )

    contractorusertype_id = models.CharField(
        max_length=35,
        db_column="contractorusertype_id",
        db_index=True,
        null=True,
        blank=True
    )

    governmentusertype_id = models.CharField(
        max_length=40,
        db_column="governmentusertype_id",
        db_index=True,
        null=True,
        blank=True
    )

    # Plain CharFields holding State/District/AreaType.unique_id (no DB
    # relation/join) — matches the rest of the geo-hierarchy refactor's
    # convention.
    state_id = models.CharField(max_length=30, null=True, blank=True)
    district_id = models.CharField(max_length=30, null=True, blank=True)
    area_type_id = models.CharField(max_length=30, null=True, blank=True)

    local_body_type = models.CharField(
        max_length=20, choices=LocalBodyType.choices,
        null=True, blank=True
    )

    local_body_id = models.CharField(max_length=30, null=True, blank=True)

    permission_type = models.CharField(
        max_length=20, choices=PermissionType.choices,
        default=PermissionType.SCREEN
    )

    permission_owner_kind = models.CharField(
        max_length=20, choices=PermissionOwnerKind.choices,
        default=PermissionOwnerKind.SUPER_ADMIN
    )

    staff_id = models.CharField(max_length=60, null=True, blank=True)

    mainscreen_id = models.CharField(
        max_length=30,
        db_column="mainscreen_id",
        db_index=True,
    )

    userscreen_id = models.CharField(
        max_length=30,
        db_column="userscreen_id",
        db_index=True,
    )

    userscreenaction_id = models.CharField(
        max_length=30,
        db_column="userscreenaction_id",
        db_index=True,
    )

    order_no = models.IntegerField()
    description = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "app_userscreenpermission"
        ordering = ["order_no"]
        verbose_name = "User Screen Permission"
        verbose_name_plural = "User Screen Permissions"
        indexes = [
            models.Index(fields=["staffusertype_id", "mainscreen_id"]),
            models.Index(fields=["contractorusertype_id", "mainscreen_id"]),
            models.Index(fields=["local_body_type", "local_body_id", "mainscreen_id"]),
            models.Index(fields=["local_body_type", "local_body_id", "permission_owner_kind", "staff_id"]),
        ]
        constraints = [
            UniqueConstraint(
                fields=[
                    "usertype_id",
                    "staffusertype_id",
                    "contractorusertype_id",
                    "governmentusertype_id",
                    "mainscreen_id",
                    "userscreen_id",
                    "userscreenaction_id",
                ],
                condition=Q(is_deleted=False),
                name="uq_active_user_screen_permission",
            ),
            UniqueConstraint(
                fields=[
                    "state_id",
                    "district_id",
                    "area_type_id",
                    "local_body_type",
                    "local_body_id",
                    "permission_owner_kind",
                    "staff_id",
                    "mainscreen_id",
                    "userscreen_id",
                    "userscreenaction_id",
                ],
                condition=Q(is_deleted=False, local_body_id__isnull=False),
                name="uq_active_local_body_screen_permission",
            ),
        ]

    def _lookup(self, model_path, value, field="unique_id"):
        if not value:
            return None
        import importlib

        module_path, class_name = model_path.rsplit(".", 1)
        model = getattr(importlib.import_module(module_path), class_name)
        return ref_cache.get(model, value, field)

    @property
    def usertype(self):
        return self._lookup("app.models.superadmin.role_management.userType.UserType", self.usertype_id)

    @property
    def staffusertype(self):
        return self._lookup("app.models.superadmin.role_management.staffUserType.StaffUserType", self.staffusertype_id)

    @property
    def contractorusertype(self):
        return self._lookup("app.models.superadmin.role_management.contractorUserType.ContractorUserType", self.contractorusertype_id)

    @property
    def governmentusertype(self):
        return self._lookup("app.models.superadmin.role_management.governmentStaffUserType.GovernmentStaffUserType", self.governmentusertype_id)

    @property
    def mainscreen(self):
        return self._lookup("app.models.superadmin.screen_management.mainscreen.MainScreen", self.mainscreen_id)

    @property
    def userscreen(self):
        return self._lookup("app.models.superadmin.screen_management.userscreen.UserScreen", self.userscreen_id)

    @property
    def userscreenaction(self):
        return self._lookup("app.models.superadmin.screen_management.userscreenaction.UserScreenAction", self.userscreenaction_id)
