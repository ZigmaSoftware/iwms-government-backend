from django.db import models
from django.db.models import UniqueConstraint

from app.models.role_assigns.contractorUserType import ContractorUserType
from app.models.role_assigns.governmentStaffUserType import GovernmentStaffUserType
from app.models.role_assigns.staffUserType import StaffUserType
from app.models.role_assigns.userType import UserType
from app.models.screen_managements.userscreen import UserScreen
from app.models.screen_managements.userscreencolumn import UserScreenColumn
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_companyuserscreencolumnpermission_id():
    return f"CMPUSERSCRNCOLPERM-{generate_unique_id()}"


class CompanyUserScreenColumnPermission(BaseMaster):
    VISIBLE = "VISIBLE"
    HIDDEN = "HIDDEN"
    EDITABLE = "EDITABLE"
    READ_ONLY = "READ_ONLY"
    MANDATORY = "MANDATORY"

    FIELD_PERMISSION_STATE_CHOICES = [
        (VISIBLE, "Visible"),
        (HIDDEN, "Hidden"),
        (EDITABLE, "Editable"),
        (READ_ONLY, "Read Only"),
        (MANDATORY, "Mandatory"),
    ]

    unique_id = models.CharField(
        max_length=70,
        primary_key=True,
        unique=True,
        default=generate_companyuserscreencolumnpermission_id,
        editable=False,
    )

    usertype_id = models.ForeignKey(
        UserType,
        on_delete=models.PROTECT,
        related_name="userscreen_column_permissions",
        to_field="unique_id",
        db_column="usertype_id",
        null=True,
        blank=True,
    )
    staffusertype_id = models.ForeignKey(
        StaffUserType,
        on_delete=models.PROTECT,
        related_name="userscreen_column_permissions",
        to_field="unique_id",
        db_column="staffusertype_id",
        null=True,
        blank=True,
    )
    contractorusertype_id = models.ForeignKey(
        ContractorUserType,
        on_delete=models.PROTECT,
        related_name="userscreen_column_permissions",
        to_field="unique_id",
        db_column="contractorusertype_id",
        null=True,
        blank=True,
    )
    governmentusertype_id = models.ForeignKey(
        GovernmentStaffUserType,
        on_delete=models.PROTECT,
        related_name="userscreen_column_permissions",
        to_field="unique_id",
        db_column="governmentusertype_id",
        null=True,
        blank=True,
    )
    userscreen_id = models.ForeignKey(
        UserScreen,
        on_delete=models.PROTECT,
        related_name="column_permissions",
        to_field="unique_id",
        db_column="userscreen_id",
    )
    column_id = models.ForeignKey(
        UserScreenColumn,
        on_delete=models.PROTECT,
        related_name="company_permissions",
        to_field="unique_id",
        db_column="column_id",
    )

    field_permission_state = models.CharField(
        max_length=20,
        choices=FIELD_PERMISSION_STATE_CHOICES,
        default=VISIBLE,
    )
    order_no = models.IntegerField(default=1)
    description = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order_no"]
        verbose_name = "Company User Screen Column Permission"
        verbose_name_plural = "Company User Screen Column Permissions"
        indexes = [
            models.Index(fields=["userscreen_id"]),
            models.Index(fields=["staffusertype_id", "userscreen_id"]),
            models.Index(fields=["contractorusertype_id", "userscreen_id"]),
            models.Index(fields=["governmentusertype_id", "userscreen_id"]),
            models.Index(fields=["userscreen_id", "column_id", "is_active", "is_deleted"]),
        ]
        constraints = [
            UniqueConstraint(
                fields=[
                    "usertype_id",
                    "staffusertype_id",
                    "contractorusertype_id",
                    "governmentusertype_id",
                    "userscreen_id",
                    "column_id",
                    "is_deleted",
                ],
                name="uq_screen_column_perm",
            )
        ]

    @property
    def userscreencolumn_id(self):
        return self.column_id

    @property
    def can_view(self):
        return self.field_permission_state != self.HIDDEN

    @can_view.setter
    def can_view(self, value):
        self.field_permission_state = self.VISIBLE if value else self.HIDDEN

    def __str__(self):
        return f"{self.userscreen_id} - {self.column_id}"

    def delete(self, *args, **kwargs):
        self.is_active = False
        self.is_deleted = True
        self.save(update_fields=["is_active", "is_deleted"])
