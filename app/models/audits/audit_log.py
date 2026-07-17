from django.db import models

from app.models.user_creations.auditlog import generate_login_id
from app.models.screen_managements.mainscreen import MainScreen
from app.models.screen_managements.userscreen import UserScreen
from app.models.screen_managements.userscreenaction import UserScreenAction
from app.models.user_creations.staffcreation import Staffcreation
from app.models.role_assigns.staffUserType import StaffUserType


class AuditLog(models.Model):

    # -------------------------------------------------
    # PRIMARY IDENTIFIER
    # -------------------------------------------------
    unique_id = models.CharField(
        max_length=100,
        primary_key=True,
        default=generate_login_id,
        editable=False
    )

    # -------------------------------------------------
    # WHO performed the action
    # -------------------------------------------------
    user_id = models.ForeignKey(
        Staffcreation,
        on_delete=models.PROTECT,
        to_field="staff_unique_id",
        db_column="user_id",
        related_name="audit_logs"
    )

    # -------------------------------------------------
    # AS WHICH ROLE (snapshot at action time)
    # -------------------------------------------------
    staffusertype_id = models.ForeignKey(
        StaffUserType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="staffusertype_id",
        related_name="audit_logs"
    )

    # -------------------------------------------------
    # WHERE the action occurred
    # -------------------------------------------------
    mainscreen_id = models.ForeignKey(
        MainScreen,
        on_delete=models.PROTECT,
        to_field="unique_id",
        db_column="mainscreen_id",
        related_name="audit_logs"
    )

    userscreen_id = models.ForeignKey(
        UserScreen,
        on_delete=models.PROTECT,
        to_field="unique_id",
        db_column="userscreen_id",
        related_name="audit_logs"
    )

    # -------------------------------------------------
    # WHAT action was performed
    # -------------------------------------------------
    userscreenaction_id = models.ForeignKey(
        UserScreenAction,
        on_delete=models.PROTECT,
        to_field="unique_id",
        db_column="userscreenaction_id",
        related_name="audit_logs"
    )

    # -------------------------------------------------
    # OUTCOME (MANDATORY)
    # -------------------------------------------------
    success = models.BooleanField()

    reason = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    # -------------------------------------------------
    # FORENSICS / SECURITY
    # -------------------------------------------------
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True
    )

    user_agent = models.TextField(
        null=True,
        blank=True
    )

    # -------------------------------------------------
    # TIMESTAMP
    # -------------------------------------------------
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True
    )

    # -------------------------------------------------
    # META CONFIGURATION
    # -------------------------------------------------
    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"
        indexes = [
            models.Index(fields=["user_id"]),
            models.Index(fields=["staffusertype_id"]),
            models.Index(fields=["mainscreen_id"]),
            models.Index(fields=["userscreen_id"]),
            models.Index(fields=["userscreenaction_id"]),
            models.Index(fields=["timestamp"]),
        ]

    def __str__(self):
        return f"{self.unique_id} | {self.user_id} | {self.userscreenaction_id}"
