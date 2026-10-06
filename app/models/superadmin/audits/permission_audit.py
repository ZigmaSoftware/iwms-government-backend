from django.db import models

from app.models.superadmin.screen_management.mainscreen import MainScreen
from app.models.superadmin.screen_management.userscreen import UserScreen
from app.models.superadmin.screen_management.userscreenaction import UserScreenAction
from app.models.superadmin.screen_management.userscreenpermission import LocalBodyType
from app.utils import ref_cache


class PermissionAuditLog(models.Model):
    """Track permission updates for audit trail."""

    ACTION_CHOICES = [
        ("CREATED", "Created"),
        ("UPDATED", "Updated"),
        ("DELETED", "Deleted"),
    ]

    # Where the grant was made. Every current source stores ONE row per save
    # with the whole access before and after it (old_permissions /
    # new_permissions, see app/utils/permission_snapshot.py): per local body
    # + role for LOCAL_BODY_SCREEN, per role for ROLE_SCREEN, per person for
    # STAFF_ACCESS / CUSTOMER_ACCESS.
    SOURCE_CHOICES = [
        ("LOCAL_BODY_SCREEN", "Local Body Screen Permission"),
        ("ROLE_SCREEN", "Role Screen Permission"),
        ("STAFF_ACCESS", "Staff Access Configuration"),
        ("CUSTOMER_ACCESS", "Customer Access Configuration"),
        # Per-grant rows written by the UserScreenPermission post_save signal
        # (app/signals/permission_signals.py): every row from before saves
        # were snapshotted, plus any write made outside an audited request.
        ("GRANT_CHANGE", "Screen Permission Change"),
    ]
    CURRENT_SOURCES = ("LOCAL_BODY_SCREEN", "ROLE_SCREEN", "STAFF_ACCESS", "CUSTOMER_ACCESS")

    source = models.CharField(
        max_length=20, choices=SOURCE_CHOICES, default="GRANT_CHANGE", db_index=True
    )
    # Who received the access: a staff_unique_id for STAFF_ACCESS rows, a
    # customer unique_id for CUSTOMER_ACCESS rows. Local-body / role grants
    # have no single recipient and leave it blank.
    target_id = models.CharField(max_length=60, null=True, blank=True, db_index=True)
    # HTTP method of the request that made the change (POST/PUT/PATCH/DELETE).
    http_method = models.CharField(max_length=10, null=True, blank=True)
    # The whole access before and after the save; see
    # app/utils/permission_snapshot.py for the shape. Per-grant rows leave
    # both blank.
    old_permissions = models.JSONField(null=True, blank=True)
    new_permissions = models.JSONField(null=True, blank=True)
    # Geography of the grant (or of the person who received it), so the
    # list can be scoped to the requester's own hierarchy.
    state_id = models.CharField(max_length=30, null=True, blank=True)
    district_id = models.CharField(max_length=30, null=True, blank=True, db_index=True)
    area_type_id = models.CharField(max_length=30, null=True, blank=True)

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
    # Local-body ownership context, mirrored from UserScreenPermission at
    # write time so a grant with no role attached (permission_owner_kind
    # "super_admin"/"staff" scoped to a local body, not a StaffUserType)
    # still carries a meaningful "who this applies to" on the audit row.
    permission_owner_kind = models.CharField(max_length=20, null=True, blank=True)
    local_body_type = models.CharField(
        max_length=20, choices=LocalBodyType.choices, null=True, blank=True,
    )
    local_body_id = models.CharField(max_length=30, null=True, blank=True, db_index=True)
    staff_id = models.CharField(max_length=60, null=True, blank=True, db_index=True)
    mainscreen_id = models.CharField(
        max_length=30,
        db_column="mainscreen_id",
        db_index=True,
        null=True,
        blank=True,
    )
    userscreen_id = models.CharField(
        max_length=30,
        db_column="userscreen_id",
        db_index=True,
        null=True,
        blank=True,
    )
    userscreenaction_id = models.CharField(
        max_length=30,
        db_column="userscreenaction_id",
        db_index=True,
        null=True,
        blank=True,
    )
    # Actor: a staff_unique_id for staff, or the platform User.unique_id
    # (up to 100 chars) for platform users.
    updated_by_id = models.CharField(
        max_length=100,
        db_column="updated_by",
        db_index=True,
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
    def mainscreen(self):
        return self._lookup("app.models.superadmin.screen_management.mainscreen.MainScreen", self.mainscreen_id)

    @property
    def userscreen(self):
        return self._lookup("app.models.superadmin.screen_management.userscreen.UserScreen", self.userscreen_id)

    @property
    def userscreenaction(self):
        return self._lookup("app.models.superadmin.screen_management.userscreenaction.UserScreenAction", self.userscreenaction_id)

    @property
    def updated_by(self):
        return self._lookup("app.models.superadmin.staff_management.staffcreation.Staffcreation", self.updated_by_id, field="staff_unique_id")
