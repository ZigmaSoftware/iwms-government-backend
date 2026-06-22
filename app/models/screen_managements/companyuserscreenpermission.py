from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.screen_managements.mainscreen import MainScreen
from app.models.screen_managements.userscreen import UserScreen
from app.models.role_assigns.userType import UserType
from app.models.role_assigns.staffUserType import StaffUserType
from app.models.screen_managements.userscreenaction import UserScreenAction
from django.db.models import Q, UniqueConstraint

from app.models.role_assigns.contractorUserType import ContractorUserType
from app.models.role_assigns.governmentStaffUserType import GovernmentStaffUserType


def generate_userscreenpermission_id():
    return f"USERSCRNPERM-{generate_unique_id()}"


def generate_companyuserscreenpermission_id():
    return generate_userscreenpermission_id()


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
        related_name="userscreenpermissions"
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
            )
        ]


    def delete(self, *args, **kwargs):
        self.is_active = False
        self.is_deleted = True
        self.save(update_fields=["is_active", "is_deleted"])


CompanyUserScreenPermission = UserScreenPermission
