from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.screen_managements.mainscreen import MainScreen
from app.models.screen_managements.userscreen import UserScreen
from app.models.role_assigns.userType import UserType
from app.models.role_assigns.staffUserType import StaffUserType
from app.models.screen_managements.userscreenaction import UserScreenAction
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from django.db.models import Q, UniqueConstraint

from app.models.role_assigns.contractorUserType import ContractorUserType


def generate_companyuserscreenpermission_id():
    return f"CMPUSERSCRNPERM-{generate_unique_id()}"


class CompanyUserScreenPermission(BaseMaster):
    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="project_id",
    )

    unique_id = models.CharField(
        max_length=60,
        primary_key=True,
        unique=True,
        default=generate_companyuserscreenpermission_id,
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
    
    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        to_field="unique_id", db_column="company_id",
        related_name="userscreenpermissions"
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
        ordering = ["order_no"]
        indexes = [
            models.Index(fields=["company_id", "staffusertype_id", "mainscreen_id"]),
            models.Index(fields=["company_id", "contractorusertype_id", "mainscreen_id"]),
        ]
        constraints = [
            UniqueConstraint(
                fields=[
                    "company_id",
                    "usertype_id",
                    "staffusertype_id",
                    "contractorusertype_id",
                    "mainscreen_id",
                    "userscreen_id",
                    "userscreenaction_id",
                ],
                condition=Q(is_deleted=False),
                name="uq_active_company_user_screen_permission",
            )
        ]


    def delete(self, *args, **kwargs):
        self.is_active = False
        self.is_deleted = True
        self.save(update_fields=["is_active", "is_deleted"])
