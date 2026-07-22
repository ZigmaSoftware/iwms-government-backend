from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.superadmin.screen_management.mainscreen import MainScreen
from app.models.superadmin.screen_management.userscreen import UserScreen
from app.models.superadmin.role_management.userType import UserType
from app.models.superadmin.role_management.staffUserType import StaffUserType
from app.models.superadmin.screen_management.userscreenaction import UserScreenAction
from django.db.models import Q, UniqueConstraint

from app.models.superadmin.role_management.contractorUserType import ContractorUserType
from app.models.superadmin.role_management.governmentStaffUserType import GovernmentStaffUserType
from app.models.superadmin.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType


def generate_userscreenpermission_id():
    return f"USERSCRNPERM-{generate_unique_id()}"


def generate_companyuserscreenpermission_id():
    return generate_userscreenpermission_id()


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

    usertype_id = models.ForeignKey(
        UserType, on_delete=models.PROTECT,
        to_field="unique_id", db_column="usertype_id",
        related_name="userscreenpermissions",
        null=True, blank=True
    )

    staffusertype_id = models.ForeignKey(
        StaffUserType,
        on_delete=models.PROTECT,
        to_field="unique_id",
        db_column="staffusertype_id",
        related_name="userscreenpermissions",
        null=True,
        blank=True
    )

    contractorusertype_id = models.ForeignKey(
        ContractorUserType,
        on_delete=models.PROTECT,
        to_field="unique_id",
        db_column="contractorusertype_id",
        related_name="userscreenpermissions",
        null=True,
        blank=True
    )

    governmentusertype_id = models.ForeignKey(
        GovernmentStaffUserType,
        on_delete=models.PROTECT,
        to_field="unique_id",
        db_column="governmentusertype_id",
        related_name="userscreenpermissions",
        null=True,
        blank=True
    )

    state_id = models.ForeignKey(
        State, on_delete=models.PROTECT,
        to_field="unique_id", db_column="state_id",
        related_name="userscreenpermissions",
        null=True, blank=True
    )

    district_id = models.ForeignKey(
        District, on_delete=models.PROTECT,
        to_field="unique_id", db_column="district_id",
        related_name="userscreenpermissions",
        null=True, blank=True
    )

    area_type_id = models.ForeignKey(
        AreaType, on_delete=models.PROTECT,
        to_field="unique_id", db_column="area_type_id",
        related_name="userscreenpermissions",
        null=True, blank=True
    )

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

    mainscreen_id = models.ForeignKey(
        MainScreen, on_delete=models.PROTECT,
        to_field="unique_id", db_column="mainscreen_id",
        related_name="userscreenpermissions"
    )

    userscreen_id = models.ForeignKey(
        UserScreen, on_delete=models.PROTECT,
        to_field="unique_id", db_column="userscreen_id",
        related_name="userscreenpermissions"
    )

    userscreenaction_id = models.ForeignKey(
        UserScreenAction, on_delete=models.PROTECT,
        to_field="unique_id", db_column="userscreenaction_id",
        related_name="userscreenpermissions"
    )

    order_no = models.IntegerField()
    description = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "app_companyuserscreenpermission"
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


    def delete(self, *args, **kwargs):
        self.is_active = False
        self.is_deleted = True
        self.save(update_fields=["is_active", "is_deleted"])


CompanyUserScreenPermission = UserScreenPermission
