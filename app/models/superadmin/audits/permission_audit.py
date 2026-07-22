from django.db import models

from app.models.superadmin.screen_management.mainscreen import MainScreen
from app.models.superadmin.screen_management.userscreen import UserScreen
from app.models.superadmin.screen_management.userscreenaction import UserScreenAction
from app.models.superadmin.role_management.staffUserType import StaffUserType
from app.models.superadmin.user_management.staffcreation import Staffcreation


class PermissionAuditLog(models.Model):
    """Track permission updates for audit trail."""

    ACTION_CHOICES = [
        ("CREATED", "Created"),
        ("UPDATED", "Updated"),
        ("DELETED", "Deleted"),
    ]

    staffusertype = models.ForeignKey(
        StaffUserType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        to_field="unique_id",
        db_column="staffusertype_id",
    )
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
    action_type = models.CharField(max_length=10, choices=ACTION_CHOICES, default="UPDATED")
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "permission_audit_logs"
        ordering = ["-timestamp"]
