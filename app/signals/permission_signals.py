from django.db.models.signals import post_save
from django.dispatch import receiver

from app.models.screen_managements.companyuserscreenpermission import UserScreenPermission
from app.models.audits.permission_audit import PermissionAuditLog


@receiver(post_save, sender=UserScreenPermission)
def log_permission_change(sender, instance, created, **kwargs):
    try:
        action_type = "CREATED" if created else "UPDATED"
        if not created and instance.is_deleted:
            action_type = "DELETED"

        updated_by = None
        account = getattr(instance, "updated_by", None)
        if account is not None:
            updated_by = getattr(account, "staff", None)

        PermissionAuditLog.objects.create(
            staffusertype_id=instance.staffusertype_id_id,
            mainscreen_id=instance.mainscreen_id_id,
            userscreen_id=instance.userscreen_id_id,
            userscreenaction_id=instance.userscreenaction_id_id,
            updated_by=updated_by,
            is_active=instance.is_active,
            is_deleted=instance.is_deleted,
            action_type=action_type,
        )

    except Exception as e:
        print("❌ Permission Audit Log Error:", str(e))
