from django.db import models
from app.utils.comfun import generate_unique_id
from app.models.superadmin.screen_management.mainscreen import MainScreen
from app.models.superadmin.screen_management.userscreen import UserScreen
from app.models.superadmin.screen_management.userscreenaction import UserScreenAction
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.models.superadmin.role_management.staffUserType import StaffUserType
from app.utils import ref_cache


def generate_login_id():
    return f"AUDITLOG-{generate_unique_id()}"


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
    user_id = models.CharField(
        max_length=30,
        db_column="user_id",
        db_index=True,
    )

    # -------------------------------------------------
    # AS WHICH ROLE (snapshot at action time)
    # -------------------------------------------------
    staffusertype_id = models.CharField(
        max_length=30,
        db_column="staffusertype_id",
        db_index=True,
        null=True,
        blank=True,
    )

    # -------------------------------------------------
    # WHERE the action occurred
    # -------------------------------------------------
    mainscreen_id = models.CharField(
        max_length=30,
        db_column="mainscreen_id",
        db_index=True,
    )

    userscreen_id = models.CharField(
        max_length=30,
        db_column="userscreen_id",
        db_index=True,
    )

    # -------------------------------------------------
    # WHAT action was performed
    # -------------------------------------------------
    userscreenaction_id = models.CharField(
        max_length=30,
        db_column="userscreenaction_id",
        db_index=True,
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

    def _lookup(self, model_path, value, field="unique_id"):
        if not value:
            return None
        import importlib

        module_path, class_name = model_path.rsplit(".", 1)
        model = getattr(importlib.import_module(module_path), class_name)
        return ref_cache.get(model, value, field)

    @property
    def user(self):
        return self._lookup("app.models.superadmin.staff_management.staffcreation.Staffcreation", self.user_id, field="staff_unique_id")

    @property
    def staffusertype(self):
        return self._lookup("app.models.superadmin.role_management.staffUserType.StaffUserType", self.staffusertype_id)

    @property
    def mainscreen(self):
        return self._lookup("app.models.superadmin.screen_management.mainscreen.MainScreen", self.mainscreen_id)

    @property
    def userscreen(self):
        return self._lookup("app.models.superadmin.screen_management.userscreen.UserScreen", self.userscreen_id)

    @property
    def userscreenaction(self):
        return self._lookup("app.models.superadmin.screen_management.userscreenaction.UserScreenAction", self.userscreenaction_id)
