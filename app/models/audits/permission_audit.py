from django.db import models

from app.models.screen_managements.mainscreen import MainScreen
from app.models.screen_managements.userscreen import UserScreen
from app.models.screen_managements.userscreenaction import UserScreenAction
from app.models.role_assigns.staffUserType import StaffUserType
from app.models.superadmin_masters.company import Company
from app.models.user_creations.staffcreation import Staffcreation


class PermissionAuditLog(models.Model):
    """Track permission updates for audit trail."""

    ACTION_CHOICES = [
        ("CREATED", "Created"),
        ("UPDATED", "Updated"),
        ("DELETED", "Deleted"),
    ]

    company= models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        to_field="unique_id",
        db_column="company_id",
    )
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