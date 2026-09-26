from django.db import models
from django.db.models import Q, UniqueConstraint
from app.models.superadmin.screen_management.userscreen import UserScreen
from app.models.superadmin.screen_management.userscreencolumn import UserScreenColumn
from app.models.superadmin.screen_management.userscreenpermission import LocalBodyType, PermissionOwnerKind
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils import ref_cache


def generate_userscreencolumnpermission_id():
    return f"USERSCRNCOLPERM-{generate_unique_id()}"


def generate_companyuserscreencolumnpermission_id():
    return generate_userscreencolumnpermission_id()


class UserScreenColumnPermission(BaseMaster):
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

    userscreen_id = models.CharField(
        max_length=30,
        db_column="userscreen_id",
        db_index=True,
    )
    column_id = models.CharField(
        max_length=30,
        db_column="column_id",
        db_index=True,
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
        db_table = "app_userscreencolumnpermission"
        ordering = ["order_no"]
        verbose_name = "User Screen Column Permission"
        verbose_name_plural = "User Screen Column Permissions"
        indexes = [
            models.Index(fields=["userscreen_id"]),
            models.Index(fields=["staffusertype_id", "userscreen_id"]),
            models.Index(fields=["contractorusertype_id", "userscreen_id"]),
            models.Index(fields=["governmentusertype_id", "userscreen_id"]),
            models.Index(fields=["userscreen_id", "column_id", "is_active", "is_deleted"]),
            models.Index(fields=["local_body_type", "local_body_id", "userscreen_id"]),
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
                    "userscreen_id",
                    "column_id",
                ],
                condition=Q(is_deleted=False, local_body_id__isnull=False),
                name="uq_active_local_body_column_perm",
            ),
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
    def userscreen(self):
        return self._lookup("app.models.superadmin.screen_management.userscreen.UserScreen", self.userscreen_id)

    @property
    def column(self):
        return self._lookup("app.models.superadmin.screen_management.userscreencolumn.UserScreenColumn", self.column_id)
