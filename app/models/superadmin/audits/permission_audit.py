from django.db import models

from app.models.superadmin.screen_management.mainscreen import MainScreen
from app.models.superadmin.screen_management.userscreen import UserScreen
from app.models.superadmin.screen_management.userscreenaction import UserScreenAction
from app.models.superadmin.screen_management.userscreenpermission import LocalBodyType
from app.models.superadmin.role_management.staffUserType import StaffUserType
from app.models.superadmin.role_management.userType import UserType
from app.models.superadmin.role_management.contractorUserType import ContractorUserType
from app.models.superadmin.role_management.governmentStaffUserType import GovernmentStaffUserType
from app.models.superadmin.staff_management.staffcreation import Staffcreation


class PermissionAuditLog(models.Model):
    """Track permission updates for audit trail."""

    ACTION_CHOICES = [
        ("CREATED", "Created"),
        ("UPDATED", "Updated"),
        ("DELETED", "Deleted"),
    ]

    usertype = models.ForeignKey(
        UserType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        to_field="unique_id",
        db_column="usertype_id",
    )
    staffusertype = models.ForeignKey(
        StaffUserType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        to_field="unique_id",
        db_column="staffusertype_id",
    )
    contractorusertype = models.ForeignKey(
        ContractorUserType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        to_field="unique_id",
        db_column="contractorusertype_id",
    )
    governmentusertype = models.ForeignKey(
        GovernmentStaffUserType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        to_field="unique_id",
        db_column="governmentusertype_id",
    )
    # Local-body ownership context, mirrored from UserScreenPermission at
    # write time so a grant with no role attached (permission_owner_kind
    # "super_admin"/"staff" scoped to a local body, not a StaffUserType)
    # still carries a meaningful "who this applies to" on the audit row.
    permission_owner_kind = models.CharField(max_length=20, null=True, blank=True)
    local_body_type = models.CharField(
        max_length=20, choices=LocalBodyType.choices, null=True, blank=True,
    )
    local_body_id = models.CharField(max_length=30, null=True, blank=True)
    staff_id = models.CharField(max_length=60, null=True, blank=True)
    mainscreen = models.ForeignKey(
        MainScreen,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        to_field="unique_id",
        db_column="mainscreen_id",
    )
    userscreen = models.ForeignKey(
        UserScreen,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        to_field="unique_id",
        db_column="userscreen_id",
    )
    userscreenaction = models.ForeignKey(
        UserScreenAction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        to_field="unique_id",
        db_column="userscreenaction_id",
    )
    updated_by = models.ForeignKey(
        Staffcreation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(null=True, blank=True)
    is_deleted = models.BooleanField(null=True, blank=True)
    previous_is_active = models.BooleanField(null=True, blank=True)
    previous_is_deleted = models.BooleanField(null=True, blank=True)
    action_type = models.CharField(max_length=10, choices=ACTION_CHOICES, default="UPDATED")
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "permission_audit_logs"
        ordering = ["-timestamp"]
