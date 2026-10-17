import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from app.models.superadmin.screen_management.userscreenpermission import UserScreenPermission
from app.models.superadmin.audits.permission_audit import PermissionAuditLog
from app.utils.permission_snapshot import snapshot_audit_active

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=UserScreenPermission)
def _stash_previous_permission_state(sender, instance, **kwargs):
    """Snapshot is_active/is_deleted as they stood before this save, so the
    post_save handler below can log what changed instead of only the latest
    state. No previous row (a plain insert) leaves both fields unset, which
    log_permission_change treats as "no prior state"."""
    if not instance.pk:
        return
    previous = UserScreenPermission.objects.filter(pk=instance.pk).values(
        "is_active", "is_deleted"
    ).first()
    if previous:
        instance._previous_permission_state = previous


@receiver(post_save, sender=UserScreenPermission)
def log_permission_change(sender, instance, created, **kwargs):
    # Requests through a permission screen record ONE row per save with the
    # whole access before and after it (app/utils/permission_snapshot.py);
    # a per-grant row here would only repeat it. Writes made anywhere else
    # (cascade deletes, admin, shell) still get a per-grant row.
    if snapshot_audit_active():
        return
    try:
        action_type = "CREATED" if created else "UPDATED"
        if not created and instance.is_deleted:
            action_type = "DELETED"

        updated_by = None
        # BaseMaster.updated_by is a plain Account id string (no DB relation).
        account_id = getattr(instance, "updated_by", None)
        if account_id:
            from app.utils.base_models import Account

            account = Account.objects.filter(pk=account_id).select_related("staff").first()
            updated_by = getattr(account, "staff", None)

        previous = getattr(instance, "_previous_permission_state", None)

        PermissionAuditLog.objects.create(
            source="GRANT_CHANGE",
            usertype_id=instance.usertype_id,
            staffusertype_id=instance.staffusertype_id,
            contractorusertype_id=instance.contractorusertype_id,
            governmentusertype_id=instance.governmentusertype_id,
            permission_owner_kind=instance.permission_owner_kind,
            local_body_type=instance.local_body_type,
            local_body_id=instance.local_body_id,
            staff_id=instance.staff_id,
            mainscreen_id=instance.mainscreen_id,
            userscreen_id=instance.userscreen_id,
            userscreenaction_id=instance.userscreenaction_id,
            updated_by_id=getattr(updated_by, "staff_unique_id", None),
            is_active=instance.is_active,
            is_deleted=instance.is_deleted,
            previous_is_active=previous["is_active"] if previous else None,
            previous_is_deleted=previous["is_deleted"] if previous else None,
            action_type=action_type,
        )

    except Exception:
        logger.exception("Failed to write PermissionAuditLog for UserScreenPermission %s", instance.pk)
