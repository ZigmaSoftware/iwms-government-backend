from django.db import models
from django.conf import settings
from django.utils import timezone

from app.utils.cascade_delete import cascade_soft_delete




class Account(models.Model):

    # Use string primary key
    account_id = models.CharField(
        max_length=50,
        primary_key=True,
        editable=False
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    staff = models.OneToOneField(
        "app.StaffcreationOfficeDetails",
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    def save(self, *args, **kwargs):
        # Auto assign account_id from related model
        if self.user:
            self.account_id = self.user.unique_id
        elif self.staff:
            self.account_id = self.staff.staff_unique_id

        super().save(*args, **kwargs)


class BaseMaster(models.Model):
    """Shared active/deleted flags for most tables."""
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    # Why the record was deleted — required from the user on every delete
    # (see app/utils/delete_reason.py) and kept for audit.
    delete_reason = models.CharField(max_length=500, null=True, blank=True)

    # Reverse-relation names (related_name strings) to soft-delete
    # transitively when this row is soft-deleted. See app/utils/cascade_delete.py.
    CASCADE_SOFT_DELETE = ()

    created_by = models.CharField(
        max_length=50,
        db_column="created_by_id",
        null=True,
        blank=True,
        db_index=True,
    )

    updated_by = models.CharField(
        max_length=50,
        db_column="updated_by_id",
        null=True,
        blank=True,
        db_index=True,
    )

    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    # When the row was soft-deleted and who deleted it. deleted_at is
    # stamped automatically by save() on any is_deleted flip (covers the
    # model-level delete() overrides and the viewsets that flip the flags
    # by hand); deleted_by is stamped by cascade_soft_delete() and by
    # DeleteReasonMixin for request-driven deletes.
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.CharField(
        max_length=50,
        db_column="deleted_by_id",
        null=True,
        blank=True,
        db_index=True,
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if getattr(self, "is_deleted", False) and getattr(self, "deleted_at", None) is None:
            self.deleted_at = timezone.now()
            update_fields = kwargs.get("update_fields")
            if update_fields is not None and "deleted_at" not in update_fields:
                kwargs["update_fields"] = [*update_fields, "deleted_at"]
        super().save(*args, **kwargs)

    def delete(self, *args, updated_by=None, delete_reason=None, deleted_by=None, **kwargs):
        cascade_soft_delete(
            self, updated_by=updated_by, delete_reason=delete_reason, deleted_by=deleted_by
        )