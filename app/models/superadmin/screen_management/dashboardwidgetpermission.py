from django.db import models
from django.db.models import Q, UniqueConstraint
from app.models.superadmin.screen_management.userscreenpermission import LocalBodyType, PermissionOwnerKind
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils import ref_cache


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
    usertype_id = models.CharField(
        max_length=30,
        db_column="usertype_id",
        db_index=True,
        null=True,
        blank=True,
    )
    staffusertype_id = models.CharField(
        max_length=30,
        db_column="staffusertype_id",
        db_index=True,
        null=True,
        blank=True,
    )
    contractorusertype_id = models.CharField(
        max_length=35,
        db_column="contractorusertype_id",
        db_index=True,
        null=True,
        blank=True,
    )
    governmentusertype_id = models.CharField(
        max_length=40,
        db_column="governmentusertype_id",
        db_index=True,
        null=True,
        blank=True,
    )
    # Plain CharFields holding State/District/AreaType.unique_id (no DB
    # relation/join) — matches the rest of the geo-hierarchy refactor's
    # convention.
    state_id = models.CharField(max_length=30, null=True, blank=True)
    district_id = models.CharField(max_length=30, null=True, blank=True)
    area_type_id = models.CharField(max_length=30, null=True, blank=True)
    local_body_type = models.CharField(
        max_length=20, choices=LocalBodyType.choices,
        null=True, blank=True,
    )
    local_body_id = models.CharField(max_length=30, null=True, blank=True)

    permission_owner_kind = models.CharField(
        max_length=20, choices=PermissionOwnerKind.choices,
        default=PermissionOwnerKind.SUPER_ADMIN,
    )
    staff_id = models.CharField(max_length=60, null=True, blank=True)

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
                fields=[
                    "usertype_id",
                    "staffusertype_id",
                    "contractorusertype_id",
                    "governmentusertype_id",
                    "widget_name",
                ],
                condition=Q(is_deleted=False),
                name="uq_active_staff_dashboard_widget_permission",
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
                    "widget_name",
                ],
                condition=Q(is_deleted=False, local_body_id__isnull=False),
                name="uq_active_local_body_dashboard_widget_permission",
            ),
        ]

    def __str__(self):
        return f"{self.widget_name} ({self.staffusertype_id or self.contractorusertype_id or self.governmentusertype_id})"

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
