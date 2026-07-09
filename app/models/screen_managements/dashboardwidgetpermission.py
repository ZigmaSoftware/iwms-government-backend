from django.db import models
from django.db.models import Q, UniqueConstraint

from app.models.role_assigns.contractorUserType import ContractorUserType
from app.models.role_assigns.governmentStaffUserType import GovernmentStaffUserType
from app.models.role_assigns.staffUserType import StaffUserType
from app.models.role_assigns.userType import UserType
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_dashboardwidgetpermission_id():
    return f"DASHWGT-{generate_unique_id()}"


class DashboardWidgetPermission(BaseMaster):
    unique_id = models.CharField(
        max_length=60,
        primary_key=True,
        unique=True,
        default=generate_dashboardwidgetpermission_id,
        editable=False,
    )
    usertype_id = models.ForeignKey(
        UserType,
        on_delete=models.PROTECT,
        to_field="unique_id",
        db_column="usertype_id",
        related_name="dashboard_widget_permissions",
        null=True,
        blank=True,
    )
    staffusertype_id = models.ForeignKey(
        StaffUserType,
        on_delete=models.PROTECT,
        to_field="unique_id",
        db_column="staffusertype_id",
        related_name="dashboard_widget_permissions",
        null=True,
        blank=True,
    )
    contractorusertype_id = models.ForeignKey(
        ContractorUserType,
        on_delete=models.PROTECT,
        to_field="unique_id",
        db_column="contractorusertype_id",
        related_name="dashboard_widget_permissions",
        null=True,
        blank=True,
    )
    governmentusertype_id = models.ForeignKey(
        GovernmentStaffUserType,
        on_delete=models.PROTECT,
        to_field="unique_id",
        db_column="governmentusertype_id",
        related_name="dashboard_widget_permissions",
        null=True,
        blank=True,
    )
    widget_name = models.CharField(max_length=50)
    is_enabled = models.BooleanField(default=True)
    order_no = models.IntegerField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order_no"]
        verbose_name = "Dashboard Widget Permission"
        verbose_name_plural = "Dashboard Widget Permissions"
        constraints = [
            UniqueConstraint(
                fields=["usertype_id", "staffusertype_id", "widget_name"],
                condition=Q(is_deleted=False),
                name="uq_active_staff_dashboard_widget_permission",
            )
        ]

    def __str__(self):
        return f"{self.widget_name} ({self.staffusertype_id or self.contractorusertype_id or self.governmentusertype_id})"
